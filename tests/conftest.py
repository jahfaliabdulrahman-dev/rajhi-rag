import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


import pytest

#: **بياناتُ المستخدم في الاختبار معزولة (R130):** التطبيقُ صار يكتب قاعدةَ الكشف في مجلّد بيانات
#: المستخدم (`~/Library/Application Support/rajhi-rag`)، وبلا عزلٍ تكتب الضوابطُ بياناتٍ حقيقيّةً
#: في مجلّد المالك. يُضبط المتغيّرُ **قبل استيراد `app`** (يقرؤه عند الاستيراد)، ويُنظَّف عند الخروج.
_TEST_HOME = Path(tempfile.mkdtemp(prefix="rajhi_test_home_"))
os.environ["RAJHI_DATA_HOME"] = str(_TEST_HOME)
atexit.register(shutil.rmtree, _TEST_HOME, ignore_errors=True)
#: **والسطحُ في الضوابط محلّيٌّ صراحةً (المرحلة ١):** التطبيقُ يفترض السطحَ العامّ (فشلٌ مُغلَق) فيطلب
#: مفتاحَ الزائر؛ والضوابطُ القائمة تقيس سطحَ المالك المحلّيّ، وضوابطُ السطح العامّ تضبط `app.SURFACE`
#: بنفسها في كلّ ضابط. والقيمةُ تُفرَض لا تُقترح، فلا يغيّر متغيّرٌ في بيئة الطرفيّة ما يقيسه الضابط.
os.environ["RAJHI_SURFACE"] = "local"


@pytest.fixture(autouse=True)
def _no_real_data_left_behind(tmp_path):
    """**لا تُترك نسخةٌ من بيانات المالك في مجلّدٍ مؤقّت** (مراجعة ٩١ · الإصلاحُ المطلوب ②).

    **العِلّة المقيسة:** ضابطٌ يبني دفترًا من بيانات المالك يستعمل `tmp_path` — وهو تحت `TMPDIR`
    (مخدعُ الجلسة) ويبقى ثلاثَ جولاتٍ بعد التشغيل ⇒ فبقيت **سبعُ نسخٍ كاملةٍ** (5809 صفًّا · 3.7MB
    لكلّ نسخة) خارجَ المجلّد المحميّ، لم يذكرها تقرير. وُجدت في مراجعة ٩١ وحُذفت بجردٍ، **وهذا
    الضابطُ يمنع تكرارَها**: يُزيل ما بُني من قواعدَ في مجلّد الاختبار فورًا بعده.

    **وحدُّه:** يُزيل ملفّات `*.sqlite*` تحت مجلّد الاختبار وحدَه — ولا يمسّ `data/ledgers/` في الشجرة.
    **وأُضيف في R130:** كلُّ ضابطٍ يحصل على مجلّدِ بياناتِ مستخدمٍ خاصٍّ به (`tmp_path/userdata`)،
    فيُقاس ما يكتبه التطبيقُ بلا أن يُلوّث مجلّدَ المالك ولا مجلّدَ ضابطٍ آخر.
    """
    home = tmp_path / "userdata"
    home.mkdir(parents=True, exist_ok=True)
    old_env = os.environ.get("RAJHI_DATA_HOME")
    os.environ["RAJHI_DATA_HOME"] = str(home)
    if "app" in sys.modules:                     # الاستيرادُ وقع سابقًا ⇒ الحالةُ تُصحَّح هنا
        sys.modules["app"].DATA_HOME = home
        sys.modules["app"].LOCK_PATH = home / "job.lock"
    yield
    if old_env is None:
        os.environ.pop("RAJHI_DATA_HOME", None)
    else:
        os.environ["RAJHI_DATA_HOME"] = old_env
    for f in tmp_path.rglob("*.sqlite*"):
        try:
            f.unlink()
        except OSError:                      # ملفٌّ قيد الفتح على نظامٍ يمنع الحذف ⇒ يُعلَن لا يُسكَت
            print(f"تعذّر حذفُ {f.name} — يُفحَص يدويًّا")
