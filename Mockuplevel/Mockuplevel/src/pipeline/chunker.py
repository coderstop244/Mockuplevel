"""Content chunking."""
from openai import OpenAI
from src.config import settings
from typing import List, Dict, Any, Optional

class EmbeddingChunker:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = ""
        self.client = None
        configured_key = (
            getattr(settings, "OPENAI_API_KEY", "")
            if api_key is None
            else api_key
        )
        self.set_api_key(configured_key)

    def set_api_key(self, api_key: str) -> None:
        """Configure the OpenAI client used for both ingestion and RAG queries."""
        self.api_key = api_key.strip()
        self.client = (
            OpenAI(
                api_key=self.api_key,
                base_url=settings.OPENAI_BASE_URL or None,
            )
            if self.api_key
            else None
        )

    def generate_embedding(self, text: str) -> List[float]:
        if not self.client:
            raise RuntimeError(
                "OpenAI API key is not configured; cannot generate a RAG embedding"
            )

        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = response.data[0].embedding
            if len(embedding) != 1536:
                raise RuntimeError(
                    f"OpenAI returned an embedding with {len(embedding)} dimensions; "
                    "expected 1536"
                )
            return embedding
        except Exception as exc:
            raise RuntimeError(
                f"OpenAI embedding request failed: {exc}"
            ) from exc

    def chunk_transcript(self, transcript_segments: List[Dict[str, Any]], source_id: str) -> List[Dict[str, Any]]:
        chunks = []
        for segment in transcript_segments:
            embedding = self.generate_embedding(segment["text"])
            chunks.append({
                "source_id": source_id,
                "content": segment["text"],
                "embedding": embedding,
                "metadata": {
                    "t_start": segment["t_start"],
                    "t_end": segment["t_end"],
                    "media_type": "video"
                }
            })
        return chunks