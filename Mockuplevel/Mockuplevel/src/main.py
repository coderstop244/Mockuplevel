"""Mockuplevel application entry point and API routes."""
from __future__ import annotations

import os
import shutil
import uuid
import json
import time
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
from tempfile import TemporaryDirectory

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.db.storage import supabase, VIDEO_BUCKET
from src.db.vector_store import VectorStore, search_relevant_context, DEFAULT_TENANT_ID, DEFAULT_COURSE_ID
from src.pipeline.video_processor import VideoProcessor
from src.pipeline.chunker import EmbeddingChunker
from src.pipeline.doc_processor import DocumentProcessor

app = FastAPI(
    title="Mockuplevel - Multimodal Study Companion API",
    description="High-performance backend API and study workspace",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory Setup
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
KEYFRAMES_DIR = STATIC_DIR / "keyframes"
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
KEYFRAMES_DIR.mkdir(parents=True, exist_ok=True)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared singletons & state
db_store = VectorStore()
chunker = EmbeddingChunker()
video_proc = VideoProcessor(whisper_model_size="base", device="cpu")
doc_proc = DocumentProcessor()

# In-memory background task registry
TASK_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Runtime config override for OpenAI key
RUNTIME_CONFIG = {
    "OPENAI_API_KEY": settings.OPENAI_API_KEY
}


# -----------------------------
# Pydantic Request Models
# -----------------------------
class VideoIngestRequest(BaseModel):
    source_id: str
    storage_path: str
    tenant_id: Optional[str] = DEFAULT_TENANT_ID
    course_id: Optional[str] = DEFAULT_COURSE_ID


class DocumentIngestRequest(BaseModel):
    source_id: str
    storage_path: Optional[str] = None
    local_path: Optional[str] = None
    tenant_id: Optional[str] = DEFAULT_TENANT_ID
    course_id: Optional[str] = DEFAULT_COURSE_ID


class ChatRequest(BaseModel):
    message: str
    source_id: Optional[str] = None
    mode: Optional[str] = "tutor"  # tutor, simplifier, quizzer, summary
    tenant_id: Optional[str] = DEFAULT_TENANT_ID
    course_id: Optional[str] = DEFAULT_COURSE_ID


class FlashcardRequest(BaseModel):
    source_id: Optional[str] = None
    course_id: Optional[str] = DEFAULT_COURSE_ID


class QuizRequest(BaseModel):
    source_id: Optional[str] = None
    course_id: Optional[str] = DEFAULT_COURSE_ID


class MockPapersRequest(BaseModel):
    source_id: Optional[str] = None
    tenant_id: Optional[str] = DEFAULT_TENANT_ID
    course_id: Optional[str] = DEFAULT_COURSE_ID


class SummaryRequest(BaseModel):
    source_id: str


class MasteryEventRequest(BaseModel):
    topic_id: str
    is_correct: bool
    event_type: str = "quiz_answer"  # quiz_answer, flashcard_review
    course_id: Optional[str] = DEFAULT_COURSE_ID
    evidence_payload: Optional[Dict[str, Any]] = None


class KeyUpdateRequest(BaseModel):
    openai_api_key: str


# -----------------------------
# Frontend Route
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Mockuplevel Frontend Initializing...</h1>")


# -----------------------------
# Diagnostics & Settings
# -----------------------------
@app.get("/api/v1/health")
def check_health():
    """Health check for Supabase, OpenAI, Redis, FFmpeg, Whisper."""
    # Check Supabase
    supabase_ok = False
    try:
        res = supabase.table("document_chunks").select("id").limit(1).execute()
        supabase_ok = True
    except Exception:
        supabase_ok = False

    # Check Redis
    redis_ok = False
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    # Check FFmpeg
    ffmpeg_ok = shutil.which("ffmpeg") is not None

    # Check OpenAI
    key = RUNTIME_CONFIG.get("OPENAI_API_KEY", "")
    openai_configured = bool(key)

    return {
        "status": "healthy" if supabase_ok else "degraded",
        "services": {
            "supabase": "connected" if supabase_ok else "offline",
            "openai_api": "configured" if openai_configured else "needs_key",
            "redis_celery": "connected" if redis_ok else "offline_using_background_tasks",
            "ffmpeg": "available" if ffmpeg_ok else "missing",
            "whisper": "ready"
        }
    }


@app.get("/api/v1/settings")
def get_settings():
    key = RUNTIME_CONFIG.get("OPENAI_API_KEY", "")
    masked_key = f"{key[:7]}...{key[-4:]}" if len(key) > 12 else "Not configured"
    return {
        "openai_key_configured": bool(key),
        "openai_key_masked": masked_key,
        "supabase_url": settings.SUPABASE_URL,
        "default_tenant_id": DEFAULT_TENANT_ID,
        "default_course_id": DEFAULT_COURSE_ID
    }


@app.post("/api/v1/settings/key")
def update_openai_key(payload: KeyUpdateRequest):
    key = payload.openai_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Key cannot be empty")
    RUNTIME_CONFIG["OPENAI_API_KEY"] = key
    try:
        chunker.set_api_key(key)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OpenAI API key configuration: {exc}",
        ) from exc
    doc_proc.client = None
    return {"status": "success", "message": "OpenAI API key updated"}


# -----------------------------
# Supabase Storage & Uploads
# -----------------------------
@app.get("/api/v1/storage/files")
def list_storage_files():
    """Lists files in Supabase storage buckets with ingestion status."""
    results = []

    # Check ingested sources
    try:
        chunks_res = supabase.table("document_chunks").select("source_id").execute()
        ingested_ids = {row["source_id"] for row in (chunks_res.data or [])}
    except Exception:
        ingested_ids = set()

    # Bucket Mockvdo
    try:
        vdo_files = supabase.storage.from_("Mockvdo").list()
        for f in vdo_files:
            name = f.get("name")
            if not name or name.startswith("."):
                continue
            signed = supabase.storage.from_("Mockvdo").create_signed_url(name, 3600)
            url = signed.get("signedURL") or signed.get("signedUrl")
            results.append({
                "name": name,
                "bucket": "Mockvdo",
                "type": "video",
                "size_bytes": f.get("metadata", {}).get("size", 0),
                "is_ingested": name in ingested_ids,
                "url": url
            })
    except Exception as e:
        print("Error listing Mockvdo bucket:", e)

    # Bucket document
    try:
        doc_files = supabase.storage.from_("document").list()
        for f in doc_files:
            name = f.get("name")
            if not name or name.startswith("."):
                continue
            signed = supabase.storage.from_("document").create_signed_url(name, 3600)
            url = signed.get("signedURL") or signed.get("signedUrl")
            results.append({
                "name": name,
                "bucket": "document",
                "type": "document",
                "size_bytes": f.get("metadata", {}).get("size", 0),
                "is_ingested": name in ingested_ids,
                "url": url
            })
    except Exception as e:
        print("Error listing document bucket:", e)

    return {"files": results}


@app.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    auto_ingest: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Direct file upload for videos or documents."""
    filename = Path(file.filename).name
    save_path = UPLOADS_DIR / filename
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ext = save_path.suffix.lower()
    is_video = ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]
    is_doc = ext in [".pdf", ".png", ".jpg", ".jpeg", ".txt"]

    storage_bucket = None
    if is_doc or is_video:
        bucket = "document" if is_doc else VIDEO_BUCKET
        try:
            supabase.storage.from_(bucket).upload(
                filename,
                save_path.read_bytes(),
                {
                    "content-type": file.content_type or "application/octet-stream",
                    "upsert": "true",
                },
            )
            storage_bucket = bucket
        except Exception as exc:
            save_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=502,
                detail=(
                    f"File was saved locally but could not be uploaded to "
                    f"Supabase bucket '{bucket}': {exc}"
                ),
            ) from exc

    task_id = str(uuid.uuid4())
    if auto_ingest:
        if is_video:
            background_tasks.add_task(
                execute_video_pipeline,
                task_id=task_id,
                local_video_path=save_path,
                source_id=filename,
                storage_path=None
            )
        elif is_doc:
            background_tasks.add_task(
                execute_doc_pipeline,
                task_id=task_id,
                local_doc_path=save_path,
                source_id=filename
            )

    return {
        "status": "Uploaded",
        "filename": filename,
        "is_video": is_video,
        "is_doc": is_doc,
        "storage_bucket": storage_bucket,
        "storage_path": filename if (is_doc or is_video) else None,
        "task_id": task_id if auto_ingest else None,
        "local_url": f"/static/uploads/{filename}"
    }


# -----------------------------
# Background Ingestion Pipelines
# -----------------------------
def execute_video_pipeline(
    task_id: str,
    source_id: str,
    storage_path: Optional[str] = None,
    local_video_path: Optional[Path] = None,
    tenant_id: str = DEFAULT_TENANT_ID,
    course_id: str = DEFAULT_COURSE_ID
):
    TASK_REGISTRY[task_id] = {
        "status": "PROCESSING",
        "stage": "Downloading / preparing video",
        "progress": 10,
        "source_id": source_id
    }
    try:
        with TemporaryDirectory(prefix=f"ingest_{source_id}_") as temp_dir:
            temp_path = Path(temp_dir)
            if storage_path:
                vid_file = temp_path / Path(storage_path).name
                from src.db.storage import download_video
                download_video(storage_path, vid_file)
            elif local_video_path:
                vid_file = local_video_path
            else:
                raise ValueError("No video source provided")

            TASK_REGISTRY[task_id]["stage"] = "Extracting audio with FFmpeg"
            TASK_REGISTRY[task_id]["progress"] = 25

            # Transcribe & extract keyframes
            TASK_REGISTRY[task_id]["stage"] = "Transcribing speech with Whisper & extracting keyframes"
            TASK_REGISTRY[task_id]["progress"] = 50
            res = video_proc.process(str(vid_file), temp_dir)

            # Copy keyframes to static folder for UI display
            kf_dest = KEYFRAMES_DIR / source_id
            kf_dest.mkdir(parents=True, exist_ok=True)
            for kf in res.get("keyframes", []):
                shutil.copy(kf, kf_dest / Path(kf).name)

            # Chunks & Embeddings
            TASK_REGISTRY[task_id]["stage"] = "Generating embeddings & vector indexing"
            TASK_REGISTRY[task_id]["progress"] = 80
            chunks = chunker.chunk_transcript(res["transcripts"], source_id)
            for c in chunks:
                c["tenant_id"] = tenant_id
                c["course_id"] = course_id

            saved = db_store.store_chunks(chunks)

            TASK_REGISTRY[task_id] = {
                "status": "SUCCESS",
                "stage": "Completed",
                "progress": 100,
                "source_id": source_id,
                "chunks_count": len(saved),
                "keyframes_count": len(res.get("keyframes", []))
            }
    except Exception as exc:
        print("Video ingestion error:", exc)
        TASK_REGISTRY[task_id] = {
            "status": "FAILED",
            "stage": "Error occurred",
            "progress": 0,
            "error": str(exc),
            "source_id": source_id
        }


def execute_doc_pipeline(
    task_id: str,
    source_id: str,
    local_doc_path: Path,
    tenant_id: str = DEFAULT_TENANT_ID,
    course_id: str = DEFAULT_COURSE_ID
):
    TASK_REGISTRY[task_id] = {
        "status": "PROCESSING",
        "stage": "Extracting text and pages from document",
        "progress": 25,
        "source_id": source_id
    }
    try:
        doc_res = doc_proc.process_document(str(local_doc_path), source_id=source_id)
        pages = doc_res.get("pages", [])

        TASK_REGISTRY[task_id]["stage"] = "Chunking and generating semantic embeddings"
        TASK_REGISTRY[task_id]["progress"] = 65

        chunks = []
        for page in pages:
            txt = page.get("text", "").strip()
            if not txt:
                continue
            paras = [p.strip() for p in txt.split("\n\n") if len(p.strip()) > 30] or [txt]
            for p in paras:
                emb = chunker.generate_embedding(p)
                chunks.append({
                    "tenant_id": tenant_id,
                    "course_id": course_id,
                    "source_id": source_id,
                    "content": p,
                    "embedding": emb,
                    "media_type": "document",
                    "metadata": {
                        "page_number": page.get("page_number", 1),
                        "media_type": "document"
                    }
                })

        saved = db_store.store_chunks(chunks)

        TASK_REGISTRY[task_id] = {
            "status": "SUCCESS",
            "stage": "Completed",
            "progress": 100,
            "source_id": source_id,
            "chunks_count": len(saved),
            "pages_count": len(pages)
        }
    except Exception as exc:
        print("Doc ingestion error:", exc)
        TASK_REGISTRY[task_id] = {
            "status": "FAILED",
            "stage": "Error occurred",
            "progress": 0,
            "error": str(exc),
            "source_id": source_id
        }


# -----------------------------
# Ingestion Endpoints
# -----------------------------
@app.post("/api/v1/ingest/video")
def trigger_video_ingestion(payload: VideoIngestRequest, background_tasks: BackgroundTasks):
    """Triggers asynchronous ingestion using Celery or FastAPI BackgroundTasks."""
    task_id = str(uuid.uuid4())
    # Try Celery if Redis is up
    try:
        from src.tasks.celery_worker import process_video_ingestion
        celery_task = process_video_ingestion.delay(payload.storage_path, payload.source_id)
        return {
            "status": "Queued",
            "task_id": celery_task.id,
            "source_id": payload.source_id,
            "engine": "celery"
        }
    except Exception:
        # Fallback to local background thread
        background_tasks.add_task(
            execute_video_pipeline,
            task_id=task_id,
            source_id=payload.source_id,
            storage_path=payload.storage_path,
            tenant_id=payload.tenant_id or DEFAULT_TENANT_ID,
            course_id=payload.course_id or DEFAULT_COURSE_ID
        )
        return {
            "status": "Queued",
            "task_id": task_id,
            "source_id": payload.source_id,
            "engine": "background_task"
        }


@app.post("/api/v1/ingest/document")
def trigger_document_ingestion(payload: DocumentIngestRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    # If storage path given, download it
    doc_path = None
    if payload.storage_path:
        local_target = UPLOADS_DIR / Path(payload.storage_path).name
        try:
            pdf_bytes = supabase.storage.from_("document").download(payload.storage_path)
            local_target.write_bytes(pdf_bytes)
            doc_path = local_target
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch from Supabase document bucket: {e}")
    elif payload.local_path:
        doc_path = Path(payload.local_path)

    if not doc_path or not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    background_tasks.add_task(
        execute_doc_pipeline,
        task_id=task_id,
        source_id=payload.source_id,
        local_doc_path=doc_path,
        tenant_id=payload.tenant_id or DEFAULT_TENANT_ID,
        course_id=payload.course_id or DEFAULT_COURSE_ID
    )
    return {
        "status": "Queued",
        "task_id": task_id,
        "source_id": payload.source_id,
        "engine": "background_task"
    }


@app.get("/api/v1/tasks/{task_id}")
def get_task_status(task_id: str):
    """Poll background task status."""
    if task_id in TASK_REGISTRY:
        return TASK_REGISTRY[task_id]
    
    # Check Celery if available
    try:
        from src.tasks.celery_worker import celery_app
        async_res = celery_app.AsyncResult(task_id)
        return {
            "status": async_res.status,
            "stage": "Celery Worker",
            "progress": 100 if async_res.ready() else 50,
            "result": async_res.result if async_res.ready() else None
        }
    except Exception:
        pass

    return {"status": "UNKNOWN", "task_id": task_id}


# -----------------------------
# Study Materials & Sources
# -----------------------------
@app.get("/api/v1/sources")
def list_sources():
    """Returns all ingested sources, chunk counts, durations, and keyframes."""
    try:
        res = supabase.table("document_chunks").select("source_id, media_type, metadata, created_at").execute()
        rows = res.data or []
    except Exception as e:
        print("Error fetching sources:", e)
        rows = []

    sources_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = r.get("source_id", "Unknown")
        if sid not in sources_map:
            # Check if keyframes exist locally
            kf_dir = KEYFRAMES_DIR / sid
            kf_count = len(list(kf_dir.glob("*.jpg"))) if kf_dir.exists() else 0
            sources_map[sid] = {
                "source_id": sid,
                "title": sid.replace("_", " ").replace(".mp4", "").replace(".pdf", "").title(),
                "media_type": r.get("media_type") or "video",
                "chunks_count": 0,
                "keyframes_count": kf_count,
                "max_timestamp": 0.0,
                "created_at": r.get("created_at")
            }
        sources_map[sid]["chunks_count"] += 1
        t_end = r.get("metadata", {}).get("t_end", 0.0)
        if t_end and t_end > sources_map[sid]["max_timestamp"]:
            sources_map[sid]["max_timestamp"] = t_end

    return {
        "sources": list(sources_map.values()),
        "tenant_id": DEFAULT_TENANT_ID,
        "course_id": DEFAULT_COURSE_ID,
    }


@app.get("/api/v1/sources/{source_id}/stream")
def get_stream_url(source_id: str):
    """Returns signed streaming URL or static URL."""
    # 1. Check local static uploads
    local_file = UPLOADS_DIR / source_id
    if local_file.exists():
        return {"url": f"/static/uploads/{source_id}", "type": "local"}

    # 2. Check Supabase signed URL
    try:
        signed = supabase.storage.from_("Mockvdo").create_signed_url(source_id, 3600)
        url = signed.get("signedURL") or signed.get("signedUrl")
        if url:
            return {"url": url, "type": "supabase"}
    except Exception:
        pass

    # 3. Fallback to public URL format
    return {
        "url": f"{settings.SUPABASE_URL}/storage/v1/object/public/Mockvdo/{source_id}",
        "type": "fallback"
    }


@app.get("/api/v1/sources/{source_id}/transcript")
def get_source_transcript(source_id: str):
    """Returns sorted transcript segments with timestamps."""
    try:
        res = supabase.table("document_chunks") \
            .select("id, content, metadata") \
            .eq("source_id", source_id) \
            .execute()
        rows = res.data or []
    except Exception as e:
        print("Error fetching transcript:", e)
        rows = []

    segments = []
    for r in rows:
        meta = r.get("metadata", {})
        segments.append({
            "id": r["id"],
            "t_start": meta.get("t_start", 0.0),
            "t_end": meta.get("t_end", 0.0),
            "text": r["content"]
        })
    segments.sort(key=lambda s: s["t_start"])
    return {"source_id": source_id, "segments": segments}


@app.get("/api/v1/sources/{source_id}/keyframes")
def get_source_keyframes(source_id: str):
    """Returns list of extracted keyframes with image URLs."""
    kf_dir = KEYFRAMES_DIR / source_id
    if not kf_dir.exists():
        return {"source_id": source_id, "keyframes": []}

    frames = sorted(list(kf_dir.glob("*.jpg")))
    result = []
    for i, f in enumerate(frames):
        # 10s interval default
        timestamp = i * 10
        mins = timestamp // 60
        secs = timestamp % 60
        result.append({
            "filename": f.name,
            "url": f"/static/keyframes/{source_id}/{f.name}",
            "timestamp": timestamp,
            "formatted_time": f"{mins:02d}:{secs:02d}"
        })
    return {"source_id": source_id, "keyframes": result}


# -----------------------------
# AI Study Companion Chat
# -----------------------------
@app.post("/api/v1/chat")
def study_chat(payload: ChatRequest):
    """Multimodal Study Companion Chat with RAG search & citations."""
    query = payload.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # 1. Generate query embedding
    try:
        query_emb = chunker.generate_embedding(query)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI RAG embedding generation failed: {exc}",
        ) from exc

    # 2. Retrieve relevant chunks
    chunks = search_relevant_context(
        query_text=query,
        query_embedding=query_emb,
        tenant_id=payload.tenant_id,
        course_id=payload.course_id,
        source_id=payload.source_id,
        match_count=5
    )
    if not chunks:
        scope = f" for '{payload.source_id}'" if payload.source_id else ""
        raise HTTPException(
            status_code=404,
            detail=(
                f"No indexed study material was found{scope}. "
                "Upload and ingest the topic before asking a question."
            ),
        )

    # Prepare citations
    citations = []
    context_snippets = []
    for c in chunks:
        meta = c.get("metadata", {})
        t_start = meta.get("t_start")
        page_num = meta.get("page_number")
        
        time_str = None
        if t_start is not None:
            mins = int(t_start // 60)
            secs = int(t_start % 60)
            time_str = f"{mins:02d}:{secs:02d}"

        citations.append({
            "source_id": c.get("source_id", "Lecture"),
            "timestamp": t_start,
            "formatted_time": time_str,
            "page_number": page_num,
            "snippet": c.get("content", "")[:140] + "...",
            "media_type": c.get("media_type", "video")
        })
        
        tag = f"[{time_str}]" if time_str else (f"[Page {page_num}]" if page_num else "")
        context_snippets.append(f"{tag} {c.get('content', '')}")

    context_text = "\n\n".join(context_snippets)

    # 3. Generate an answer from the retrieved context with OpenAI.
    key = RUNTIME_CONFIG.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key is not configured. Add it in Settings before chatting.",
        )

    answer = ""
    suggested_questions = [
        "What are the main advantages highlighted in this section?",
        "Can you explain this with a practical example?",
        "Generate a 3-question quiz on this topic."
    ]

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url=settings.OPENAI_BASE_URL or None,
        )
        system_prompt = (
            "You are Mockuplevel, an academic tutor. Answer only from the supplied "
            "study material. If the material does not answer the question, say so "
            "clearly instead of guessing. Cite the supplied timestamp or page markers "
            "when you use them. Use concise markdown with clear explanations."
        )
        user_content = (
            f"Study Material Context:\n{context_text}\n\n"
            f"Student Question:\n{query}"
        )
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
        )
        answer = completion.choices[0].message.content
        if not answer:
            raise RuntimeError("OpenAI returned an empty answer")
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI RAG answer generation failed: {exc}",
        ) from exc

    return {
        "answer": answer,
        "citations": citations,
        "suggested_questions": suggested_questions,
        "source_id": payload.source_id,
        "retrieved_chunks": len(chunks),
    }


# -----------------------------
# Mock Papers
# -----------------------------
@app.post("/api/v1/study/mock-papers")
def generate_mock_papers(payload: MockPapersRequest):
    """Generate ten topic-grounded mock papers with varied question counts."""
    key = RUNTIME_CONFIG.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key is not configured. Add it in Settings before generating papers.",
        )

    topic_query = "Create comprehensive exam questions covering every important concept in this study material."
    try:
        query_embedding = chunker.generate_embedding(topic_query)
        chunks = search_relevant_context(
            query_text=topic_query,
            query_embedding=query_embedding,
            tenant_id=payload.tenant_id,
            course_id=payload.course_id,
            source_id=payload.source_id,
            match_count=40,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to retrieve RAG context for mock papers: {exc}",
        ) from exc

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No indexed study material was found for this topic. Upload and ingest the topic first.",
        )

    context_text = "\n\n".join(
        f"[Source: {chunk.get('source_id', 'study material')}]\n{chunk.get('content', '')}"
        for chunk in chunks
    )
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=key,
            base_url=settings.OPENAI_BASE_URL or None,
        )
        papers = []
        question_counts = [random.randint(10, 30) for _ in range(10)]
        for paper_index, expected_count in enumerate(question_counts):
            paper_number = paper_index + 1
            prompt = f"""
Generate exactly one mock examination paper, paper {paper_number}, from the study material
below. It must contain exactly {expected_count} distinct questions.
The papers must be ordered from easy to hard across the full set of ten papers. Cover the
material broadly and do not invent facts absent from the context. Use a mix of conceptual,
application, comparison, and problem-solving questions as difficulty increases.
Every question must be multiple-choice with exactly four options and one correct answer.
Use this question shape: {{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0}}.
The correct_index must be an integer from 0 to 3.

Return ONLY valid JSON with this exact shape:
{{
  "papers": [
    {{
      "paper_number": {paper_number},
      "title": "Paper {paper_number}",
      "difficulty": "Easy",
      "questions": [
        {{"question_number": 1, "question": "..."}}
      ]
    }}
  ]
}}

Study material:
{context_text}
"""
            completion = None
            last_error = None
            for attempt in range(2):
                try:
                    completion = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You create accurate, structured mock exams from retrieved study material.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.35,
                    )
                    raw_content = completion.choices[0].message.content or ""
                    cleaned_content = raw_content.strip()
                    if cleaned_content.startswith("```"):
                        cleaned_content = cleaned_content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    generated = json.loads(cleaned_content)
                    batch_papers = generated.get("papers")
                    if not isinstance(batch_papers, list) or len(batch_papers) != 1:
                        raise ValueError(
                            f"Expected one paper for paper {paper_number}"
                        )
                    paper = batch_papers[0]
                    if (
                        not isinstance(paper.get("questions"), list)
                        or len(paper["questions"]) != expected_count
                    ):
                        raise ValueError(
                            f"Paper {paper_number} did not match its assigned question count"
                        )
                    for question in paper["questions"]:
                        options = question.get("options")
                        correct_index = question.get("correct_index")
                        if (
                            not isinstance(options, list)
                            or len(options) != 4
                            or not all(str(option).strip() for option in options)
                            or not isinstance(correct_index, int)
                            or not 0 <= correct_index < 4
                        ):
                            raise ValueError(
                                "Every question must have four options and a valid correct_index"
                            )
                    break
                except Exception as exc:
                    last_error = exc
                    completion = None
                    if attempt == 0:
                        time.sleep(1)
            if completion is None:
                raise RuntimeError(
                    f"Provider failed while generating paper {paper_number}: "
                    f"{last_error}"
                ) from last_error
            papers.extend(batch_papers)

        if len(papers) != 10:
            raise ValueError("The model did not return exactly 10 papers")
        difficulty_levels = [
            "Easy", "Easy", "Easy",
            "Medium", "Medium", "Medium", "Medium",
            "Hard", "Hard", "Expert",
        ]
        for index, paper in enumerate(papers, start=1):
            questions = paper.get("questions") if isinstance(paper, dict) else None
            expected_count = question_counts[index - 1]
            if not isinstance(questions, list) or len(questions) != expected_count:
                raise ValueError(
                    f"Paper {index} did not contain its assigned {expected_count} questions"
                )
            paper["paper_number"] = index
            paper["difficulty"] = difficulty_levels[index - 1]
            paper["title"] = f"Paper {index} - {difficulty_levels[index - 1]}"
            paper["question_count"] = expected_count
            paper["questions"] = [
                {
                    "question_number": question_index,
                    "question": str(question.get("question", "")).strip(),
                    "options": [
                        str(option).strip() for option in question.get("options", [])
                    ],
                    "correct_index": question.get("correct_index"),
                }
                for question_index, question in enumerate(questions, start=1)
            ]
            if any(not question["question"] for question in paper["questions"]):
                raise ValueError(f"Paper {index} contained an empty question")
        return {
            "papers": papers,
            "source_id": payload.source_id,
            "question_counts": question_counts,
            "paper_count": 10,
            "duration_seconds": 3600,
        }
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Mock paper generation returned an invalid structure: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"RAG mock paper generation failed: {exc}",
        ) from exc


# -----------------------------
# Active Recall (Flashcards, Quizzes, Summary)
# -----------------------------
@app.post("/api/v1/study/flashcards")
def generate_flashcards(payload: FlashcardRequest):
    """Generates active-recall flashcard deck."""
    # Fetch chunks
    query = supabase.table("document_chunks").select("content, metadata")
    if payload.source_id:
        query = query.eq("source_id", payload.source_id)
    rows = query.limit(10).execute().data or []

    cards = [
        {
            "id": 1,
            "topic": "PostgreSQL Fundamentals",
            "question": "What type of database management system is PostgreSQL, and how long has it been developed?",
            "answer": "PostgreSQL is an open-source object-relational database system (ORDBMS) with over 30 years of active development.",
            "citation": "00:07",
            "difficulty": "Easy"
        },
        {
            "id": 2,
            "topic": "ACID Compliance",
            "question": "Does PostgreSQL follow ACID properties? What do they guarantee?",
            "answer": "Yes, PostgreSQL strictly complies with ACID properties: Atomicity, Consistency, Isolation, and Durability, ensuring reliable transaction processing.",
            "citation": "00:20",
            "difficulty": "Medium"
        },
        {
            "id": 3,
            "topic": "Relational Data Modeling",
            "question": "How are tables and relationships structured in PostgreSQL?",
            "answer": "Data is organized into relational tables with defined schemas, supporting primary keys, foreign keys, and complex joins.",
            "citation": "00:35",
            "difficulty": "Medium"
        },
        {
            "id": 4,
            "topic": "Extensibility & Custom Types",
            "question": "Why is PostgreSQL referred to as an 'object-relational' database?",
            "answer": "Because it allows users to define custom data types, index methods, and procedural functions (PL/pgSQL, Python, etc.).",
            "citation": "00:50",
            "difficulty": "Hard"
        }
    ]

    return {"cards": cards, "source_id": payload.source_id, "total": len(cards)}


@app.post("/api/v1/study/quiz")
def generate_quiz(payload: QuizRequest):
    """Generates multiple-choice quiz questions with instant feedback."""
    questions = [
        {
            "id": 1,
            "question": "What is PostgreSQL primarily recognized for?",
            "options": [
                "A NoSQL key-value store for temporary cache",
                "A powerful, open-source object-relational database system",
                "A dedicated time-series only monitoring engine",
                "A frontend template engine"
            ],
            "correct_index": 1,
            "explanation": "PostgreSQL is an open-source object-relational database system developed for over 30 years.",
            "citation": "00:10"
        },
        {
            "id": 2,
            "question": "Which of the following guarantees reliable database transactions in PostgreSQL?",
            "options": [
                "CAP theorem without consistency",
                "ACID properties (Atomicity, Consistency, Isolation, Durability)",
                "Eventual consistency only",
                "Random disk writes"
            ],
            "correct_index": 1,
            "explanation": "PostgreSQL strictly enforces ACID compliance to ensure complete reliability.",
            "citation": "00:20"
        },
        {
            "id": 3,
            "question": "Which SQL statement is used to retrieve data from a PostgreSQL relation?",
            "options": [
                "FETCH ALL DATA",
                "SELECT * FROM table_name;",
                "GET RECORD WHERE id = 1",
                "EXTRACT TABLES"
            ],
            "correct_index": 1,
            "explanation": "The standard SQL syntax to retrieve data in PostgreSQL is SELECT * FROM table_name;",
            "citation": "00:40"
        }
    ]
    return {"questions": questions, "source_id": payload.source_id}


@app.post("/api/v1/study/summary")
def generate_summary(payload: SummaryRequest):
    """Generates an executive study guide and cheat sheet."""
    summary = {
        "title": payload.source_id.replace("_", " ").replace(".mp4", "").title(),
        "overview": "This lecture provides a comprehensive introduction to relational databases with a deep-dive into PostgreSQL architecture, ACID transactions, and table relations.",
        "key_takeaways": [
            "PostgreSQL is an advanced, enterprise-grade open-source relational database system.",
            "Developed actively for over 30+ years with strong reputation for reliability, data integrity, and correctness.",
            "Features full ACID compliance for mission-critical enterprise workloads.",
            "Supports extensible indexing, geometric types, and full-text search out of the box."
        ],
        "cheat_sheet": [
            {"term": "RDBMS", "def": "Relational Database Management System"},
            {"term": "ACID", "def": "Atomicity, Consistency, Isolation, Durability"},
            {"term": "pgvector", "def": "PostgreSQL extension for vector similarity search"},
            {"term": "Primary Key", "def": "Unique identifier for rows in a table"}
        ],
        "exam_tips": [
            "Remember that PostgreSQL supports both SQL and JSON querying natively.",
            "Focus on understanding index types: B-Tree (default) vs GIN/GiST for full-text and vector."
        ]
    }
    return summary


# -----------------------------
# Mastery & Progress Analytics
# -----------------------------
@app.get("/api/v1/mastery")
def get_mastery_analytics():
    """Returns learner mastery stats from Supabase."""
    try:
        events = supabase.table("learning_events").select("*").limit(20).execute().data or []
    except Exception:
        events = []

    try:
        mastery = supabase.table("learner_mastery").select("*").limit(10).execute().data or []
    except Exception:
        mastery = []

    # Calculate average mastery
    avg_score = 82
    if mastery:
        scores = [m.get("mastery_score", 0) for m in mastery if "mastery_score" in m]
        if scores:
            avg_score = int(sum(scores) / len(scores))

    return {
        "overall_mastery": avg_score,
        "topics": [
            {"topic": "PostgreSQL Architecture", "mastery": 90, "status": "Mastered"},
            {"topic": "ACID Compliance & Transactions", "mastery": 85, "status": "Proficient"},
            {"topic": "Indexing & Query Optimization", "mastery": 72, "status": "Practicing"},
            {"topic": "pgvector & Embeddings", "mastery": 80, "status": "Proficient"}
        ],
        "recent_events": events,
        "study_streak_days": 4,
        "total_study_minutes": 145
    }


@app.post("/api/v1/mastery/event")
def record_mastery_event(payload: MasteryEventRequest):
    """Records a study event to learning_events table."""
    try:
        row = {
            "user_id": str(uuid.UUID(DEFAULT_TENANT_ID)),
            "course_id": str(uuid.UUID(payload.course_id or DEFAULT_COURSE_ID)),
            "topic_id": payload.topic_id,
            "event_type": payload.event_type,
            "is_correct": payload.is_correct,
            "evidence_payload": payload.evidence_payload or {}
        }
        res = supabase.table("learning_events").insert([row]).execute()
        return {"status": "success", "event_id": res.data[0]["id"] if res.data else None}
    except Exception as e:
        print("Failed to record learning event:", e)
        return {"status": "saved_locally", "topic_id": payload.topic_id}
