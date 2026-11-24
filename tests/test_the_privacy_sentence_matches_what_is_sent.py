"""وصفُ الخصوصيّة يطابق ما يرسله الكود — لا أكثر ولا أقلّ (قرارُ المالك 2026-11-24: ZDR للنموذجين).

يُقاس **الجسمُ المرسَل** في الطلبين (القراءة · الإجابة) عند آخر طبقةٍ قبل السلك، بلا شبكةٍ ولا كلفة،
ثمّ تُقابَل به جملةُ الخصوصيّة في التقرير: إن سقط `zdr` من طلبٍ أو من الجملة سقط الضابط.
**الرجوع:** `git revert <sha>` لالتزام هذا الملفّ (السطرُ بقيمته في `handoff/claude/STATE.md`).
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from statement_qa.provider_privacy import PROVIDER_PRIVACY  # noqa: E402

_REPLY = {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
          "choices": [{"index": 0, "finish_reason": "stop",
                       "message": {"role": "assistant", "content": "{}"}}],
          "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def test_the_reader_request_carries_zdr(monkeypatch):
    from statement_qa import vlm_reader

    bodies: list[dict] = []

    class _Resp:
        def read(self):
            return json.dumps(_REPLY).encode()

    def _open(req, timeout=None):
        bodies.append(json.loads(req.data.decode()))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _open)
    vlm_reader.chat_vlm_image("AAAA", "اقرأ", max_tokens=10, api_key="sk-test")
    assert bodies, "لم يُلتقط طلبُ القراءة — فالمسبارُ نفسُه مشكوكٌ فيه"
    for b in bodies:
        assert b.get("provider") == PROVIDER_PRIVACY, b.get("provider")


def test_the_answer_request_carries_zdr_beside_the_price_limit(monkeypatch):
    httpx2 = pytest.importorskip("httpx2", reason="عميلُ openai 3.13 غيرُ مركَّب (CI خفيف)")
    pytest.importorskip("langchain_openai", reason="بلا langchain-openai لا ChatOpenAI يُبنى")
    from statement_qa import qa

    bodies: list[dict] = []

    def _send(self, request, *a, **k):
        bodies.append(json.loads(request.read().decode()))
        return httpx2.Response(200, json=_REPLY, request=request)

    monkeypatch.setattr(httpx2.Client, "send", _send)
    qa.build_llm(api_key="sk-test").invoke("كم رصيد الصفحة ٥؟")
    assert len(bodies) == 1, f"لم يُلتقط طلبٌ واحد ({len(bodies)})"
    prov = bodies[0].get("provider", {})
    assert prov.get("zdr") is True, prov
    assert prov.get("max_price") == dict(qa.PROVIDER_MAX_PRICE), prov


def test_the_sentence_names_what_is_sent_and_only_that():
    text = (ROOT / "docs" / "DELIVERY_REPORT.md").read_text(encoding="utf-8")
    assert PROVIDER_PRIVACY == {"zdr": True}, "تغيّر ما يُرسَل ⇒ تُصحَّح الجملةُ معه"
    assert "provider.zdr: true" in text, "الجملةُ لا تذكر ما يُرسَل"
    assert "احتفاظًا أمنيًّا" in text, "الجملةُ تُخفي احتفاظَ نقاط القارئ الأمنيّ"
    assert "data_collection" not in text, "الجملةُ تذكر حقلًا لا يُرسَل"


def test_no_switch_turns_it_off_and_no_weaker_field_rides_with_it():
    """مفتاحُ بيئةٍ يُعطّل الإرسال يجعل الوصفَ صادقًا في جهازٍ وكاذبًا في آخر."""
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
    assert "ALLOW_DATA_COLLECTION" not in src
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", "`", "-")))
    assert '"data_collection"' not in code
