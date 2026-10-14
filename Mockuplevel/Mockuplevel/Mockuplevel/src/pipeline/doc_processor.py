"""Document processing helpers for text extraction and chunking."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from openai import OpenAI

from src.config import settings

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

class DocumentProcessor:
    """Extract text from PDF and image documents, with OCR fallback."""

    def __init__(self, ocr_language: str = "eng", api_key: Optional[str] = None):
        self.ocr_language = ocr_language
        api_key = api_key or getattr(settings, "OPENAI_API_KEY", None)
        self.client = OpenAI(api_key=api_key) if api_key else None

    def _validate_document_path(self, document_path: str) -> str:
        if not document_path:
            raise ValueError("document_path must not be empty")
        normalized_path = os.fspath(document_path)
        if not os.path.exists(normalized_path):
            raise FileNotFoundError(f"Document file does not exist: {normalized_path}")
        return normalized_path

    def _ocr_image(self, image: Image.Image) -> str:
        try:
            text = pytesseract.image_to_string(image, lang=self.ocr_language)
            return text.strip()
        except Exception:
            return "[Scanned document page / diagram - OCR engine unavailable]"

    def _extract_pdf_page_text(self, page: fitz.Page) -> str:
        text = page.get_text("text", sort=True).strip()
        if text:
            return text

        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return self._ocr_image(image)

    def extract_text(self, document_path: str) -> List[Dict[str, Any]]:
        """Return a list of page payloads containing page numbers and extracted text."""
        normalized_path = self._validate_document_path(document_path)
        extension = os.path.splitext(normalized_path)[1].lower()

        if extension == ".pdf":
            doc = fitz.open(normalized_path)
            pages: List[Dict[str, Any]] = []
            try:
                for page_number, page in enumerate(doc, start=1):
                    pages.append({
                        "page_number": page_number,
                        "text": self._extract_pdf_page_text(page),
                    })
            finally:
                doc.close()
            return pages

        if extension in _IMAGE_EXTENSIONS:
            with Image.open(normalized_path) as image:
                return [{
                    "page_number": 1,
                    "text": self._ocr_image(image.convert("RGB")),
                }]

        with open(normalized_path, "r", encoding="utf-8") as handle:
            text = handle.read().strip()
        return [{"page_number": 1, "text": text}]

    def process_document(self, document_path: str, source_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract document text and return a structured payload for downstream embedding."""
        documents = self.extract_text(document_path)
        page_text = [page["text"] for page in documents if page.get("text")]
        content = "\n\n".join(page_text)
        result: Dict[str, Any] = {
            "source_type": "document",
            "source_id": source_id,
            "pages": documents,
            "content": content,
        }
        return result

    def generate_embedding(self, text: str) -> List[float]:
        """Create an embedding for a text snippet using OpenAI or fallback."""
        if self.client is not None:
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                )
                return response.data[0].embedding
            except Exception:
                pass

        import hashlib, math
        h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        vec = [math.sin(h * (i + 1) % 10000) for i in range(1536)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]


def extract_document_text(document_path: str, ocr_language: str = "eng") -> List[Dict[str, Any]]:
    return DocumentProcessor(ocr_language=ocr_language).extract_text(document_path)


def process_document(document_path: str, source_id: Optional[str] = None, ocr_language: str = "eng") -> Dict[str, Any]:
    return DocumentProcessor(ocr_language=ocr_language).process_document(document_path, source_id=source_id)
