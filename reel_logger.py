#!/usr/bin/env python3
# ============================================================
#  REEL LOGGER PIPELINE
#  URL → yt-dlp download → Gemini summary + label → Google Sheets
#
#  Setup:
#    pip install yt-dlp google-genai google-auth-oauthlib google-api-python-client
#
#  Usage:
#    python reel_logger.py
# ============================================================

import os
import json
import time
import tempfile
import yt_dlp
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── CONFIG — edit these ──────────────────────────────────────
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
SPREADSHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"  # from your sheet URL
SHEET_NAME     = "Reels"
CREDENTIALS_FILE = "credentials.json"  # same folder as this script
TOKEN_FILE       = "token.json"        # auto-created on first run

LABEL_LIST = [
    "Finance", "Tech", "Motivation", "Business",
    "Health", "Entertainment", "Learning", "Other"
]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── 1. GOOGLE SHEETS AUTH ────────────────────────────────────
def get_sheets_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


# ── 2. DOWNLOAD REEL WITH yt-dlp ─────────────────────────────
def download_reel(url, output_dir):
    print("📥 Downloading reel...")
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "reel.%(ext)s"),
        "format": "mp4/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # ensure .mp4 extension
        base = os.path.splitext(filename)[0]
        mp4_path = base + ".mp4"
        if not os.path.exists(mp4_path):
            # fallback: find whatever was downloaded
            for f in os.listdir(output_dir):
                if f.startswith("reel"):
                    mp4_path = os.path.join(output_dir, f)
                    break
    print(f"✅ Downloaded: {mp4_path}")
    return mp4_path


# ── 3. UPLOAD TO GEMINI FILE API + SUMMARISE ─────────────────
def summarise_with_gemini(video_path):
    print("🤖 Sending to Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Upload video file
    print("   📤 Uploading video...")
    with open(video_path, "rb") as f:
        video_file = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type="video/mp4")
        )

    # Wait for processing
    while video_file.state.name == "PROCESSING":
        print("   ⏳ Gemini processing video...")
        time.sleep(3)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Gemini failed to process the video.")

    prompt = f"""Watch this Instagram Reel and respond ONLY with a JSON object. No extra text.

{{
  "summary": "One sentence describing what this reel is about",
  "label": "Pick exactly one from: {', '.join(LABEL_LIST)}"
}}"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[video_file, prompt]
    )

    # Clean and parse response
    raw = response.text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)

    # Delete file from Gemini after use
    client.files.delete(name=video_file.name)

    print(f"✅ Summary: {result['summary']}")
    print(f"✅ Label:   {result['label']}")
    return result


# ── 4. EXTRACT REEL SHORT ID ─────────────────────────────────
def extract_reel_id(url):
    import re
    match = re.search(r"/reel(?:s)?/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else "unknown"


# ── 5. LOG TO GOOGLE SHEETS ──────────────────────────────────
def log_to_sheet(service, url, short_id, label, summary):
    from datetime import datetime
    date_str = datetime.now().strftime("%d %b %Y")
    row = [url, short_id, label, summary, date_str, "Unwatched"]

    body = {"values": [row]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    print("✅ Logged to Google Sheet!")


# ── MAIN PIPELINE ─────────────────────────────────────────────
def main():
    print("\n🎬 REEL LOGGER — paste URL below (or 'q' to quit)\n")
    sheets_service = get_sheets_service()

    while True:
        url = input("Reel URL: ").strip()
        if url.lower() == "q":
            print("👋 Bye!")
            break
        if not url:
            continue

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Step 1: Download
                video_path = download_reel(url, tmpdir)

                # Step 2: Summarise
                result = summarise_with_gemini(video_path)

            # Step 3: Log
            short_id = extract_reel_id(url)
            log_to_sheet(
                sheets_service,
                url,
                short_id,
                result["label"],
                result["summary"]
            )

            print(f"\n🔥 Done! '{result['summary']}' logged as [{result['label']}]\n")

        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            print("Tip: Make sure the reel is public and the URL is correct.\n")


if __name__ == "__main__":
    main()
