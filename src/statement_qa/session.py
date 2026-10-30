"""جلسةُ الواجهة: حالتُها ومجلّدُها وملفّاتُها — **وحدةٌ واحدةٌ تُغلق مرّةً** (المرحلة ١ · شروطُ (ب) الأربعة).

**العِلّة:** كانت الواجهةُ لمستخدمٍ واحد — حالةٌ عامّةٌ واحدة (`app.STATE`) ومجلّدُ بياناتٍ دائمٌ واحد
(`DATA_HOME`) ومؤشّرُ «الكشف النشِط» فيه. فزائران على السطح العامّ يتشاركان الحالةَ والدفترَ: يرى الثاني
كشفَ الأوّل، ويمحو حذفُ أحدهما ملفّاتِ الآخر. وقرارُ المالك (G3 البند ٣ · 2026-10-28) يشترط: لا شيءَ
يُحفظ بعد الجلسة · دفترٌ ومؤقّتٌ **لكلّ جلسة** يُحذفان بانتهائها · **جلسةٌ لا ترى دفترَ جلسةٍ أخرى**.

**والحاملُ مكوّنُ المكتبة لا سجلٌّ نبنيه:** الجلسةُ تعيش في `gr.State` (حالةٌ لكلّ زائر بمعرّف جلسته)،
وتُغلق بـ`delete_callback` الذي تناديه Gradio حين تحذف حالةَ الجلسة. وهذه الوحدةُ لا تعرف Gradio:
تُختبر بلا شاشة، والتوصيلُ في `app.py`.

- **العامّة** (`public`): مجلّدُها `TemporaryDirectory` خاصٌّ بها — فيه دفترُها ومحادثتُها — يُمحى عند
  إغلاقها، ومعه نسخُ العرض التي أنتجتها في حافظة Gradio.
- **المحلّيّة** (`local`): مجلّدُ بيانات المالك الدائم (قرارُ R130: «الذاكرةُ في ملفّ العميل») — إغلاقُها
  يمحو حالتَها في الذاكرة ونسخَ العرض، ولا يمسّ قاعدةَ المالك.
"""
from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path


class Session:
    """حالةُ زائرٍ واحد (`state`) ومجلّدُه (`home`) والملفّاتُ التي أنتجها خارجه (`files`)."""

    def __init__(self, home: Path, *, owned: tempfile.TemporaryDirectory | None = None):
        self.state: dict = {}
        self.home = Path(home)
        #: رمزُ الجلسة في أسماء نسخ العرض — حافظةُ Gradio تعنون الملفَّ بمحتواه واسمه، فبلا رمزٍ
        #: تتشارك جلستان قرأتا الكشفَ نفسَه نسخةً واحدة (ويمحوها حذفُ إحداهما من تحت الأخرى).
        self.token = secrets.token_hex(4)
        self.files: set[str] = set()
        self._owned = owned
        self.closed = False

    @classmethod
    def local(cls, home) -> "Session":
        """جلسةُ المالك على جهازه — مجلّدُ بياناته الدائم، لا يُمحى بإغلاقها."""
        return cls(Path(home))

    @classmethod
    def public(cls) -> "Session":
        """جلسةُ زائرٍ على السطح العامّ — مجلّدٌ مؤقّتٌ خاصٌّ بها يُمحى بإغلاقها."""
        owned = tempfile.TemporaryDirectory(prefix="rajhi_session_")
        return cls(Path(owned.name), owned=owned)

    @property
    def ephemeral(self) -> bool:
        return self._owned is not None

    def keep(self, path) -> str:
        """يسجّل ملفًّا أنتجته الجلسةُ خارج مجلّدها (نسخةَ عرضٍ في حافظة Gradio) ليُحذف معها."""
        self.files.add(str(path))
        return str(path)

    def drop_files(self) -> tuple[int, int]:
        """يحذف ملفّاتِ الجلسة **وحدَها** ويعدّ: (ما حُذف، ما بقي). الغائبُ أصلًا لا يُعدّ محذوفًا."""
        removed = 0
        for f in sorted(self.files):
            try:
                os.unlink(f)
                removed += 1
            except FileNotFoundError:
                pass
            except OSError:
                continue                      # يبقى في القائمة فيُعدّ «بقي» — لا يُبتلع
        self.files = {f for f in self.files if os.path.exists(f)}
        return removed, len(self.files)

    def close(self) -> dict:
        """ينهي الجلسة: الحالةُ في الذاكرة · ملفّاتُها · وفي العامّة حافظةُ المحادثة ومجلّدُها كلُّه.

        **والترتيبُ مقصود:** حافظةُ المحادثة (`qa.reset_memory`) تُغلق **قبل** محو المجلّد — متّصلٌ
        مفتوحٌ يُعيد إنشاء `-wal` بعد الحذف (درسُ زرّ الحذف في R130). ويُعاد عدُّ ما بقي، فلا يُدَّعى
        محوٌ بلا عدّ.
        """
        if self.closed:
            return {"files_left": 0, "home_left": False}
        self.state.clear()
        _removed, files_left = self.drop_files()
        home_left = False
        if self._owned is not None:
            from statement_qa.qa import reset_memory   # noqa: PLC0415 — يفتح LangGraph عند الحاجة وحدها

            for db in self.home.rglob("*.sqlite"):
                reset_memory(db)
            self._owned.cleanup()
            home_left = self.home.exists()
        self.closed = True
        return {"files_left": files_left, "home_left": home_left}
