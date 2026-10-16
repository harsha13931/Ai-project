"""RAG index: FAISS vector store (primary) with hashing fallback.

When HuggingFace + FAISS are installed the index uses real semantic
embeddings.  Otherwise it falls back to the hashing embedder with
NumPy cosine similarity — still functional, just less accurate.
"""
from __future__ import annotations

import logging
import os
import re
import uuid

import numpy as np

from .config import settings
from .ingest import HashingEmbedder, chunk_pages, extract_pages, get_hf_embeddings
from .resume import build_profile, looks_like_resume

log = logging.getLogger(__name__)

STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "are",
    "what", "how", "why", "when", "which", "who", "does", "do", "did", "it", "this", "that",
}


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "e", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


# ── Module-level singleton ─────────────────────────────────────────────

_index: RAGIndex | None = None


def get_index() -> RAGIndex:
    global _index
    if _index is None:
        _index = RAGIndex()
    return _index


def reset_index() -> None:
    global _index
    _index = RAGIndex()


# ── RAG Index ──────────────────────────────────────────────────────────

class RAGIndex:
    def __init__(self):
        self.documents: dict[str, dict] = {}
        self._hf = get_hf_embeddings()
        self._faiss_store = None
        self._use_faiss = False

        if self._hf is not None:
            try:
                import faiss  # noqa: F401
                self._use_faiss = True
                log.info("FAISS + HuggingFace mode active")
            except ImportError:
                log.warning("faiss-cpu not installed, using HuggingFace embeddings with NumPy search")

        if not self._use_faiss:
            self._fallback_embedder = HashingEmbedder()
            self._chunks: list[dict] = []
            self._vectors = np.zeros((0, self._fallback_embedder.dim), dtype=np.float32)

    # ── Compatibility properties so tests / main.py can access chunks ──
    @property
    def chunks(self) -> list[dict]:
        if self._use_faiss and self._faiss_store is not None:
            docs = self._faiss_store.docstore._dict
            return [
                {"text": d.page_content, **d.metadata}
                for d in docs.values()
            ]
        if not self._use_faiss:
            return self._chunks
        return []

    def add_document(self, filename: str, data: bytes) -> dict:
        pages = extract_pages(filename, data)
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("The file contains no readable text.")

        doc_id = uuid.uuid4().hex[:12]
        full_text = "\n".join(text for _, text in pages)

        if self._use_faiss:
            self._add_to_faiss(chunks, doc_id, filename)
        else:
            vectors = self._fallback_embedder.embed([c["text"] for c in chunks])
            for chunk in chunks:
                chunk.update(doc_id=doc_id, doc_name=filename)
            self._chunks.extend(chunks)
            self._vectors = np.vstack([self._vectors, vectors])

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

    def _add_to_faiss(self, chunks: list[dict], doc_id: str, filename: str):
        from langchain_core.documents import Document
        from langchain_community.vectorstores import FAISS

        docs = [
            Document(
                page_content=c["text"],
                metadata={"page": c["page"], "doc_id": doc_id, "doc_name": filename},
            )
            for c in chunks
        ]
        if self._faiss_store is None:
            self._faiss_store = FAISS.from_documents(docs, self._hf)
        else:
            self._faiss_store.add_documents(docs)

    def public_doc(self, doc_id: str) -> dict:
        doc = self.documents[doc_id]
        return {k: v for k, v in doc.items() if k != "text"}

    def search(self, query: str, k: int = 4, doc_id: str | None = None) -> list[dict]:
        if self._use_faiss and self._faiss_store is not None:
            return self._faiss_search(query, k, doc_id)
        return self._fallback_search(query, k, doc_id)

    def _faiss_search(self, query: str, k: int, doc_id: str | None) -> list[dict]:
        fetch_k = k * 4 if doc_id else k
        results = self._faiss_store.similarity_search_with_score(query, k=fetch_k)
        hits = []
        for doc, score in results:
            if doc_id and doc.metadata.get("doc_id") != doc_id:
                continue
            similarity = 1.0 / (1.0 + score)
            hits.append({
                "text": doc.page_content,
                "page": doc.metadata["page"],
                "doc_id": doc.metadata["doc_id"],
                "doc_name": doc.metadata["doc_name"],
                "score": round(similarity, 4),
            })
            if len(hits) == k:
                break
        return hits

    def _fallback_search(self, query: str, k: int, doc_id: str | None) -> list[dict]:
        if not self._chunks:
            return []
        scores = self._vectors @ self._fallback_embedder.embed([query])[0]
        results = []
        for idx in np.argsort(-scores):
            chunk = self._chunks[idx]
            if doc_id and chunk["doc_id"] != doc_id:
                continue
            results.append({**chunk, "score": round(float(scores[idx]), 4)})
            if len(results) == k:
                break
        return results

    def answer(self, question: str, doc_id: str | None = None) -> dict:
        hits = [h for h in self.search(question, k=settings.RETRIEVAL_K, doc_id=doc_id) if h["score"] > settings.SCORE_THRESHOLD]
        if not hits:
            return {"answer": "I could not find that in the uploaded documents.", "mode": "none", "sources": []}

        sources = [{"doc": h["doc_name"], "page": h["page"], "score": h["score"], "excerpt": h["text"][:240]} for h in hits]

        from .chains import rag_chain
        chain = rag_chain()
        if chain is not None:
            try:
                context = "\n\n".join(f"[{i + 1}] (page {h['page']}) {h['text']}" for i, h in enumerate(hits))
                answer = chain.invoke({"context": context, "question": question})
                return {"answer": answer, "mode": "llm", "sources": sources}
            except Exception:
                log.exception("LLM answering failed, falling back to extractive")

        return {"answer": self._extractive_answer(question, hits), "mode": "extractive", "sources": sources}

    def _extractive_answer(self, question: str, hits: list[dict]) -> str:
        if self._use_faiss:
            tokens_fn = lambda text: [t for t in re.findall(r"[a-z0-9+#.]+", text.lower()) if t not in STOP]
        else:
            tokens_fn = self._fallback_embedder.tokens
        terms = {_stem(t) for t in tokens_fn(question) if t not in STOP}
        sentences = []
        for hit in hits:
            for sentence in re.split(r"(?<=[.!?])\s+|\n", hit["text"]):
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                overlap = len(terms & {_stem(t) for t in tokens_fn(sentence)})
                sentences.append((overlap, sentence))
        sentences.sort(key=lambda pair: -pair[0])
        best = [s for overlap, s in sentences[:3] if overlap > 0]
        return " ".join(best) if best else hits[0]["text"][:400]
