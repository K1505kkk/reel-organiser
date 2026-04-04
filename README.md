# 🎬 ReelVault — Instagram Reels Organiser Pipeline

A personal data engineering project that collects, organises, and searches Instagram Reels saved via DMs — built entirely with Python, Google Sheets API, and Gemini AI.

---

## 🧩 The Problem

I send useful Instagram Reels to my own DM account constantly — finance tips, tech tools, motivation clips. After a few months, I had **568 saved reels** with zero organisation. No labels, no summaries, no way to find anything.

I built ReelVault to solve that.

---

## 🏗️ Architecture

```
Instagram DM Export (JSON)
        │
        ▼
reel_bulk_import.py         ← parses 568 reels, auto-labels, bulk loads into Sheet
        │
        ▼
Google Sheets (ReelsOrganiser)  ← central data store
  [URL | Short ID | Label | Summary | Date | Status]
        │
        ├──▶ reel_watcher.py     ← polls sheet every 30s for new URLs
        │         │
        │         ▼
        │    yt-dlp downloads reel
        │         │
        │         ▼
        │    Gemini 2.0 Flash (video understanding)
        │         │
        │         ▼
        │    summary + label written back to sheet
        │
        └──▶ reel_search.py      ← Flask local search UI
                  │
                  ▼
           http://localhost:5000  ← search 568 reels by keyword/label
```

---

## 📁 Files

| File | What it does |
|------|-------------|
| `reel_bulk_import.py` | Parses Instagram DM export JSON, extracts all reel URLs, auto-labels from captions, bulk imports into Google Sheet |
| `reel_logger.py` | Manual pipeline — paste a URL, downloads via yt-dlp, sends to Gemini for summary, logs to sheet |
| `reel_watcher.py` | Background script that watches the Sheet for new URLs and auto-processes them without any manual input |
| `reel_search.py` | Flask web server + search UI to search all saved reels by keyword, label, or topic |

---

## ⚙️ Tech Stack

- **Python 3.12+** — core scripting
- **Google Sheets API** — data store and interface
- **yt-dlp** — Instagram Reel video downloader
- **Gemini 2.0 Flash API** — multimodal video understanding for auto-summary
- **Flask** — local search web server
- **OAuth2** — Google authentication

---

## 🚀 Setup

### 1. Clone the repo
```bash
git clone https://github.com/K1505kkk/reel-organiser.git
cd reel-organiser
```

### 2. Install dependencies
```bash
pip install yt-dlp google-genai google-auth-oauthlib google-api-python-client flask
```

### 3. Set up Google Sheets API
- Go to [console.cloud.google.com](https://console.cloud.google.com)
- Enable **Google Sheets API** and **Google Drive API**
- Create OAuth 2.0 credentials → Desktop App
- Download as `credentials.json` and place in project root

### 4. Get Gemini API key
- Go to [aistudio.google.com](https://aistudio.google.com)
- Create an API key (free tier available)

### 5. Configure each script
Open each `.py` file and fill in:
```python
GEMINI_API_KEY = "your_key_here"
SPREADSHEET_ID = "your_sheet_id_here"  # from the Sheet URL
```

---

## 📦 Usage

### Bulk import from Instagram export
```bash
# Place your message_1.json from Instagram data export in the folder
python reel_bulk_import.py
# → Imports all reels with auto-labels and captions
```

### Run background watcher (for new reels)
```bash
python reel_watcher.py
# → Paste any reel URL into column A of the Sheet
# → Summary + label appear automatically within 30 seconds
```

### Search your reels
```bash
python reel_search.py
# → Open http://localhost:5000
# → Search by keyword, filter by label
```

---

## 📊 Data Schema

| Column | Field | Description |
|--------|-------|-------------|
| A | Reel URL | Full Instagram URL |
| B | Short ID | Extracted reel identifier |
| C | Label | Auto-assigned category |
| D | Summary/Notes | Caption or Gemini-generated summary |
| E | Date Added | When the reel was saved |
| F | Status | Unwatched / Watched / Saved |

---

## 🔑 Security

- `credentials.json` and `token.json` are in `.gitignore` — never committed
- API keys are not hardcoded — fill them in locally before running
- Instagram export JSON (`message_1.json`) is excluded from version control

---

## 🗺️ Roadmap

- [ ] Semantic search using embeddings + vector database
- [ ] Analytics dashboard (reels by label, activity over time)
- [ ] Ollama integration for fully local AI summaries
- [ ] `.env` file support for cleaner config

---

## 👤 Author

**Krushna Junnarkar** — SE ENTC, Savitribai Phule Pune University  
Building systems at the intersection of data and automation.

[GitHub](https://github.com/K1505kkk)
