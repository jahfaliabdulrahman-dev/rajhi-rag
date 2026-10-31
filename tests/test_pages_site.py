"""The public story page (site/) tells the truth about where its numbers come from.

docs/SHOWCASE_PLAN.md section 6, «شرطُ الصدق»: every number on the page comes from the ledger the system
wrote when it read the synthetic statement, the line «الأرقام من كشفٍ اصطناعيّ قرأه النظام» stands under
it, and the owner's own statement never appears. The page reads its numbers at load time from that
ledger, so no figure may be typed into it. And the live site changes only when someone publishes it
(section 4, condition 1): the Pages workflow starts by hand and nothing else.
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


def test_the_numbers_come_from_the_systems_ledger_of_the_synthetic_statement():
    link = SITE / "statement_showcase.ledger.json"
    assert link.is_symlink(), "الصفحةُ تقرأ نسخةً من الدفتر لا الدفترَ نفسَه: نسختان تفترقان"
    assert link.resolve() == LEDGER.resolve()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    pdf = LEDGER.with_name(ledger["source"])
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == ledger["source_sha256"], (
        "الدفترُ لا يطابق بايتاتِ الكشف الاصطناعيّ المتتبَّع")
    assert 'const LEDGER = "statement_showcase.ledger.json";' in (SITE / "app.js").read_text(encoding="utf-8")


def test_no_figure_is_typed_into_the_page():
    typed = {name: sorted({f for text in texts for f in _TYPED_FIGURE.findall(text)})
             for name, texts in _what_a_reader_meets().items()}
    typed = {name: found for name, found in typed.items() if found}
    assert typed == {}, f"أرقامٌ مكتوبةٌ باليد في الصفحة (تُقرأ من الدفتر لا تُكتب): {typed}"


def test_the_source_line_stands_under_the_story():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "الأرقام من كشفٍ اصطناعيّ قرأه النظام." in html
    assert html.index("الأرقام من كشفٍ اصطناعيّ قرأه النظام") > html.index('id="beat-tower"')


def test_the_owners_statement_is_never_on_the_page():
    for name, text in _page_sources().items():
        for banned in ("local_sample", "sample_10p", "data/statements"):
            assert banned not in text, f"{name} يذكر {banned}"


def test_the_seal_is_set_in_noto_naskh_arabic():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "font-family=\"'Noto Naskh Arabic', serif\"" in html
    assert "family=Noto+Naskh+Arabic" in html
    assert "Amiri" not in html


def test_the_gateway_opens_the_space():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert html.count(f'href="{SPACE_URL}"') == 2


def test_the_scanned_page_image_is_described():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for src in re.findall(r'<img src="([^"]+)"', html):
        assert (SITE / src).is_file(), src
    assert not re.search(r"<img(?![^>]*\balt=\"[^\"]+\")[^>]*>", html, re.S), "صورةٌ بلا وصف"


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
