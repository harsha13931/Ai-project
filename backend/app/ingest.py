"""Stage 1-3: extract text, chunk with LangChain, embed with HuggingFace.

Extraction keeps page numbers so answers can cite their source page.
Chunking uses LangChain's RecursiveCharacterTextSplitter for paragraph-aware
splitting.  Embeddings use a free, local HuggingFace model (no API key).
"""
from __future__ import annotations

import io
import logging
import re

import docx
import numpy as np
from pypdf import PdfReader

from .config import settings

log = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


# ── Text extraction (unchanged — framework-agnostic) ──────────────────

def extract_pages(filename: str, data: bytes) -> list[tuple[int, str]]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type '{ext or 'none'}'. Use PDF, DOCX, TXT or MD.")

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        if not any(text.strip() for _, text in pages):
            raise ValueError("No selectable text found. Scanned PDFs need OCR first.")
        return pages

    if ext == ".docx":
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return [(1, "\n".join(parts))]

    return [(1, data.decode("utf-8", errors="replace"))]


# ── Chunking with LangChain ───────────────────────────────────────────

def chunk_pages(
    pages: list[tuple[int, str]],
    size: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    size = size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        chunks: list[dict] = []
        for page_no, text in pages:
            for chunk_text in splitter.split_text(text):
                chunk_text = chunk_text.strip()
                if chunk_text:
                    chunks.append({"page": page_no, "text": chunk_text})
        return chunks
    except ImportError:
        log.warning("langchain-text-splitters not installed, using built-in chunker")
        return _fallback_chunk_pages(pages, size, overlap)


def _fallback_chunk_pages(
    pages: list[tuple[int, str]], size: int, overlap: int,
) -> list[dict]:
    """Built-in chunker kept as fallback."""
    chunks: list[dict] = []
    for page_no, text in pages:
        paragraphs: list[str] = []
        for raw in re.split(r"\n\s*\n|\n", text):
            raw = raw.strip()
            if raw:
                paragraphs.extend(_split_long(raw, size) if len(raw) > size else [raw])
        buffer = ""
        for para in paragraphs:
            if buffer and len(buffer) + len(para) + 1 > size:
                chunks.append({"page": page_no, "text": buffer})
                room = size - len(para) - 1
                tail = buffer[-min(overlap, room):] if room > 0 else ""
                tail = tail.split(" ", 1)[-1] if " " in tail else ""
                buffer = f"{tail} {para}".strip()
            else:
                buffer = f"{buffer}\n{para}".strip() if buffer else para
        if buffer:
            chunks.append({"page": page_no, "text": buffer})
    return chunks


def _split_long(paragraph: str, size: int) -> list[str]:
    pieces, current = [], ""
    for word in paragraph.split():
        if len(current) + len(word) + 1 > size and current:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        pieces.append(current)
    return pieces


# ── Embeddings: HuggingFace (primary) → hashing (fallback) ────────────

_hf_embedder = None


def get_hf_embeddings():
    """Return a LangChain HuggingFaceEmbeddings instance (singleton)."""
    global _hf_embedder
    if _hf_embedder is not None:
        return _hf_embedder
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        _hf_embedder = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": settings.EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )
        log.info("Using HuggingFace embeddings: %s", settings.EMBEDDING_MODEL)
        return _hf_embedder
    except Exception:
        log.warning("HuggingFace embeddings unavailable, using hashing fallback")
        return None


class HashingEmbedder:
    """Offline embedder kept as zero-dependency fallback."""

    name = "hashing-v1"
    dim = 512
    _token = re.compile(r"[a-z0-9+#.]+")
    _stop = {
        "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
        "is", "are", "was", "were", "be", "by", "as", "at", "from", "that", "this", "it",
    }

    def tokens(self, text: str) -> list[str]:
        return [t for t in self._token.findall(text.lower()) if t not in self._stop]

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            toks = self.tokens(text)
            feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
            counts: dict[int, int] = {}
            for feat in feats:
                idx = _stable_hash(feat) % self.dim
                counts[idx] = counts.get(idx, 0) + 1
            for idx, count in counts.items():
                matrix[row, idx] = 1.0 + np.log(count)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-9)


def _stable_hash(text: str) -> int:
    h = 2166136261
    for byte in text.encode("utf-8"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return h
