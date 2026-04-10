#!/usr/bin/env python3
# ============================================================
#  REEL WATCHER V2 — Whisper + Ollama gemma2b
#  Setup:
#    pip install yt-dlp openai-whisper google-auth-oauthlib google-api-python-client
#    ollama pull gemma2:2b
#    winget install ffmpeg
#  Usage: python reel_watcher.py
# ============================================================

import os
import re
import json
import time
import tempfile
import subprocess
from datetime import datetime

import yt_dlp
import ollama
import whisper
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── CONFIG ───────────────────────────────────────────────────
SPREADSHEET_ID   = "1344SzsRrl6jBYey6EHIiGYUiD-JC-okLocsuUdgEeUs"
SHEET_NAME       = "Reels"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"
POLL_INTERVAL    = 30
WHISPER_MODEL    = "tiny"
SUMMARY_MODEL    = "gemma2:2b"

LABEL_LIST = ["Finance","Tech","Motivation","Business","Health","Entertainment","Learning","Other"]

COL_URL   = 1
COL_ID    = 2
COL_LABEL = 3
COL_NOTES = 4
COL_DATE  = 5
COL_STATUS= 6

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

print("⏳ Loading Whisper tiny...")
WHISPER = whisper.load_model(WHISPER_MODEL)
print("✅ Whisper ready\n")


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


# ── GET UNPROCESSED ROWS ──────────────────────────────────────
def get_unprocessed_rows(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F"
    ).execute()
    rows = result.get("values", [])
    unprocessed = []
    for i, row in enumerate(rows):
        if i == 0: continue
        while len(row) < 6: row.append("")
        url   = row[COL_URL - 1].strip()
        notes = row[COL_NOTES - 1].strip()
        if url and not notes:
            unprocessed.append({
                "row_index": i + 1,
                "url":       url,
                "label":     row[COL_LABEL - 1]
            })
    return unprocessed


# ── URL CLEANER ───────────────────────────────────────────────
def clean_reel_url(url):
    match = re.search(r"(https://www\.instagram\.com/reel/[A-Za-z0-9_-]+/)", url)
    return match.group(1) if match else url

def extract_reel_id(url):
    match = re.search(r"/reel(?:s)?/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else "unknown"


# ── DOWNLOAD ──────────────────────────────────────────────────
def download_reel(url, output_dir):
    ydl_opts = {
        "outtmpl":     os.path.join(output_dir, "reel.%(ext)s"),
        "format":      "mp4/best[ext=mp4]/best",
        "quiet":       True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info     = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        base     = os.path.splitext(filename)[0]
        mp4_path = base + ".mp4"
        if not os.path.exists(mp4_path):
            for f in os.listdir(output_dir):
                if f.startswith("reel"):
                    mp4_path = os.path.join(output_dir, f)
                    break
        metadata = {
            "uploader":    info.get("uploader", "") or "",
            "description": info.get("description", "") or "",
        }
    return mp4_path, metadata


# ── WHISPER TRANSCRIPTION ─────────────────────────────────────
def transcribe_audio(video_path, output_dir):
    audio_path = os.path.join(output_dir, "audio.wav")
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le",
        audio_path, "-y", "-loglevel", "error"
    ], capture_output=True)
    if not os.path.exists(audio_path):
        return ""
    result = WHISPER.transcribe(audio_path, fp16=False)
    transcript = result.get("text", "").strip()
    return transcript if len(transcript) > 10 else ""


# ── OLLAMA SUMMARY ────────────────────────────────────────────
def summarise_with_ollama(profile, transcript, raw_caption, existing_label):
    clean_caption = re.sub(r"#\w+", "", raw_caption)
    clean_caption = re.sub(r"\s+", " ", clean_caption).strip()[:300]
    transcript    = transcript[:600]

    prompt = f"""You are building a searchable knowledge base of Instagram Reels.

Posted by: {profile or "Unknown"}
Transcript: {transcript or "No speech detected"}
Caption: {clean_caption or "No caption"}
Category: {existing_label or "Unknown"}

Respond ONLY with a JSON object, no extra text, no markdown:
{{"summary": "One sentence starting with the subject. Max 20 words. Never start with This/The/A/An/This reel/This video.", "label": "Pick one: {'/'.join(LABEL_LIST)}"}}

Good: "NVIDIA offers 200+ free AI API keys with no credit card required"
Bad: "This reel shows someone explaining NVIDIA tools" """

    response = ollama.chat(
        model=SUMMARY_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response["message"]["content"].strip().replace("```json","").replace("```","").strip()

    try:
        result  = json.loads(raw)
        summary = result.get("summary", "").strip()
        label   = result.get("label", existing_label or "Other").strip()
    except Exception:
        # If JSON parse fails, use raw text as summary
        summary = raw[:100]
        label   = existing_label or "Other"

    # Clean up
    summary = re.sub(
        r"^(Summary:|This reel|This video|This Instagram|The reel)[:\s]*",
        "", summary, flags=re.IGNORECASE
    ).strip()
    if summary:
        summary = summary[0].upper() + summary[1:]

    return summary, label


# ── WRITE TO SHEET ────────────────────────────────────────────
def update_row(service, row_index, url, summary, label):
    short_id = extract_reel_id(url)
    date_str = datetime.now().strftime("%d %b %Y")
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{row_index}:F{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[url, short_id, label, summary, date_str, "Unwatched"]]}
    ).execute()

def write_notes(service, row_index, text):
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!D{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[text]]}
    ).execute()


# ── MAIN LOOP ─────────────────────────────────────────────────
def main():
    print("\n👁️  REEL WATCHER V2")
    print(f"   Whisper:  {WHISPER_MODEL} (CPU)")
    print(f"   Summary:  Ollama {SUMMARY_MODEL}")
    print(f"   Polling:  every {POLL_INTERVAL}s")
    print("   Paste URLs into column A. Ctrl+C to stop.\n")

    service = get_sheets_service()
    print("✅ Connected to Google Sheets\n")

    while True:
        try:
            pending = get_unprocessed_rows(service)
            if pending:
                print(f"🔍 Found {len(pending)} new reel(s)...")
                for item in pending:
                    url            = item["url"]
                    row            = item["row_index"]
                    existing_label = item["label"]
                    print(f"\n▶ Row {row}: {url[:60]}...")
                    try:
                        write_notes(service, row, "⏳ Processing...")
                        with tempfile.TemporaryDirectory() as tmpdir:
                            print("   📥 Downloading...")
                            video_path, metadata = download_reel(clean_reel_url(url), tmpdir)
                            profile = metadata.get("uploader", "")
                            if profile: print(f"   👤 {profile}")

                            print("   🎙️  Transcribing (Whisper)...")
                            transcript = transcribe_audio(video_path, tmpdir)
                            if transcript:
                                print(f"   ✅ {transcript[:60]}...")
                            else:
                                print("   ⚠️  No speech detected")

                        print("   🤖 Summarising (Ollama)...")
                        summary, label = summarise_with_ollama(
                            profile, transcript,
                            metadata.get("description", ""),
                            existing_label
                        )
                        print(f"   ✅ [{label}] {summary}")
                        update_row(service, row, url, summary, label)
                        print("   📝 Saved")
                        time.sleep(5)

                    except Exception as e:
                        write_notes(service, row, f"❌ Error: {str(e)[:100]}")
                        print(f"   ❌ Failed: {e}")
            else:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] Watching...", end="\r")

        except Exception as e:
            print(f"\n⚠️  Error: {e} — retrying in 30s...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()