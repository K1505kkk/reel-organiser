#!/usr/bin/env python3
# ============================================================
#  REEL WATCHER — Background Sheet Monitor
#  Watches column A of your Google Sheet for new URLs.
#  When it finds one with no summary yet, it:
#    1. Downloads the reel
#    2. Sends to Gemini for summary + label
#    3. Writes results back into the same row
#
#  Run once and leave it running in the background.
#  All interaction happens in the Google Sheet.
#
#  Setup:
#    pip install yt-dlp google-genai google-auth-oauthlib google-api-python-client
#
#  Usage:
#    python reel_watcher.py
# ============================================================

import os
import re
import json
import time
import tempfile
import yt_dlp
from datetime import datetime
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── CONFIG — edit these two lines ────────────────────────────
GEMINI_API_KEY   = "AIzaSyC9j1W-7u3VG1i3cU2qWC6jgT3aOAvF64g"
SPREADSHEET_ID   = "1344SzsRrl6jBYey6EHIiGYUiD-JC-okLocsuUdgEeUs"

# ── SETTINGS (leave as-is unless you want to change) ─────────
SHEET_NAME       = "Reels"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"
POLL_INTERVAL    = 30  # seconds between each sheet check

# Column positions (1-indexed, matching your sheet layout)
# A=URL, B=ShortID, C=Label, D=Summary(Notes), E=Date, F=Status
COL_URL     = 1
COL_ID      = 2
COL_LABEL   = 3
COL_SUMMARY = 4
COL_DATE    = 5
COL_STATUS  = 6

LABEL_LIST = [
    "Finance", "Tech", "Motivation", "Business",
    "Health", "Entertainment", "Learning", "Other"
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]


# ════════════════════════════════════════════════════════════
#  CONCEPT 1: AUTHENTICATION
#  OAuth2 lets your script act on behalf of your Google account.
#  First run: opens browser for login → saves token.json.
#  Every run after: uses token.json silently (no browser needed).
# ════════════════════════════════════════════════════════════
def get_sheets_service():
    creds = None

    # Load saved token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid token, get one
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token expired → silently refresh it
            creds.refresh(Request())
        else:
            # First time → open browser for login
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


# ════════════════════════════════════════════════════════════
#  CONCEPT 2: READING THE SHEET
#  We fetch all rows from the sheet and look for rows where:
#  - Column A (URL) has a value
#  - Column D (Summary) is EMPTY → means not processed yet
#  This is how the watcher knows what's new.
# ════════════════════════════════════════════════════════════
def get_unprocessed_rows(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F"
    ).execute()

    rows = result.get("values", [])
    unprocessed = []

    for i, row in enumerate(rows):
        if i == 0:
            continue  # skip header row

        # Pad row to 6 columns in case trailing cells are empty
        while len(row) < 6:
            row.append("")

        url     = row[COL_URL - 1].strip()
        summary = row[COL_SUMMARY - 1].strip()

        # A row is "unprocessed" if it has a URL but no summary yet
        if url and not summary:
            unprocessed.append({
                "row_index": i + 1,  # 1-indexed for Sheets API
                "url": url
            })

    return unprocessed


# ════════════════════════════════════════════════════════════
#  CONCEPT 3: DOWNLOADING WITH yt-dlp
#  yt-dlp is a command-line tool wrapped in Python.
#  It handles Instagram's CDN, redirects, and formats for us.
#  We save to a temp folder that auto-deletes after use.
# ════════════════════════════════════════════════════════════
def download_reel(url, output_dir):
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "reel.%(ext)s"),
        "format": "mp4/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base = os.path.splitext(filename)[0]
        mp4_path = base + ".mp4"
        if not os.path.exists(mp4_path):
            for f in os.listdir(output_dir):
                if f.startswith("reel"):
                    mp4_path = os.path.join(output_dir, f)
                    break
    return mp4_path


# ════════════════════════════════════════════════════════════
#  CONCEPT 4: GEMINI MULTIMODAL API
#  We upload the video to Gemini's File API (like an attachment).
#  Gemini processes the video frames + audio.
#  We prompt it to return structured JSON — summary + label.
#  We parse that JSON and write it back to the sheet.
# ════════════════════════════════════════════════════════════
def summarise_with_gemini(video_path):
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Upload video
    with open(video_path, "rb") as f:
        video_file = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type="video/mp4")
        )

    # Wait for Gemini to process the video
    while video_file.state.name == "PROCESSING":
        time.sleep(3)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Gemini failed to process video.")

    # Prompt Gemini — asking for strict JSON output
    prompt = f"""Watch this Instagram Reel carefully and respond ONLY with a JSON object. No extra text, no markdown.

{{
  "summary": "One clear sentence describing what this reel is about and its key insight",
  "label": "Pick exactly one from: {', '.join(LABEL_LIST)}"
}}"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[video_file, prompt]
    )

    # Clean and parse JSON response
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)

    # Clean up: delete video from Gemini servers
    client.files.delete(name=video_file.name)

    return result


# ════════════════════════════════════════════════════════════
#  CONCEPT 5: WRITING BACK TO THE SHEET
#  We use the Sheets API to update specific cells in the row
#  that we just processed. We write summary, label, date, status.
#  batchUpdate lets us write multiple cells in one API call.
# ════════════════════════════════════════════════════════════
def update_row(service, row_index, url, result):
    short_id = extract_reel_id(url)
    date_str = datetime.now().strftime("%d %b %Y")

    # Build the range string e.g. "Reels!A5:F5"
    range_str = f"{SHEET_NAME}!A{row_index}:F{row_index}"

    values = [[
        url,
        short_id,
        result["label"],
        result["summary"],
        date_str,
        "Unwatched"
    ]]

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_str,
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()


# ════════════════════════════════════════════════════════════
#  CONCEPT 6: THE POLLING LOOP
#  The script runs an infinite loop.
#  Every POLL_INTERVAL seconds it checks the sheet for new URLs.
#  This is called "polling" — a simple alternative to webhooks.
#  It's not instant (30s delay) but costs nothing and needs no server.
# ════════════════════════════════════════════════════════════
def extract_reel_id(url):
    match = re.search(r"/reel(?:s)?/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else "unknown"


def main():
    print("\n👁️  REEL WATCHER — running in background")
    print(f"   Checking sheet every {POLL_INTERVAL} seconds...")
    print("   Paste URLs into column A of your sheet.")
    print("   Press Ctrl+C to stop.\n")

    # Authenticate once at startup
    service = get_sheets_service()
    print("✅ Connected to Google Sheets\n")

    while True:
        try:
            # Check sheet for unprocessed rows
            pending = get_unprocessed_rows(service)

            if pending:
                print(f"🔍 Found {len(pending)} new reel(s) to process...")

                for item in pending:
                    url = item["url"]
                    row = item["row_index"]
                    print(f"\n▶ Row {row}: {url[:60]}...")

                    try:
                        # Mark as "Processing" immediately so we don't double-process
                        service.spreadsheets().values().update(
                            spreadsheetId=SPREADSHEET_ID,
                            range=f"{SHEET_NAME}!D{row}",
                            valueInputOption="USER_ENTERED",
                            body={"values": [["⏳ Processing..."]]}
                        ).execute()

                        with tempfile.TemporaryDirectory() as tmpdir:
                            print("   📥 Downloading...")
                            video_path = download_reel(url, tmpdir)

                            print("   🤖 Summarising with Gemini...")
                            result = summarise_with_gemini(video_path)

                        update_row(service, row, url, result)
                        print(f"   ✅ Done! [{result['label']}] {result['summary']}")

                        # Wait between reels to respect Gemini rate limits
                        time.sleep(5)

                    except Exception as e:
                        # Write error into summary cell so you can see it in the sheet
                        service.spreadsheets().values().update(
                            spreadsheetId=SPREADSHEET_ID,
                            range=f"{SHEET_NAME}!D{row}",
                            valueInputOption="USER_ENTERED",
                            body={"values": [[f"❌ Error: {str(e)[:100]}"]]}
                        ).execute()
                        print(f"   ❌ Failed: {e}")

            else:
                # Nothing to do — print a dot so you know it's alive
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] Watching... (no new reels)", end="\r")

        except Exception as e:
            print(f"\n⚠️  Watcher error: {e}")
            print("   Retrying in 30 seconds...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
