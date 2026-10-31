"""The public story page (site/) tells the truth about where its numbers come from.

docs/SHOWCASE_PLAN.md section 6, «شرطُ الصدق»: the story's numbers come from the ledger the system wrote when
it read the synthetic statement, the measured-results section from the guarded aggregates of the real run
(widened on the owner's word, 2026-10-31), and the owner's own statement never appears. The page reads every
number at load time from a tracked file, so no figure may be typed into it. The live site changes only when
someone publishes it (section 4, condition 1), and every title a person reads carries the registered name
(section 6b).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
LEDGER = ROOT / "data" / "sample" / "statement_showcase.ledger.json"
SPACE_URL = "https://huggingface.co/spaces/jahfaliabdulrahman-dev/arabic-statement-reader"
OFFICIAL_NAME = "AI Bank Statement Auditor"

#: Each data file the page reads, and the tracked source it must be a link to (a copy would drift).
SOURCES = {
    "statement_showcase.ledger.json": LEDGER,
    "pypdfloader.json": ROOT / "docs" / "measurements" / "pypdfloader.json",
    "plain-read.json": ROOT / "docs" / "measurements" / "plain-read.json",
    "claims.json": ROOT / "docs" / "claims.json",
}

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


def test_every_number_source_is_a_link_to_its_tracked_file():
    js = (SITE / "app.js").read_text(encoding="utf-8")
    for name, source in SOURCES.items():
        link = SITE / name
        assert link.is_symlink(), f"{name}: نسخةٌ لا رابط — نسختان تفترقان"
        assert link.resolve() == source.resolve(), name
        assert f'"{name}"' in js, f"app.js لا يقرأ {name}"
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    pdf = LEDGER.with_name(ledger["source"])
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == ledger["source_sha256"], (
        "الدفترُ لا يطابق بايتاتِ الكشف الاصطناعيّ المتتبَّع")


def test_no_figure_is_typed_into_the_page():
    typed = {name: sorted({f for text in texts for f in _TYPED_FIGURE.findall(text)})
             for name, texts in _what_a_reader_meets().items()}
    typed = {name: found for name, found in typed.items() if found}
    assert typed == {}, f"أرقامٌ مكتوبةٌ باليد في الصفحة (تُقرأ من مصادرها لا تُكتب): {typed}"


def test_each_kind_of_number_says_where_it_comes_from():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "من كشفٍ اصطناعيّ قرأه النظام" in html
    assert "أرقامٌ إجماليّةٌ من قراءة كشفٍ حقيقيّ لصاحب المشروع، ولا رقمَ هنا من صفوفه" in html
    footer = html[html.index("<footer>"):]
    assert "الأرقام من كشفٍ اصطناعيّ قرأه النظام" in footer


def test_the_plain_read_is_the_systems_model_and_stayed_in_its_budget():
    """The page says the same model the system reads with: a model change makes that false until re-measured."""
    source = (ROOT / "src" / "statement_qa" / "vlm_reader.py").read_text(encoding="utf-8")
    model = re.search(r'MODEL = os\.environ\.get\("OPENROUTER_MODEL_VLM", "([^"]+)"\)', source).group(1)
    runs = json.loads(SOURCES["plain-read.json"].read_text(encoding="utf-8"))["runs"]
    assert runs, "لا قياسَ مسجَّل"
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for run in runs:
        assert run["model"] == model, f"قِيس بـ{run['model']} والنظامُ يقرأ بـ{model} ⇒ أعِد القياس"
        assert run["spent"] <= run["budget"]
        assert run["source_sha256"] == ledger["source_sha256"], "قِيس على كشفٍ غير الكشف المتتبَّع"
    loader = json.loads(SOURCES["pypdfloader.json"].read_text(encoding="utf-8"))
    assert loader["documents"] == ledger["n_pages"]


def test_the_owners_statement_is_never_on_the_page():
    for name, text in _page_sources().items():
        for banned in ("local_sample", "sample_10p", "data/statements"):
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
