#!/usr/bin/env python3
# ============================================================
#  REEL SEARCH — Flask Backend
#  Reads your Google Sheet and serves a search API
#
#  Setup:
#    pip install flask google-auth-oauthlib google-api-python-client
#
#  Usage:
#    python reel_search.py
#    Then open http://localhost:5000 in your browser
# ============================================================

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── CONFIG ───────────────────────────────────────────────────
SPREADSHEET_ID   = "https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_ID/edit?gid=446667742#gid=446667742"
SHEET_NAME       = "Reels"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

app = Flask(__name__, static_folder="static")

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


# ── LOAD ALL REELS FROM SHEET ─────────────────────────────────
def load_reels():
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F"
    ).execute()

    rows = result.get("values", [])
    reels = []

    for i, row in enumerate(rows):
        if i == 0:
            continue  # skip header
        while len(row) < 6:
            row.append("")

        reels.append({
            "url":     row[0],
            "id":      row[1],
            "label":   row[2],
            "notes":   row[3],
            "date":    row[4],
            "status":  row[5],
        })

    return reels


# ── SEARCH LOGIC ──────────────────────────────────────────────
def search_reels(reels, query, label_filter):
    query = query.lower().strip()
    results = []

    for reel in reels:
        # Label filter
        if label_filter and label_filter != "All":
            if reel["label"] != label_filter:
                continue

        # Keyword search across notes, label, id
        if query:
            searchable = f"{reel['notes']} {reel['label']} {reel['id']}".lower()
            # Support multi-word: all words must match
            if not all(word in searchable for word in query.split()):
                continue

        results.append(reel)

    return results


# ── ROUTES ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search")
def api_search():
    query       = request.args.get("q", "")
    label       = request.args.get("label", "All")
    page        = int(request.args.get("page", 1))
    per_page    = 20

    try:
        reels   = load_reels()
        results = search_reels(reels, query, label)

        # Pagination
        total   = len(results)
        start   = (page - 1) * per_page
        end     = start + per_page
        page_results = results[start:end]

        return jsonify({
            "results": page_results,
            "total": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    try:
        reels = load_reels()
        label_counts = {}
        status_counts = {}

        for r in reels:
            label_counts[r["label"]] = label_counts.get(r["label"], 0) + 1
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

        return jsonify({
            "total": len(reels),
            "by_label": label_counts,
            "by_status": status_counts
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n🔍 REEL SEARCH — starting server...")
    print("   Open http://localhost:5000 in your browser\n")
    app.run(debug=False, port=5000)
