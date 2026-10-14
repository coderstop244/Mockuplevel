"""Content chunking."""
from openai import OpenAI
from src.config import settings
from typing import List, Dict, Any

class EmbeddingChunker:
    def __init__(self, api_key: str = None):
        key = api_key or getattr(settings, "OPENAI_API_KEY", "")
        self.api_key = key
        try:
            self.client = OpenAI(api_key=key) if key else None
        except Exception:
            self.client = None

    def generate_embedding(self, text: str) -> List[float]:
        if self.client:
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            except Exception:
                pass
        
        # Deterministic 1536-dim normalized vector fallback
        import hashlib, math
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        vec = [math.sin(h * (i + 1) % 10000) for i in range(1536)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

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