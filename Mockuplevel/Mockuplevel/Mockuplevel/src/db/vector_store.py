from supabase import create_client, Client
from src.config import settings
from pathlib import Path
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

VIDEO_BUCKET = "Mockvdo"

def download_video(storage_path: str, local_path: Path) -> Path:
    video_bytes = supabase.storage.from_(VIDEO_BUCKET).download(storage_path)
    local_path.write_bytes(video_bytes)
    return local_path

#input by frotend
DEFAULT_TENANT_ID = "51d1d7f6-c03f-5e63-8019-265ba8b68c7c"
DEFAULT_COURSE_ID = "51d1d7f6-c03f-5e63-8019-265ba8b68c7c"

class VectorStore:
    """Persistence operations for embedded document chunks."""

    def store_chunks(self, chunks: list[dict]) -> list[dict]:
        if not chunks:
            return []

        clean_chunks = []
        for c in chunks:
            media_type = c.get("media_type") or c.get("metadata", {}).get("media_type", "video")
            row = {
                "tenant_id": c.get("tenant_id") or DEFAULT_TENANT_ID,
                "course_id": c.get("course_id") or DEFAULT_COURSE_ID,
                "source_id": c.get("source_id", "default"),
                "content": c.get("content", ""),
                "embedding": c.get("embedding"),
                "media_type": media_type,
                "metadata": c.get("metadata", {})
            }
            clean_chunks.append(row)

        try:
            response = supabase.table("document_chunks").insert(clean_chunks).execute()
            return response.data or []
        except Exception as e:
            print("Failed to store chunks in Supabase:", e)
            return clean_chunks


def search_relevant_context(query_text: str, query_embedding: list = None, tenant_id: str = None, course_id: str = None, source_id: str = None, match_count: int = 5):
    # 1. Try match_document_chunks_rrf RPC if tenant and course IDs are provided
    if tenant_id and course_id and query_embedding:
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
                return response.data
        except Exception:
            pass

    # 2. Resilient table search
    try:
        query = supabase.table("document_chunks").select("id, source_id, content, media_type, metadata, created_at")
        if source_id:
            query = query.eq("source_id", source_id)
        
        words = [w for w in query_text.replace("?", "").replace(",", "").split() if len(w) > 3]
        if words:
            query = query.ilike("content", f"%{words[0]}%")
        res = query.limit(match_count).execute()
        if res.data:
            return res.data
        
        # Fallback to recent chunks for that source
        fallback = supabase.table("document_chunks").select("id, source_id, content, media_type, metadata, created_at")
        if source_id:
            fallback = fallback.eq("source_id", source_id)
        res_fb = fallback.order("created_at", desc=False).limit(match_count).execute()
        return res_fb.data or []
    except Exception as exc:
        print("Error searching relevant context:", exc)
        return []