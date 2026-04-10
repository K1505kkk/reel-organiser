# 🎬 ReelVault — Instagram Reels Organiser Pipeline

A personal data engineering project that collects, organises, summarises, and searches 568+ Instagram Reels saved via DMs — built with Python, Google Sheets API, Whisper, Ollama, and Flask.

---

## 🧩 The Problem

I forward useful Instagram Reels to my own DM account constantly — finance tips, tech tools, motivation clips. After a few months I had **568 saved reels** with zero organisation. No labels, no summaries, no way to find anything.

I built ReelVault to solve that — end to end.

---

## 🏗️ Architecture

```
Instagram DM Export (JSON)
        │
        ▼
reel_bulk_import.py       ← parses 568 reels, auto-labels, bulk loads into Sheet
        │
        ▼
Google Sheets (ReelsOrganiser)
  [URL | Short ID | Label | Summary | Date | Status]
        │
        ├──▶ reel_watcher.py (V2)     ← polls sheet every 30s for new URLs
        │         │
        │         ├── yt-dlp downloads reel
        │         ├── Whisper tiny transcribes audio (local CPU)
        │         └── Ollama gemma2:2b writes clean summary → sheet
        │
        ├──▶ reel_summariser.py       ← batch reprocessor (RTX 3060, LLaVA + Gemma3)
        │         │
        │         ├── SP1: yt-dlp → ffmpeg frames → LLaVA vision description
        │         ├── SP1c: ffmpeg audio → Whisper transcription
        │         └── SP2: Gemma3 12B → clean topic-first summary → sheet
        │
        ├──▶ reel_search.py           ← Flask search UI (localhost:5000)
        │         └── keyword + label filter across 568 reels
        │
        └──▶ reel_analytics.py        ← Flask analytics dashboard (localhost:5001)
                  └── label distribution, monthly timeline, status breakdown
```

---

## 📁 Files

| File | What it does |
|------|-------------|
| `reel_bulk_import.py` | Parses Instagram DM export JSON, auto-labels from captions, bulk imports into Sheet |
| `reel_logger.py` | Manual paste pipeline — URL → download → summary → sheet |
| `reel_watcher.py` | V2 background watcher — Whisper + Ollama gemma2b for daily use on laptop |
| `reel_summariser.py` | Batch reprocessor — full E pipeline (LLaVA + Whisper + Gemma3) for friend's RTX 3060 |
| `reel_search.py` | Flask search server — keyword + label filter UI |
| `reel_analytics.py` | Flask analytics dashboard — charts from sheet data |
| `static/index.html` | Search frontend |
| `templates/analytics.html` | Analytics frontend |

---

## ⚙️ Tech Stack

- **Python 3.12+**
- **Google Sheets API** — central data store
- **yt-dlp** — Instagram Reel downloader + metadata extraction
- **Whisper (tiny/base)** — local audio transcription (OpenAI, runs on CPU)
- **Ollama + gemma2:2b** — local LLM for daily summaries (laptop)
- **Ollama + LLaVA + Gemma3:12b** — full vision pipeline (RTX 3060)
- **Flask** — local search + analytics web servers
- **Matplotlib + Pandas** — analytics charts
- **OAuth2** — Google authentication

---

## 🚀 Setup

### 1. Clone
```bash
git clone https://github.com/K1505kkk/reel-organiser.git
cd reel-organiser
```

### 2. Install dependencies
```bash
pip install yt-dlp openai-whisper google-auth-oauthlib google-api-python-client flask pandas matplotlib
ollama pull gemma2:2b
winget install ffmpeg
```

### 3. Google Sheets API
- console.cloud.google.com → enable Sheets + Drive API
- Create OAuth 2.0 credentials → Desktop App → download as `credentials.json`

### 4. Configure
In each script, set:
```python
SPREADSHEET_ID = "your_sheet_id_here"
```

---

## 📦 Usage

### Bulk import backlog
```bash
python reel_bulk_import.py
```

### Watch for new reels (V2 — daily use)
```bash
python reel_watcher.py
# Paste any reel URL into column A → summary appears in ~30s
```

### Batch reprocess with full pipeline (RTX 3060)
```bash
python reel_summariser.py
```

### Search UI
```bash
python reel_search.py
# Open http://localhost:5000
```

### Analytics dashboard
```bash
python reel_analytics.py
# Open http://localhost:5001
```

---

## 📊 Data Schema

| Column | Field | Description |
|--------|-------|-------------|
| A | Reel URL | Full Instagram URL |
| B | Short ID | Extracted reel identifier |
| C | Label | Auto-assigned category |
| D | Summary | Clean topic-first summary (max 20 words) |
| E | Date Added | When the reel was saved |
| F | Status | Unwatched / Watched / Saved |

---

## 🗺️ Roadmap

- [ ] Semantic search — ChromaDB embeddings
- [ ] SP3 embeddings pipeline
- [ ] Deploy Flask apps to free hosting (Render/Railway)
- [ ] Mobile share sheet integration

---

## 🔑 Security
- `credentials.json`, `token.json`, `.env` — never committed (in `.gitignore`)
- API keys stored in `.env` only

---

## 👤 Author
**Krushna Junnarkar** — Data Analytics | Automation | Local AI  
[GitHub](https://github.com/K1505kkk)
