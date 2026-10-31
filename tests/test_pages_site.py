"""The public story page (site/) tells the truth about where its numbers come from.

docs/SHOWCASE_PLAN.md section 6, «شرطُ الصدق», as the owner rewrote it on 2026-10-31: the story is ONE page of a
real statement («ما ابغى كشف اصطناعي ابدا هنا»), its amounts visible, published with the account holder's consent,
cropped and boxed (tools/publish_real_page.py); the section on the whole statement shows its guarded aggregates;
and the synthetic statement appears only behind the «try» button. The page reads every number at load time from a
tracked file, so no figure may be typed into it. The real page is pinned here, so any edit to it fails first in
this file. The live site changes only when someone publishes it (section 4, condition 1), and every title a person
reads carries the registered name (section 6b).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
MEASURED = ROOT / "docs" / "measurements"
SPACE_URL = "https://huggingface.co/spaces/jahfaliabdulrahman-dev/arabic-statement-reader"
OFFICIAL_NAME = "AI Bank Statement Auditor"

#: Each data file the page reads, and the tracked source it must be a link to (a copy would drift).
SOURCES = {
    "page.json": MEASURED / "real-page-43.json",
    "pypdfloader.json": MEASURED / "real-pypdfloader.json",
    "plain-read.json": MEASURED / "real-plain-read.json",
    "claims.json": ROOT / "docs" / "claims.json",
}
#: The one real page (section 6): its bytes as the owner approved them. Re-running the tool on new inputs fails here.
REAL_PAGE_SHA256 = "5c3b641f2bbf36b301e52ad7621fb218cdf5b5f332d3c828054cc448877e993a"
#: The only pictures on the page: the two crops of that page, each declared with its md5 for a visual check.
REAL_IMAGES = {"real-rows.png", "real-row.png"}

#: A figure typed by hand: an amount with two decimals, or any Arabic-Indic digit.
_TYPED_FIGURE = re.compile(r"\d[\d,]*\.\d{2}|[٠-٩]")
#: Attributes a reader sees or hears (the seal's drawing attributes are geometry, not figures).
_READ_ATTRS = {"alt", "aria-label", "title", "content"}


def _page_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SITE.glob("*")) if p.suffix in {".html", ".js", ".css"}}


def _what_a_reader_meets() -> dict[str, list[str]]:
    """The page's words as a visitor meets them: HTML text and read attributes, the strings app.js writes,
    and the `content:` CSS draws. Geometry (SVG coordinates, CSS lengths) is not text and is left out."""
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            self.skip += tag in {"script", "style"}
            self.out += [v for k, v in attrs if k in _READ_ATTRS and v]

        def handle_endtag(self, tag):
            self.skip -= tag in {"script", "style"}

        def handle_data(self, data):
            if not self.skip:
                self.out.append(data)

    parser = Text()
    parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
    js = (SITE / "app.js").read_text(encoding="utf-8")
    css = (SITE / "style.css").read_text(encoding="utf-8")
    return {"index.html": parser.out,
            "app.js": [a or b for a, b in re.findall(r'"([^"\n]*)"|`([^`]*)`', js)],
            "style.css": re.findall(r"content:\s*([^;]+);", css)}


def _read(name: str) -> dict:
    return json.loads(SOURCES[name].read_text(encoding="utf-8"))


def test_every_number_source_is_a_link_to_its_tracked_file():
    js = (SITE / "app.js").read_text(encoding="utf-8")
    for name, source in SOURCES.items():
        link = SITE / name
        assert link.is_symlink(), f"{name}: نسخةٌ لا رابط — نسختان تفترقان"
        assert link.resolve() == source.resolve(), name
        assert f'"{name}"' in js, f"app.js لا يقرأ {name}"


def test_every_number_on_the_page_comes_from_the_same_statement():
    page, loader, claims = _read("page.json"), _read("pypdfloader.json"), _read("claims.json")
    assert loader["source_sha256"] == page["source_sha256"], "المحمّلُ قِيس على كشفٍ غير كشف الصفحة"
    assert all(run["source_sha256"] == page["source_sha256"] for run in _read("plain-read.json")["runs"])
    assert loader["documents"] == page["n_pages"] == claims["pages"], "الأرقامُ الإجماليّةُ لكشفٍ آخر"


def test_the_real_page_is_one_page_pinned_and_redacted():
    """Section 6: one page, by the owner's word; the names, references and card numbers hidden as in the picture."""
    from publish_guard import TEXT_RULES

    raw = SOURCES["page.json"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REAL_PAGE_SHA256, (
        "الصفحةُ الحقيقيّةُ تغيّرت — تُعرض على المالك قبل أن يُحدَّث هذا الثابت")
    page = json.loads(raw)
    assert {r["page"] for r in page["rows"]} == {page["page"]}, "صفوفٌ من غير الصفحة الواحدة"
    assert set(page["footer"]) == {"verdict", "basis"}, "مجاميعُ الذيل تبقى خارج الصفحة"
    for r in page["rows"]:
        assert not re.search(r"[0-9٠-٩۰-۹*]{5,}", r["desc"]), f"صفّ {r['seq']}: مرجعٌ أو رقمُ بطاقةٍ ظاهر"
        for rule, level, rx, _ in TEXT_RULES:
            assert level != "BLOCK" or not rx.search(r["desc"]), f"صفّ {r['seq']}: {rule}"
    assert {p.name for p in SITE.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}} \
        == REAL_IMAGES
    declared = (ROOT / "docs" / "security" / "tracked-binaries.txt").read_text(encoding="utf-8")
    for name in REAL_IMAGES:
        md5 = hashlib.md5((SITE / name).read_bytes()).hexdigest()
        assert re.search(rf"^site/{re.escape(name)} .*md5 {md5}$", declared, re.M), f"{name} غيرُ مُعلَنٍ ببصمته"


def test_no_figure_is_typed_into_the_page():
    typed = {name: sorted({f for text in texts for f in _TYPED_FIGURE.findall(text)})
             for name, texts in _what_a_reader_meets().items()}
    typed = {name: found for name, found in typed.items() if found}
    assert typed == {}, f"أرقامٌ مكتوبةٌ باليد في الصفحة (تُقرأ من مصادرها لا تُكتب): {typed}"


def test_each_kind_of_number_says_where_it_comes_from():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "من صفحةٍ واحدةٍ من كشف حسابٍ حقيقيّ، نُشرت بموافقة صاحبه" in html
    assert "أرقامٌ إجماليّةٌ من قراءة الكشف نفسه كاملًا" in html
    footer = html[html.index("<footer>"):]
    assert "من صفحةٍ واحدةٍ من كشف حسابٍ حقيقيّ نُشرت بموافقة صاحبه" in footer
    assert "وزرُّ التجربة يفتح كشفًا اصطناعيًّا" in footer


def test_the_plain_read_is_the_systems_model_and_stayed_in_its_budget():
    """The page says the same model the system reads with: a model change makes that false until re-measured.
    The model's answers stay on the owner's machine: the tracked record holds counts only."""
    source = (ROOT / "src" / "statement_qa" / "vlm_reader.py").read_text(encoding="utf-8")
    model = re.search(r'MODEL = os\.environ\.get\("OPENROUTER_MODEL_VLM", "([^"]+)"\)', source).group(1)
    runs = _read("plain-read.json")["runs"]
    assert runs, "لا قياسَ مسجَّل"
    page = _read("page.json")
    assert sum(run["spent"] for run in runs) <= runs[0]["budget"], "تجاوز القياسُ السقفَ الذي وافق عليه المالك"
    for run in runs:
        assert run["model"] == model, f"قِيس بـ{run['model']} والنظامُ يقرأ بـ{model} ⇒ أعِد القياس"
        assert run["pages_read"] == [page["page"]], "قِيس على غير صفحة القصّة"
        assert run["rows_kept"] == "elsewhere" and not any("returned_rows" in p for p in run["pages"]), (
            "أرقامُ الصفحة الحقيقيّة كما أعادها النموذج دخلت المستودع")


def test_the_story_names_no_local_file_and_no_synthetic_statement():
    """The owner: «ما ابغى كشف اصطناعي ابدا هنا» — the synthetic statement lives behind the «try» button only."""
    for name, text in _page_sources().items():
        for banned in ("local_sample", "sample_10p", "data/statements", "slice_629p_v2", "/Users/",
                       "statement_showcase", "statement_sample"):
            assert banned not in text, f"{name} يذكر {banned}"


def test_every_title_a_person_reads_carries_the_registered_name():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert f"<title>{OFFICIAL_NAME}</title>" in html
    assert re.search(rf"<h1[^>]*>{OFFICIAL_NAME}</h1>", html)
    space = yaml.safe_load((ROOT / "space" / "README.md").read_text(encoding="utf-8").split("---")[1])
    assert space["title"] == OFFICIAL_NAME
    assert (ROOT / "README.md").read_text(encoding="utf-8").startswith(f"# {OFFICIAL_NAME}")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert f"<h1>{OFFICIAL_NAME}</h1>" in app
    assert f'gr.Blocks(title="{OFFICIAL_NAME}"' in app


def test_the_seal_is_set_in_noto_naskh_arabic():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "font-family=\"'Noto Naskh Arabic', serif\"" in html
    assert "family=Noto+Naskh+Arabic" in html
    assert "Amiri" not in html


def test_the_gateway_opens_the_space():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert html.count(f'href="{SPACE_URL}"') == 2


def test_the_scanned_page_image_and_the_architecture_are_described():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for src in re.findall(r'<img src="([^"]+)"', html):
        assert (SITE / src).is_file(), src
    assert not re.search(r"<img(?![^>]*\balt=\"[^\"]+\")[^>]*>", html, re.S), "صورةٌ بلا وصف"
    assert re.search(r'<ol class="flow" aria-label="[^"]+">', html), "مخطّطُ المعماريّة بلا وصف"


def test_the_live_site_changes_only_when_someone_publishes_it():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    triggers = wf.get("on", wf.get(True))
    assert list(triggers) == ["workflow_dispatch"], f"الموقعُ الحيّ يُنشر بغير يدٍ: {triggers}"
    steps = wf["jobs"]["deploy"]["steps"]
    assert all("run" not in step for step in steps)
    upload = next(step for step in steps if step.get("uses", "").startswith("actions/upload-pages-artifact@"))
    assert upload["with"]["path"] == "site"
    assert all(re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"]) for step in steps), (
        "كلُّ إجراءٍ مثبَّتٌ ببصمة التزامه لا بوسمٍ يتحرّك")
