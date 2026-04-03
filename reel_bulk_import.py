#!/usr/bin/env python3
# ============================================================
#  REEL BULK IMPORTER
#  Parses your Instagram DM export JSON and bulk-loads all
#  reel URLs + captions into your Google Sheet.
#
#  No Gemini needed — uses the reel caption as the summary.
#
#  Usage:
#    python reel_bulk_import.py
# ============================================================

import os
import json
import time
import re
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── CONFIG — edit these ──────────────────────────────────────
SPREADSHEET_ID   = "YOUR_GOOGLE_SHEET_ID_HERE"
JSON_FILE        = "message_1.json"   # put this in same folder as script
SHEET_NAME       = "Reels"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── Label keywords — auto-assigns label from caption text ────
LABEL_KEYWORDS = {
    "Finance":       ["money", "invest", "stock", "crypto", "wealth", "finance", "income", "profit", "trading"],
    "Tech":          ["ai", "api", "code", "python", "software", "app", "github", "developer", "programming", "tool", "model", "llm", "gpt", "nvidia", "chromium", "browser"],
    "Motivation":    ["mindset", "success", "grind", "hustle", "discipline", "goal", "habits", "motivation", "inspire"],
    "Business":      ["startup", "business", "entrepreneur", "saas", "product", "revenue", "founder", "marketing"],
    "Health":        ["health", "fitness", "workout", "diet", "nutrition", "gym", "sleep", "mental"],
    "Entertainment": ["funny", "prank", "meme", "comedy", "cute", "dog", "cat", "viral", "fun"],
    "Learning":      ["learn", "study", "course", "skill", "tutorial", "tips", "how to", "guide", "education"],
}
DEFAULT_LABEL = "Other"


# ── AUTH ─────────────────────────────────────────────────────
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
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


# ── EXTRACT REEL ID FROM URL ─────────────────────────────────
def extract_reel_id(url):
    match = re.search(r"/reel(?:s)?/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else "unknown"


# ── AUTO-LABEL FROM CAPTION ──────────────────────────────────
def guess_label(caption):
    caption_lower = caption.lower()
    for label, keywords in LABEL_KEYWORDS.items():
        if any(kw in caption_lower for kw in keywords):
            return label
    return DEFAULT_LABEL


# ── CLEAN CAPTION — strip hashtags, trim length ──────────────
def clean_caption(text):
    # Remove hashtags
    text = re.sub(r"#\w+", "", text)
    # Fix weird unicode chars from Instagram export
    text = text.encode("raw_unicode_escape").decode("utf-8", errors="replace")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Trim to 200 chars for sheet readability
    if len(text) > 200:
        text = text[:197] + "..."
    return text


# ── PARSE JSON FOR REEL LINKS ────────────────────────────────
def parse_reels(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    reels = []
    seen_urls = set()

    for msg in messages:
        share = msg.get("share", {})
        link = share.get("link", "")

        # Only grab Instagram reel links
        if "instagram.com/reel" not in link:
            continue

        # Skip duplicates
        if link in seen_urls:
            continue
        seen_urls.add(link)

        caption = clean_caption(share.get("share_text", ""))
        owner   = share.get("original_content_owner", "")
        ts      = msg.get("timestamp_ms", 0)
        date    = datetime.fromtimestamp(ts / 1000).strftime("%d %b %Y")
        label   = guess_label(caption)
        short_id = extract_reel_id(link)

        reels.append([
            link,        # A: URL
            short_id,    # B: Short ID
            label,       # C: Label (auto-guessed)
            caption,     # D: Summary/Notes (caption text)
            date,        # E: Date sent
            "Unwatched"  # F: Status
        ])

    return reels


# ── GET EXISTING URLS TO AVOID DUPLICATES ───────────────────
def get_existing_urls(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:A"
    ).execute()
    rows = result.get("values", [])
    return set(row[0] for row in rows if row)


# ── BATCH WRITE TO SHEET ─────────────────────────────────────
def write_to_sheet(service, rows):
    if not rows:
        print("Nothing to write.")
        return

    body = {"values": rows}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()


# ── MAIN ─────────────────────────────────────────────────────
def main():
    print("\n📦 REEL BULK IMPORTER")
    print(f"   Reading: {JSON_FILE}\n")

    # Parse all reels from JSON
    print("🔍 Parsing reels from DM export...")
    all_reels = parse_reels(JSON_FILE)
    print(f"   Found {len(all_reels)} unique reels in export")

    if not all_reels:
        print("❌ No reels found. Check your JSON file path.")
        return

    # Connect to sheets
    print("\n🔗 Connecting to Google Sheets...")
    service = get_sheets_service()

    # Check for existing URLs to avoid duplicates
    print("   Checking for existing entries...")
    existing = get_existing_urls(service)
    print(f"   {len(existing)} rows already in sheet")

    # Filter out already-imported reels
    new_reels = [r for r in all_reels if r[0] not in existing]
    skipped = len(all_reels) - len(new_reels)

    print(f"   {skipped} skipped (already in sheet)")
    print(f"   {len(new_reels)} new reels to import")

    if not new_reels:
        print("\n✅ Sheet is already up to date!")
        return

    # Write in batches of 100 to avoid API limits
    print(f"\n📝 Writing {len(new_reels)} reels to sheet...")
    batch_size = 100
    for i in range(0, len(new_reels), batch_size):
        batch = new_reels[i:i + batch_size]
        write_to_sheet(service, batch)
        print(f"   ✅ Batch {i//batch_size + 1}: wrote {len(batch)} rows")
        time.sleep(1)  # small pause between batches

    print(f"\n🔥 Done! {len(new_reels)} reels imported into your sheet.")
    print("   Labels were auto-guessed from captions — review column C and fix any that are wrong.")


if __name__ == "__main__":
    main()
