# Mockuplevel - Multimodal Study Companion

An intelligent, multimodal paired study companion and active-recall platform. Mockuplevel synchronizes lecture video playback, speech-to-text transcripts, visual keyframe slide decks, and OCR-extracted document knowledge bases with an AI-powered conversational study companion featuring exact timestamp citations.

---

## 🚀 Key Features

### 1. 🎓 Central Study Hub
- **Interactive Video Player**: HTML5 video streaming directly from Supabase Storage or local uploads with playback speed, +/- 10s skip, and live timestamp tracker.
- **Synchronized Live Transcript**: Transcribed via faster-whisper. The active sentence auto-highlights and auto-scrolls in sync with playback. Clicking any timestamp jumps the video directly to that second!
- **Keyframe Slide Deck**: Visual slide thumbnails extracted every 10 seconds via FFmpeg. Clicking a frame seeks the video to that moment.
- **Document & OCR Notes**: Extracted PDF pages and scanned document notes using PyMuPDF and OCR.

### 2. 🤖 AI Study Companion (RAG with Citations)
- **Time-Stamped Citations**: Every answer references exact lecture moments (e.g., `[00:15]`) and document pages (`[Page 2]`). Clicking any citation chip instantly seeks the video player!
- **Markdown & Math Rendering**: Supports KaTeX math formulas, code syntax highlighting, bullet points, and key concept takeaways.
- **Resilient Fallback Mode**: If the OpenAI key is unset or unmetered, semantic context synthesis continues to function from indexed chunks with zero crashes.

### 3. ⚡ Active Recall & Quiz Arena
- **3D Flip Flashcards**: Active recall flashcards with question on front, answer and citation on back. Clicking "Mastered" records learning progress.
- **Knowledge Quiz**: Multi-choice quiz arena with immediate feedback, rationale explanations, and score tracking.
- **Mastery Analytics**: Real-time progress tracker measuring topic competency, study streaks, and learning events.

### 4. 📚 Library & Ingestion Pipeline
- **Supabase Storage Browser**: One-click ingestion from Supabase storage buckets (`Mockvdo`, `document`).
- **Drag-and-Drop Uploader**: Direct upload for MP4, MKV, MOV videos and PDF or image documents with background processing.
- **Live Pipeline Tracker**: Visual progress modal tracking audio extraction, speech transcription, keyframe generation, and vector embedding.

---

## 🛠️ Quickstart & Running the Application

### 1. Sync Dependencies
```bash
uv sync
```

### 2. Start the Frontend & API Server
From the project directory (`Mockuplevel`):
```bash
uvicorn src.main:app --reload --port 8000
```

### 3. Open in Browser
Open: [http://localhost:8000](http://localhost:8000)

---

## 📂 Project Structure

```
Mockuplevel/
├── src/
│   ├── main.py              # FastAPI application & API endpoints
│   ├── config.py            # Environment configuration (.env loader)
│   ├── db/
│   │   ├── storage.py       # Supabase Storage helpers
│   │   └── vector_store.py  # Supabase pgvector operations & resilient search
│   ├── pipeline/
│   │   ├── video_processor.py # FFmpeg audio extraction & Whisper transcription
│   │   ├── doc_processor.py   # PyMuPDF text & Tesseract OCR extraction
│   │   └── chunker.py         # Embedding generation & text chunker
│   └── tasks/
│       └── celery_worker.py # Celery asynchronous background tasks
├── static/
│   ├── index.html           # Main Single Page Application (SPA) frontend
│   ├── css/
│   │   └── style.css        # Dark mode glassmorphic styling & 3D card flips
│   ├── js/
│   │   └── app.js           # Frontend reactive state & video sync logic
│   └── keyframes/           # Extracted visual slide frames
├── .env                     # Supabase & OpenAI API credentials
├── pyproject.toml           # uv project configuration
└── commands.txt             # Setup & execution commands
```