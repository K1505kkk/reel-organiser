#!/usr/bin/env python3
# ============================================================
#  REEL ANALYTICS — Flask Dashboard
#  Usage: python reel_analytics.py
#  Open: http://localhost:5001
# ============================================================

import os
import io
import base64
from collections import Counter
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, render_template
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SPREADSHEET_ID   = "1344SzsRrl6jBYey6EHIiGYUiD-JC-okLocsuUdgEeUs"
SHEET_NAME       = "Reels"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

app = Flask(__name__)

DARK_BG    = "#0a0a0a"
SURFACE    = "#181818"
ACCENT     = "#ff5c3a"
ACCENT2    = "#ffb23a"
TEXT       = "#efefef"
MUTED      = "#555555"


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


def load_data():
    service = get_sheets_service()
    result  = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:F"
    ).execute()
    rows = result.get("values", [])[1:]  # skip header
    data = []
    for row in rows:
        while len(row) < 6: row.append("")
        data.append({
            "url":    row[0],
            "id":     row[1],
            "label":  row[2] or "Other",
            "notes":  row[3],
            "date":   row[4],
            "status": row[5] or "Unwatched"
        })
    return data


def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return img


def chart_labels(data):
    counts = Counter(r["label"] for r in data)
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [ACCENT, ACCENT2, "#3affa0", "#7ab8ff", "#ff7ab8",
              "#b87aff", "#ffda7a", MUTED][:len(labels)]

    fig, ax = plt.subplots(figsize=(8, 4), facecolor=DARK_BG)
    bars = ax.barh(labels, values, color=colors)
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=TEXT)
    ax.spines[:].set_color(MUTED)
    ax.set_xlabel("Reels", color=TEXT)
    ax.set_title("Reels by Label", color=TEXT, fontsize=14, pad=12)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                str(val), va="center", color=TEXT, fontsize=9)
    fig.tight_layout()
    return fig_to_base64(fig)


def chart_timeline(data):
    dates = []
    for r in data:
        try:
            dates.append(datetime.strptime(r["date"], "%d %b %Y"))
        except Exception:
            pass

    if not dates:
        return None

    df = pd.DataFrame({"date": dates})
    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month").size()

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=DARK_BG)
    ax.plot(monthly.index.astype(str), monthly.values,
            color=ACCENT, linewidth=2, marker="o", markersize=5)
    ax.fill_between(range(len(monthly)), monthly.values,
                    alpha=0.15, color=ACCENT)
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=TEXT, labelrotation=45)
    ax.spines[:].set_color(MUTED)
    ax.set_ylabel("Reels saved", color=TEXT)
    ax.set_title("Reels Saved per Month", color=TEXT, fontsize=14, pad=12)
    fig.tight_layout()
    return fig_to_base64(fig)


def chart_status(data):
    counts = Counter(r["status"] for r in data)
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [ACCENT2, ACCENT, "#3affa0"][:len(labels)]

    fig, ax = plt.subplots(figsize=(5, 5), facecolor=DARK_BG)
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"color": TEXT}
    )
    for a in autotexts: a.set_color(DARK_BG)
    ax.set_title("Status Breakdown", color=TEXT, fontsize=14, pad=12)
    return fig_to_base64(fig)


@app.route("/")
def index():
    data        = load_data()
    total       = len(data)
    top_label   = Counter(r["label"] for r in data).most_common(1)[0][0]
    unwatched   = sum(1 for r in data if r["status"] == "Unwatched")

    img_labels   = chart_labels(data)
    img_timeline = chart_timeline(data)
    img_status   = chart_status(data)

    return render_template("analytics.html",
        total=total, top_label=top_label, unwatched=unwatched,
        img_labels=img_labels,
        img_timeline=img_timeline,
        img_status=img_status
    )


if __name__ == "__main__":
    print("\n📊 REEL ANALYTICS — starting on http://localhost:5001\n")
    app.run(debug=False, port=5001)
