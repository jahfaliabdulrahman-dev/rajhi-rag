"""Retriever: local multilingual embeddings + FAISS (bank-agnostic core).

Model: intfloat/multilingual-e5-small (~110MB, strong Arabic, CPU-free tier
compatible). e5 expects the 'query: ' / 'passage: ' prefixes — handled here
so callers pass raw text.
"""

from __future__ import annotations

from statement_qa.chunking import Chunk

EMBED_MODEL = "intfloat/multilingual-e5-small"

_E5_PREFIX_PASSAGE = "passage: "
_E5_PREFIX_QUERY = "query: "


def build_index(chunks: list[Chunk]):
    """Chunks -> FAISS index (+ stored chunk list). First call downloads
    the model (~110MB) into the local HF cache."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    texts = [_E5_PREFIX_PASSAGE + c.text for c in chunks]
    metas = [{"chunk_id": c.chunk_id, "page": c.page,
              "row_start": c.start_row, "row_end": c.end_row}
             for c in chunks]
    store = FAISS.from_texts(texts, embedding=embeddings, metadatas=metas)
    return store


def retrieve(store, query: str, k: int = 4) -> list[dict]:
    """Query -> top-k chunks {chunk_id, page, rows, text, score}."""
    hits = store.similarity_search_with_score(_E5_PREFIX_QUERY + query, k=k)
    return [
        {
            "chunk_id": doc.metadata["chunk_id"],
            "page": doc.metadata["page"],
            "row_start": doc.metadata["row_start"],
            "row_end": doc.metadata["row_end"],
            "text": doc.page_content,
            "score": float(score),
        }
        for doc, score in hits
    ]
