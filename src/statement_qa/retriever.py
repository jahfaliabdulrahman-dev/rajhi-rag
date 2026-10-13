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


def _as_hit(doc, score) -> dict:
    return {
        "chunk_id": doc.metadata["chunk_id"],
        "page": doc.metadata["page"],
        "row_start": doc.metadata["row_start"],
        "row_end": doc.metadata["row_end"],
        "text": doc.page_content,
        "score": float(score),
    }


def index_size(store) -> int:
    """عددُ القطع في الفهرس — **يُقرأ من الفهرس نفسِه** (`index.ntotal`) لا من قائمةٍ مُمرَّرة.

    و`0` تعني «لا أعرف» (فهرسٌ مُقلَّد في الاختبارات) ⇒ فيتصرّف النداءُ بـ`fetch_k` = `k`.
    """
    n = getattr(getattr(store, "index", None), "ntotal", None)
    return int(n) if n is not None else 0


def retrieve(store, query: str, k: int = 4, pages: list[int] | None = None) -> list[dict]:
    """Query -> chunks {chunk_id, page, rows, text, score}.

    **R105-4 · الصفحاتُ المسمّاةُ تسبق البحثَ الدلاليّ:** إن سمّى السؤالُ صفحاتٍ، تُطلَب قطعُها
    **بمرشِّح المكتبة** على `page` أوّلاً، ثمّ يُكمَّل العددُ من البحث الدلاليّ.

    **والفخُّ المقيس (مراجعة ١٠٥):** في `langchain_community` يعمل المرشِّحُ **بعد** البحث المبدئيّ
    ⇒ فبالقيمة الافتراضية `fetch_k=20` تعود القائمةُ **فارغةً** لصفحةٍ لا تقع في أوّل عشرين مرشَّحًا،
    وبـ`fetch_k` = حجمِ الفهرس تعود الصفحةُ (قِيس: الصفحة ٢٤٢ ⇒ `[242]` بـ626). فالحجمُ يُقرأ من
    `index.ntotal` ولا يُخمَّن — **و`0` تعني «لا أعرف»** (فهرسٌ مُقلَّد) فيُطلَب `fetch_k` = العددِ
    المطلوب، ولا يُنهار النداء.

    **وقاعدتان صريحتان (بوّابةُ المُنتِج · R105-4):**
    ① **صفحةٌ مسمّاةٌ لا تُسقَط:** لكلّ صفحةٍ حصّةٌ `max(1, limit // len(pages))`، فسؤالٌ يسمّي
       خمسَ صفحاتٍ يُعيد الخمسَ (‏`limit` يزيد إلى عددها) بدل أن يقطعها عند `k` بصمت.
    ② **والحدُّ مُعلَن:** السقفُ هو `limit = max(k, len(pages))`، وما زاد عن ذلك يُكمَّل دلاليًّا.

    **والفرقُ عن `boost_last_page` (طُويت هنا · مقيسٌ ومُعلَن):** كانت تُلحق **كلَّ** قطع الصفحة الأخيرة
    **بعد** نتائج البحث الدلاليّ (في آخر القائمة: `hits + [extra…]`)، والآن الصفحةُ المسمّاةُ تأتي
    **أوّلاً في الترتيب** وتأخذ حصّتَها من المجموع `limit` (وأقلَّ عددًا حين تكون الصفحةُ كبيرة).
    **والأثرُ المسمّى:** سؤالُ رصيدٍ **يسمّي صفحةً** (`abs-11`) يأخذ قطعَ الصفحة المسمّاة وحدَها ولا يُلحَق
    له رصيدُ الصفحة الأخيرة — لأنّ «المسمّاةُ تسبق»، وهو نصُّ الطلب.
    """
    pages = list(dict.fromkeys(int(p) for p in (pages or [])))
    limit = max(k, len(pages))
    out: list[dict] = []
    seen: set[tuple] = set()

    def take(pairs) -> None:
        for doc, score in pairs:
            key = (doc.metadata["page"], doc.metadata["row_start"], doc.metadata["row_end"])
            if key in seen:
                continue
            seen.add(key)
            out.append(_as_hit(doc, score))

    if pages:
        total = index_size(store) or limit
        per = max(1, limit // len(pages))
        for pg in pages:
            take(store.similarity_search_with_score(
                _E5_PREFIX_QUERY + query, k=per, filter={"page": pg}, fetch_k=total))
    if len(out) < k:
        take(store.similarity_search_with_score(_E5_PREFIX_QUERY + query, k=k))
    return out[:limit]
