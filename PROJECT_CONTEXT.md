# ReelVault — Project Context

## What it is
A personal data pipeline that organises 568 Instagram Reels saved via DMs into a searchable Google Sheet.

## Stack
- Python 3.12, Windows
- Google Sheets API (data store)
- yt-dlp (reel downloader)
- Whisper tiny (local audio transcription, CPU)
- Ollama + gemma2b (local summary, CPU-friendly)
- Flask (search UI — V3)
- Git/GitHub (version control)

## Sheet Schema
| Col | Field | Notes |
|-----|-------|-------|
| A | Reel URL | Full Instagram URL |
| B | Short ID | Extracted reel ID |
| C | Label | Finance/Tech/Motivation/Business/Health/Entertainment/Learning/Other |
| D | Notes/Summary | Clean 1-line summary — topic-first, max 20 words |
| E | Date Added | dd MMM yyyy |
| F | Status | Unwatched/Watched/Saved |

## Sheet ID
`1344SzsRrl6jBYey6EHIiGYUiD-JC-okLocsuUdgEeUs`

## Files
- `reel_bulk_import.py` — bulk imports Instagram DM export JSON
- `reel_logger.py` — manual URL → download → Gemini → sheet
- `reel_watcher.py` — polls sheet every 30s, processes new URLs automatically
- `reel_summariser.py` — batch reprocesses existing rows (friend's RTX 3060)
- `reel_search.py` — Flask local search UI (V3, WIP)
- `static/index.html` — search frontend

## V2 Pipeline (current)
```
URL in Sheet → yt-dlp download → Whisper tiny transcription
→ Ollama gemma2b summary → written back to sheet
```

## V3 Plan
- Analytics dashboard (label distribution, activity over time)
- Search UI (keyword + label filter, Flask local server)
- Semantic search (ChromaDB embeddings — future)

## Summary Prompt Rules
- Start with subject directly (no "This reel", "This video")
- Max 20 words
- Name actual topic/tool/concept
- No hashtags, emojis, URLs

## GitHub
https://github.com/K1505kkk/reel-organiser

## Credentials
- `credentials.json` — Google OAuth (never commit)
- `token.json` — auto-generated auth token (never commit)
- `.env` — contains GEMINI_API_KEY (never commit)

## Hardware
- Main laptop: i5-7200U, 8GB RAM, no GPU
- Friend's PC: RTX 3060 12GB (for batch processing)
