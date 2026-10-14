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
- **OpenAI-Compatible API Support**: Requests can use the configured OpenAI-compatible endpoint through `OPENAI_BASE_URL`.

### 3. ⚡ Active Recall & Quiz Arena
- **3D Flip Flashcards**: Active recall flashcards with question on front, answer and citation on back. Clicking "Mastered" records learning progress.
- **Knowledge Quiz**: Multi-choice quiz arena with immediate feedback, rationale explanations, and score tracking.
- **Mastery Analytics**: Real-time progress tracker measuring topic competency, study streaks, and learning events.

### 4. 📝 RAG Mock Papers & Test Yourself
- **Show Now Study Flow**: Select an indexed topic and click **Show Now** to open the cross-questioning workspace.
- **Ten Difficulty-Ordered Papers**: The RAG pipeline creates ten papers ordered from Easy through Expert using the selected topic's indexed content.
- **Random Paper Lengths**: Each paper contains a randomly assigned number of questions between 10 and 30.
- **MCQ Format**: Every generated question has four options and one validated correct answer.
- **One-Hour Attempts**: Each paper has an independent 60-minute countdown timer.
- **Progress Reports**: Submitting a paper calculates the score, answered count, percentage, completion time, and timeout status. Reports appear below the paper cards and are retained in browser local storage.

### 5. 📚 Library & Ingestion Pipeline
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

### 4. Configure Environment Variables
Create or update `.env` in the project directory:

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://aicredits.in/v1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
REDIS_URL=redis://localhost:6379/
```

The selected study material must be uploaded and ingested before chat or mock-paper
generation can retrieve RAG context.

---

## 📝 Mock Paper Workflow

1. Open the Mockuplevel web application.
2. Select an indexed topic from **Study Material**.
3. Click **Show Now** to enter the topic's cross-questioning workspace.
4. Scroll to **Test Yourself**, then click **Test Yourself** or use the top navigation tab.
5. Generate the ten papers and select a difficulty level.
6. Answer the MCQs before the 60-minute timer expires.
7. Click **Submit Paper** to view the score and update the **Progress Report** below the papers.

The mock-paper endpoint is:

```text
POST /api/v1/study/mock-papers
```

It returns ten papers, each with a `question_count`, four-option MCQs, a
`correct_index`, and a 3600-second duration.

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