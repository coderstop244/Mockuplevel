from supabase import create_client, Client
from src.config import settings
from pathlib import Path
import json
import math
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

VIDEO_BUCKET = "Mockvdo"
EMBEDDING_DIMENSIONS = 1536

def download_video(storage_path: str, local_path: Path) -> Path:
    video_bytes = supabase.storage.from_(VIDEO_BUCKET).download(storage_path)
    local_path.write_bytes(video_bytes)
    return local_path

DEFAULT_TENANT_ID = "51d1d7f6-c03f-5e63-8019-265ba8b68c7c"
DEFAULT_COURSE_ID = "51d1d7f6-c03f-5e63-8019-265ba8b68c7c"


def _normalize_rpc_row(row: dict) -> dict:
    """Convert the RPC's flattened citation fields to the app's row shape."""
    metadata = dict(row.get("metadata") or {})
    for field, metadata_key in (
        ("t_start", "t_start"),
        ("t_end", "t_end"),
        ("page", "page_number"),
        ("slide", "slide"),
    ):
        if row.get(field) is not None:
            metadata[metadata_key] = row[field]
    normalized = dict(row)
    normalized["metadata"] = metadata
    return normalized


class VectorStore:
    """Persistence operations for embedded document chunks."""

    def store_chunks(self, chunks: list[dict]) -> list[dict]:
        if not chunks:
            return []

        clean_chunks = []
        for c in chunks:
            embedding = c.get("embedding")
            if not isinstance(embedding, (list, tuple)):
                raise ValueError("Cannot store chunk without an embedding")
            if len(embedding) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Invalid embedding dimensions: expected "
                    f"{EMBEDDING_DIMENSIONS}, got {len(embedding)}"
                )

            media_type = c.get("media_type") or c.get("metadata", {}).get("media_type", "video")
            row = {
                "tenant_id": c.get("tenant_id") or DEFAULT_TENANT_ID,
                "course_id": c.get("course_id") or DEFAULT_COURSE_ID,
                "source_id": c.get("source_id", "default"),
                "content": c.get("content", ""),
                "embedding": embedding,
                "media_type": media_type,
                "metadata": c.get("metadata", {})
            }
            clean_chunks.append(row)

        try:
            response = supabase.table("document_chunks").insert(clean_chunks).execute()
            saved = response.data or []
            if len(saved) != len(clean_chunks):
                raise RuntimeError(
                    f"Supabase stored {len(saved)} of {len(clean_chunks)} chunks"
                )
            if any(row.get("embedding") is None for row in saved):
                raise RuntimeError("Supabase returned a chunk with a null embedding")
            return saved
        except Exception as exc:
            raise RuntimeError(
                f"Failed to store {len(clean_chunks)} chunks in Supabase: {exc}"
            ) from exc


def search_relevant_context(query_text: str, query_embedding: list = None, tenant_id: str = None, course_id: str = None, source_id: str = None, match_count: int = 5):
    # 1. Try match_document_chunks_rrf RPC if tenant and course IDs are provided
    # The current RPC contract has no source filter. For topic-scoped study
    # sessions, use the source-filtered vector query below instead.
    if tenant_id and course_id and query_embedding and not source_id:
        try:
            response = supabase.rpc(
                "match_document_chunks_rrf",
                {
                    "query_text": query_text,
                    "query_embedding": query_embedding,
                    "filter_tenant_id": tenant_id,
                    "filter_course_id": course_id,
                    "match_count": match_count
                }
            ).execute()
            if response.data:
                return [_normalize_rpc_row(row) for row in response.data]
        except Exception as exc:
            print(f"Vector search RPC unavailable; using local vector fallback: {exc}")

    if query_embedding:
        try:
            query = supabase.table("document_chunks").select(
                "id, tenant_id, course_id, source_id, content, media_type, metadata, created_at, embedding"
            )
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            if course_id:
                query = query.eq("course_id", course_id)
            if source_id:
                query = query.eq("source_id", source_id)

            rows = query.limit(2000).execute().data or []
            scored = []
            query_norm = math.sqrt(sum(value * value for value in query_embedding))
            if query_norm:
                for row in rows:
                    raw_embedding = row.get("embedding")
                    if not raw_embedding:
                        continue
                    embedding = (
                        raw_embedding
                        if isinstance(raw_embedding, list)
                        else json.loads(raw_embedding)
                    )
                    if len(embedding) != len(query_embedding):
                        continue
                    row_norm = math.sqrt(sum(value * value for value in embedding))
                    if not row_norm:
                        continue
                    similarity = sum(
                        left * right
                        for left, right in zip(query_embedding, embedding)
                    ) / (query_norm * row_norm)
                    scored.append((similarity, row))

            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                return [row for _, row in scored[:match_count]]
        except Exception as exc:
            print(f"Local vector search unavailable: {exc}")
            return []

        # Do not answer from arbitrary recent rows when vector retrieval found
        # nothing; that would make the response look grounded when it is not.
        return []

    # Text search is only used for callers that did not provide an embedding.
    try:
        query = supabase.table("document_chunks").select(
            "id, tenant_id, course_id, source_id, content, media_type, metadata, created_at"
        )
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        if course_id:
            query = query.eq("course_id", course_id)
        if source_id:
            query = query.eq("source_id", source_id)
        
        words = [w for w in query_text.replace("?", "").replace(",", "").split() if len(w) > 3]
        if words:
            query = query.ilike("content", f"%{words[0]}%")
        res = query.limit(match_count).execute()
        if res.data:
            return res.data
        
        # Fallback to recent chunks for that source
        fallback = supabase.table("document_chunks").select(
            "id, tenant_id, course_id, source_id, content, media_type, metadata, created_at"
        )
        if tenant_id:
            fallback = fallback.eq("tenant_id", tenant_id)
        if course_id:
            fallback = fallback.eq("course_id", course_id)
        if source_id:
            fallback = fallback.eq("source_id", source_id)
        res_fb = fallback.order("created_at", desc=False).limit(match_count).execute()
        return res_fb.data or []
    except Exception as exc:
        print("Error searching relevant context:", exc)
        return []