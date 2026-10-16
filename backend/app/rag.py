"""Stages 4-6 of the pipeline: index, retrieve, and answer with citations."""
import os
import re
import uuid

import httpx
import numpy as np

from .ingest import HashingEmbedder, chunk_pages, extract_pages
from .resume import build_profile, looks_like_resume

STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "are",
    "what", "how", "why", "when", "which", "who", "does", "do", "did", "it", "this", "that",
}
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _stem(token: str) -> str:
    """Light suffix stripping so 'release' matches 'releases' and 'releasing'."""
    for suffix in ("ing", "ed", "es", "e", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


class RAGIndex:
    def __init__(self, embedder=None):
        self.embedder = embedder or HashingEmbedder()
        self.chunks: list[dict] = []
        self.vectors = np.zeros((0, self.embedder.dim), dtype=np.float32)
        self.documents: dict[str, dict] = {}

    def add_document(self, filename: str, data: bytes) -> dict:
        pages = extract_pages(filename, data)
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("The file contains no readable text.")

        doc_id = uuid.uuid4().hex[:12]
        full_text = "\n".join(text for _, text in pages)
        vectors = self.embedder.embed([c["text"] for c in chunks])

        for chunk in chunks:
            chunk.update(doc_id=doc_id, doc_name=filename)
        self.chunks.extend(chunks)
        self.vectors = np.vstack([self.vectors, vectors])

        is_resume = looks_like_resume(full_text)
        self.documents[doc_id] = {
            "id": doc_id,
            "name": filename,
            "pages": len(pages),
            "chunks": len(chunks),
            "is_resume": is_resume,
            "profile": build_profile(full_text) if is_resume else None,
            "text": full_text,
        }
        return self.public_doc(doc_id)

    def public_doc(self, doc_id: str) -> dict:
        doc = self.documents[doc_id]
        return {k: v for k, v in doc.items() if k != "text"}

    def search(self, query: str, k: int = 4, doc_id: str | None = None) -> list[dict]:
        if not self.chunks:
            return []
        scores = self.vectors @ self.embedder.embed([query])[0]
        results = []
        for idx in np.argsort(-scores):
            chunk = self.chunks[idx]
            if doc_id and chunk["doc_id"] != doc_id:
                continue
            results.append({**chunk, "score": round(float(scores[idx]), 4)})
            if len(results) == k:
                break
        return results

    def answer(self, question: str, doc_id: str | None = None) -> dict:
        hits = [h for h in self.search(question, k=4, doc_id=doc_id) if h["score"] > 0.05]
        if not hits:
            return {"answer": "I could not find that in the uploaded documents.", "mode": "none", "sources": []}

        sources = [{"doc": h["doc_name"], "page": h["page"], "score": h["score"], "excerpt": h["text"][:240]} for h in hits]
        if os.getenv("ANTHROPIC_API_KEY") and os.getenv("ANTHROPIC_MODEL"):
            try:
                return {"answer": self._llm_answer(question, hits), "mode": "llm", "sources": sources}
            except httpx.HTTPError:
                pass  # fall back to extractive answer below
        return {"answer": self._extractive_answer(question, hits), "mode": "extractive", "sources": sources}

    def _extractive_answer(self, question: str, hits: list[dict]) -> str:
        """No-LLM fallback: return the sentences that best overlap the question terms."""
        terms = {_stem(t) for t in self.embedder.tokens(question) if t not in STOP}
        sentences = []
        for hit in hits:
            for sentence in re.split(r"(?<=[.!?])\s+|\n", hit["text"]):
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                overlap = len(terms & {_stem(t) for t in self.embedder.tokens(sentence)})
                sentences.append((overlap, sentence))
        sentences.sort(key=lambda pair: -pair[0])
        best = [s for overlap, s in sentences[:3] if overlap > 0]
        return " ".join(best) if best else hits[0]["text"][:400]

    def _llm_answer(self, question: str, hits: list[dict]) -> str:
        context = "\n\n".join(f"[{i + 1}] (page {h['page']}) {h['text']}" for i, h in enumerate(hits))
        response = httpx.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.environ["ANTHROPIC_MODEL"],
                "max_tokens": 600,
                "system": (
                    "Answer using only the numbered context. Cite sources like [1]. "
                    "If the context does not contain the answer, say so plainly."
                ),
                "messages": [{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"].strip()
