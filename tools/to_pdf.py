#!/usr/bin/env python3
"""Markdown → Arabic/RTL PDF (Chrome headless) — simple mode and house mode.

Why Chrome: fpdf2 has no true Arabic shaping (letters come out disconnected) and
WeasyPrint needs a pango fix on macOS. Chrome prints `dir="rtl"` HTML with correct
glyph shaping and margins, with no font hacks.

Two modes:

  simple (default)  markdown → HTML → PDF. Quick internal documents.
  --house           the house gold standard: one embedded font family in five
                    weights, a dark cover carrying the seal and the project line,
                    a real contents page, a running footer, page numbers in Latin
                    digits, a bookmark sidebar, and four live navigation buttons
                    on every content page (never on the cover). Then it VERIFIES
                    the artifact by reading the PDF back — page count, outline,
                    every link's own target (a self-link is a failure, not a
                    detail), embedded fonts — because a bookmark that opens on
                    the wrong page fails on first click, not in review.

    python3 tools/to_pdf.py --md docs/WHO_IS_THIS_FOR.md --out brief.pdf --house \
        --title "…" --subtitle "…" --slogan "…"
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONTS_DIR = PROJ / "assets" / "fonts"
FONTS_CSS = FONTS_DIR / "fonts.css"

# Design tokens — the house palette (royal violet / deep cosmic / teal accent)
PALETTE = {
    "cosmic_1": "#020018", "cosmic_2": "#150a58", "cosmic_3": "#1a0b70",
    "violet": "#571cbd", "violet_el": "#6d3ff0", "teal": "#79e9e0",
    "light": "#f8f6fb", "body": "#1c1c2e", "secondary": "#4f5d75",
    "muted": "#a4a2a7", "hairline": "#d9dee9",
}
NAV_Y = (37.0, 62.0)                       # vertical band of the nav strip (pt)
NAV_X = (58.0, 95.0, 133.0, 170.0)         # next · prev · contents · home


# ————————————————————————— markdown → HTML —————————————————————————

def inline(text: str) -> str:
    """Bold, inline code — and HTML-escape everything else."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def render_body(md_text: str) -> tuple[str, list[tuple[int, str]]]:
    """Markdown body → (HTML, headings). Headings drive the contents page."""
    parts: list[str] = []
    headings: list[tuple[int, str]] = []
    lines = md_text.splitlines()
    i = 0
    table: list[str] = []
    list_tag: str | None = None

    def close_table() -> None:
        if not table:
            return
        rows = [r for r in table if not re.match(r"^\s*\|[\s:|-]+\|\s*$", r)]
        parts.append("<table>")
        for n, row in enumerate(rows):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tag = "th" if n == 0 else "td"
            parts.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells)
                         + "</tr>")
        parts.append("</table>")
        table.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            parts.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i].rstrip()
        if line.lstrip().startswith("|"):
            close_list()
            table.append(line)
            i += 1
            continue
        close_table()
        stripped = line.strip()
        if not stripped:
            close_list()
        elif stripped.startswith("### "):
            close_list()
            headings.append((3, stripped[4:]))
            parts.append(f"<h3>{inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            close_list()
            headings.append((2, stripped[3:]))
            parts.append(f"<h2>{inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            close_list()
            headings.append((1, stripped[2:]))
            parts.append(f"<h1>{inline(stripped[2:])}</h1>")
        elif stripped.startswith("> "):
            close_list()
            parts.append(f"<blockquote><p>{inline(stripped[2:])}</p></blockquote>")
        elif stripped in ("---", "***", "___"):
            close_list()
            parts.append('<hr class="rule">')
        elif re.match(r"^\d+\.\s", stripped):
            if list_tag != "ol":
                close_list()
                parts.append("<ol>")
                list_tag = "ol"
            item = re.sub(r"^\d+\.\s", "", stripped)
            parts.append(f"<li>{inline(item)}</li>")
        elif stripped.startswith("- "):
            if list_tag != "ul":
                close_list()
                parts.append("<ul>")
                list_tag = "ul"
            parts.append(f"<li>{inline(stripped[2:])}</li>")
        else:
            close_list()
            parts.append(f"<p>{inline(stripped)}</p>")
        i += 1
    close_table()
    close_list()
    return "\n".join(parts), headings


SIMPLE_CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body { font-family: ".SF Arabic", "GeezaPro", "Damascus", sans-serif;
       color: #1c1c2e; font-size: 10.5pt; line-height: 1.85; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4mm; color: #12224a; }
h2 { font-size: 13.5pt; margin: 8mm 0 2mm; color: #12224a;
     border-bottom: 1.2pt solid #d9dee9; padding-bottom: 1.5mm; }
h3 { font-size: 11.5pt; margin: 5mm 0 1.5mm; }
p { margin: 0 0 3mm; text-align: justify; }
ul, ol { margin: 0 0 3mm; padding-inline-start: 6mm; }
li { margin-bottom: 1.5mm; }
blockquote { margin: 3mm 0; padding: 3mm 4mm; background: #f4f6fa;
             border-inline-start: 3pt solid #12224a; border-radius: 2pt; }
blockquote p:last-child { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 4mm; font-size: 9.5pt; }
th, td { border: 0.6pt solid #c9d0dc; padding: 2mm 2.5mm; text-align: start;
         vertical-align: top; }
th { background: #12224a; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #f7f9fc; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 9pt;
       background: #eef1f6; padding: 0 1mm; border-radius: 2pt;
       direction: ltr; unicode-bidi: embed; }
hr { border: none; border-top: 0.8pt solid #d9dee9; margin: 6mm 0; }
strong { color: #0d1a38; }
"""


def render(md_text: str, title: str) -> str:
    """Simple mode: standalone HTML. The generic path (tests use this)."""
    body, _ = render_body(md_text)
    return ('<!DOCTYPE html>\n<html lang="ar" dir="rtl">\n<head>\n'
            '<meta charset="UTF-8">'
            f"<title>{html.escape(title)}</title>"
            f"<style>{SIMPLE_CSS}</style></head><body>{body}</body></html>")


# ————————————————————————— house mode —————————————————————————

def fonts_css_inlined() -> str:
    """Base64-embed the woff2 files: deterministic print, no network, no fallback."""
    if not FONTS_CSS.exists():
        return ""
    css = FONTS_CSS.read_text(encoding="utf-8")

    def to_data_uri(match: re.Match) -> str:
        path = FONTS_DIR / match.group(1)
        if not path.exists():
            return match.group(0)
        data = base64.b64encode(path.read_bytes()).decode()
        return f"url(data:font/woff2;base64,{data}) format('woff2')"

    return re.sub(r"url\('([^']+\.woff2)'\)\s*format\('woff2'\)", to_data_uri, css)


HOUSE_CSS = """
@page { size: A4; margin: 21.5mm 21.5mm 24mm 21.5mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: "IBM Plex Sans Arabic", ".SF Arabic", sans-serif;
       color: %(body)s; font-size: 12pt; line-height: 1.9; direction: rtl; }

.cover { position: relative; height: 250mm; width: 167mm;
         background: linear-gradient(160deg, %(cosmic_1)s 0%%, %(cosmic_2)s 55%%, %(cosmic_3)s 100%%);
         color: #fff; padding: 32mm 20mm 22mm; page-break-after: always;
         border-radius: 3mm; overflow: hidden; }
.cover .logo { display: flex; align-items: center; gap: 4mm; margin-bottom: 22mm; }
.cover .logo .mark { width: 12mm; height: 12mm; border-radius: 50%%;
         border: 1.4pt solid %(teal)s; display: flex; align-items: center;
         justify-content: center; color: %(teal)s; font-weight: 700; font-size: 13pt; }
.cover .logo .name { font-size: 11pt; color: #cfd0ff; }
/* white on the dark page — the content rule must not paint the cover title */
.cover h1 { font-size: 30pt; font-weight: 700; line-height: 1.35; margin: 0 0 6mm;
            color: #ffffff; }
.cover .sub { font-size: 13pt; font-weight: 300; color: #cfd0ff; margin-bottom: 13mm; }
.cover .slogan { font-size: 12.5pt; font-weight: 300; color: %(teal)s; line-height: 2;
                 border-inline-start: 2pt solid %(teal)s; padding-inline-start: 5mm;
                 margin-bottom: 14mm; }
.cover .meta { font-size: 9pt; color: #9fa8d8; position: absolute; bottom: 20mm; }
.cover .stamp { position: absolute; bottom: 22mm; left: 18mm; }

.toc { page-break-after: always; }
.toc h2 { font-size: 18pt; color: %(violet)s; margin: 0 0 6mm; }
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li { font-size: 11.5pt; padding: 2.4mm 0; border-bottom: .5pt solid %(hairline)s;
          display: flex; justify-content: space-between; }
.toc .n { color: %(muted)s; font-size: 10pt; }

h1 { font-size: 20pt; font-weight: 700; color: %(violet)s; margin: 0 0 4mm; }
h2 { font-size: 18pt; font-weight: 600; color: %(violet)s; margin: 9mm 0 3mm;
     padding-bottom: 2mm; border-bottom: 1pt solid %(hairline)s; }
h3 { font-size: 12pt; font-weight: 600; color: %(violet_el)s; margin: 5mm 0 2mm; }
p { margin: 0 0 3.4mm; text-align: justify; }
ul, ol { padding-inline-start: 6mm; margin: 0 0 3.4mm; }
li { margin-bottom: 1.6mm; }
blockquote { margin: 3.4mm 0; padding: 3.4mm 4.5mm; background: #f2effc;
             border-inline-start: 3pt solid %(violet_el)s; border-radius: 2pt;
             font-size: 11pt; color: #2a2450; }
blockquote p:last-child { margin-bottom: 0; }
table { width: 100%%; border-collapse: collapse; margin: 3.4mm 0 4.5mm; font-size: 10.5pt; }
th, td { border: .5pt solid %(hairline)s; padding: 2.2mm 2.6mm; text-align: start;
         vertical-align: top; }
th { background: %(violet)s; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #f6f4fd; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 9.5pt; background: #efedf8;
       padding: 0 1mm; border-radius: 2pt; direction: ltr; unicode-bidi: embed; }
strong { font-weight: 600; color: #1b1436; }
.rule { border: none; border-top: .6pt solid %(hairline)s; margin: 7mm 0; }

/* a fixed element repeats on every printed page in Chrome — the running footer */
.foot { position: fixed; bottom: -16mm; right: 0; left: 0; font-size: 8pt;
        font-weight: 300; color: %(secondary)s; display: flex;
        justify-content: space-between; border-top: .5pt solid %(hairline)s;
        padding-top: 2mm; }
""" % PALETTE


def stamp_svg(size_mm: float = 38) -> str:
    """The project seal: ring, the promise inside, the line around it."""
    return f"""
<svg class="stamp" width="{size_mm}mm" height="{size_mm}mm" viewBox="0 0 200 200">
  <defs><path id="arc" d="M 100,100 m -79,0 a 79,79 0 1,1 158,0 a 79,79 0 1,1 -158,0"/></defs>
  <circle cx="100" cy="100" r="95" fill="none" stroke="{PALETTE['teal']}" stroke-width="2.2"/>
  <circle cx="100" cy="100" r="84" fill="none" stroke="{PALETTE['teal']}"
          stroke-width="0.9" stroke-dasharray="4 4"/>
  <text fill="{PALETTE['teal']}" font-size="17" font-weight="600"
        font-family="IBM Plex Sans Arabic" letter-spacing="0.4">
    <textPath href="#arc" startOffset="50%" text-anchor="middle">إثبات لا تخمين</textPath>
  </text>
  <text x="100" y="93" text-anchor="middle" fill="#ffffff" font-size="24"
        font-family="IBM Plex Sans Arabic" font-weight="700">الرقم أمانة</text>
  <text x="100" y="115" text-anchor="middle" fill="{PALETTE['teal']}" font-size="11"
        font-family="IBM Plex Sans Arabic">سلسلة رصيدية هي الحَكَم</text>
  <line x1="66" y1="128" x2="134" y2="128" stroke="{PALETTE['teal']}" stroke-width="0.9"/>
  <text x="100" y="146" text-anchor="middle" fill="#cfd0ff" font-size="10"
        font-family="IBM Plex Sans Arabic">لا قراءة بلا دليل مطبوع</text>
</svg>"""


def house_html(title: str, subtitle: str, slogan: str, body: str,
               toc: list[tuple[str, int]] | None, meta: str) -> str:
    """The document: dark cover, contents, content, running footer."""
    toc_html = ""
    if toc:
        rows = "".join(f'<li><span>{html.escape(text)}</span>'
                       f'<span class="n">{page}</span></li>' for text, page in toc)
        toc_html = f'<section class="toc"><h2>المحتويات</h2><ol>{rows}</ol></section>'
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>{fonts_css_inlined()}
{HOUSE_CSS}</style></head><body>
<section class="cover">
  <div class="logo"><span class="mark">خ</span>
    <span class="name">مشروع قراءة الكشوف — إثبات لا تخمين</span></div>
  <h1>{html.escape(title)}</h1>
  <div class="sub">{html.escape(subtitle)}</div>
  <div class="slogan">{html.escape(slogan)}</div>
  <div class="meta">{html.escape(meta)}</div>
  {stamp_svg()}
</section>
{toc_html}
<main>{body}</main>
<div class="foot"><span>{html.escape(title)}</span><span>{html.escape(subtitle)}</span></div>
</body></html>"""


def print_pdf(html_path: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
         f"--print-to-pdf={out}", "--no-pdf-header-footer",
         html_path.as_uri()],
        capture_output=True, text=True, timeout=180)


# ————————————————————————— post-pass + verification —————————————————————————

def _letters(text: str):
    """Letter multiset, ignoring order, spaces, digits and diacritics.

    Chrome's Arabic text layer is written in VISUAL order and unshaped, so the
    extracted string of «لمن بُني هذا» reads like «َُي لم ولمن — هذا ُبين لمن».
    A phrase search therefore fails or, worse, matches the wrong page. Counting
    the letters is order-independent, which makes it the one comparison that
    survives the scrambled layer.
    """
    from collections import Counter

    out: Counter = Counter()
    for ch in text:
        if ch.isalpha() and not (0x064B <= ord(ch) <= 0x0652 or ord(ch) == 0x0670):
            out[ch] += 1
    return out


def heading_pages(doc, headings: list[tuple[int, str]], start: int = 0) -> list[int]:
    """Locate each heading by LAYOUT (its font size) and letter content.

    Text search is unreliable on this layer, so the heading is identified by the
    span's size (headings are printed larger than body text) and confirmed by its
    letters. `start` skips the cover and the contents page: both repeat headings,
    and a contents page that lies about its own numbers is worse than none.
    """
    found_pages: list[int] = []
    fallback = start
    for level, text in headings:
        target = _letters(text)
        min_size = 15.0 if level <= 2 else 11.5     # h1/h2 are large; h3 is body-sized
        best: tuple[float, int] | None = None
        for i in range(start, doc.page_count):
            for block in doc[i].get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["size"] < min_size or not span["text"].strip():
                            continue
                        span_letters = _letters(span["text"])
                        if not span_letters or not target:
                            continue
                        shared = sum((span_letters & target).values())
                        score = shared / max(sum(target.values()), 1)
                        if score >= 0.8 and (best is None or score > best[0]):
                            best = (score, i)
        if best is None:
            found_pages.append(fallback)
        else:
            found_pages.append(best[1])
            fallback = best[1]
    return found_pages


def house_finish(pdf: Path, headings: list[tuple[int, str]], *,
                 contents_page: int, cover_pages: int = 1) -> dict:
    """Bookmarks, nav icons + live links, page numbers — then read it all back."""
    import pymupdf

    doc = pymupdf.open(pdf)
    first_content = cover_pages + (1 if contents_page else 0)
    pages = heading_pages(doc, headings, start=first_content)
    outline = [[1, "الغلاف", 1]]
    if contents_page:
        outline.append([1, "المحتويات", contents_page + 1])
    outline += [[min(level, 3), text, page + 1]
                for (level, text), page in zip(headings, pages)]
    doc.set_toc(outline)

    icon = pymupdf.utils.getColor(PALETTE["violet_el"])
    rule = pymupdf.utils.getColor(PALETTE["hairline"])
    number_color = pymupdf.utils.getColor(PALETTE["secondary"])
    width = doc[0].rect.width
    covered = 0
    for i in range(first_content, doc.page_count):
        page = doc[i]
        y0, y1 = NAV_Y
        for n, x in enumerate(NAV_X):
            page.draw_rect(pymupdf.Rect(x, y0, x + 25, y1), color=icon, width=0.7,
                           radius=0.15)
            cx, cy = x + 12.5, (y0 + y1) / 2
            if n == 0:                        # next ›
                page.draw_line((cx - 2, cy - 3), (cx + 2, cy), color=icon)
                page.draw_line((cx + 2, cy), (cx - 2, cy + 3), color=icon)
            elif n == 1:                      # prev ‹
                page.draw_line((cx + 2, cy - 3), (cx - 2, cy), color=icon)
                page.draw_line((cx - 2, cy), (cx + 2, cy + 3), color=icon)
            elif n == 2:                      # contents ≡
                for k in (-2.5, 0, 2.5):
                    page.draw_line((cx - 3, cy + k), (cx + 3, cy + k), color=icon)
            else:                             # home ⌂
                page.draw_line((cx, cy - 3.2), (cx + 3.4, cy - 0.2), color=icon)
                page.draw_line((cx, cy - 3.2), (cx - 3.4, cy - 0.2), color=icon)
                page.draw_rect(pymupdf.Rect(cx - 2.2, cy - 0.2, cx + 2.2, cy + 3.2),
                               color=icon, width=0.6)
        page.draw_line((61, 812), (width - 61, 812), color=rule, width=0.4)
        page.insert_text((width - 74, 806), f"{i + 1}", fontsize=8,
                         color=number_color)
        # every button targets something real and distinct; the first content page
        # sends prev and contents to the contents page, never to itself
        first = i == first_content
        last = i == doc.page_count - 1
        targets = {
            # on the last page «next» wraps back to the contents page: a button
            # that points at its own page is a button that does nothing
            0: (contents_page or 0) if last else i + 1,
            1: (contents_page or first_content) if first else i - 1,
            2: contents_page or first_content,
            3: 0,
        }
        for n, x in enumerate(NAV_X):
            rect = pymupdf.Rect(x, NAV_Y[0], x + 25, NAV_Y[1])
            page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect,
                              "page": targets[n]})
        covered += 1

    doc.saveIncr()
    doc.close()
    # الأرقام في `outline` **مطبوعة سلفاً** (page + 1) — وزيادة +1 هنا كانت تُنتج
    # إنذاراً كاذباً يقارن ٤ بـ٣ في كل مستند.
    info = verify_pdf(pdf, outline_pages=[p for _, _, p in outline[2:]],
                      contents_page=contents_page or None)
    info.update({"toc_entries": len(outline), "nav_pages": covered,
                 "outline_pages": [p for _, _, p in outline[2:]]})
    return info


def verify_pdf(pdf: Path, outline_pages: list[int] | None = None,
               contents_page: int | None = None) -> dict:
    """Read the artifact back: what a reviewer checks, done by a machine."""
    import pymupdf

    doc = pymupdf.open(pdf)
    fonts: set[str] = set()
    for page in doc:
        for f in page.get_fonts():
            fonts.add(f[3].split("+")[-1])
    links = self_links = 0
    for i, page in enumerate(doc):
        for link in page.get_links():
            if link.get("kind") == pymupdf.LINK_GOTO:
                links += 1
                if link.get("page") == i:
                    self_links += 1

    # الأرقام المطبوعة في صفحة المحتويات مقابل أرقام الفهرس الجانبي. وإن تعذّر
    # استخراجها فذلك **فشل** لا صمت: بوابة لا تستطيع أن تفشل ليست بوابة.
    contents_mismatch: list[tuple[int, int]] = []
    unreadable: tuple[int, int] | None = None
    if outline_pages and contents_page is not None and contents_page < doc.page_count:
        raw = doc[contents_page].get_text()
        printed = [int(t) for t in re.findall(r"[0-9٠-٩۰-۹]+", raw)]
        printed = printed[:len(outline_pages)]
        if len(printed) < len(outline_pages):
            unreadable = (len(printed), len(outline_pages))
        else:
            contents_mismatch = [(want, got)
                                 for want, got in zip(outline_pages, printed) if want != got]

    lengths = [len(p.get_text().strip()) for p in doc]
    skip = {0, contents_page} if contents_page is not None else {0}
    body_lengths = [n for i, n in enumerate(lengths) if i not in skip] or [0]
    median_len = sorted(body_lengths)[len(body_lengths) // 2] or 1
    # صفحة تحمل التذييل وحده = فيض تخطيط. نسبيّ لا مطلق (صفحة محتوى قصيرة مشروعة)،
    # وصفحة المحتويات مستثناة: نصّها بطبيعته أقلّ من صفحات المتن فيُعلَّم خطأً.
    blank = [i + 1 for i, n in enumerate(lengths)
             if i not in skip and n < 0.35 * median_len]

    info = {
        "pages": doc.page_count,
        "toc": len(doc.get_toc()),
        "links": links,
        "self_links": self_links,
        "fonts": sorted(fonts),
        "embedded_plex": any("IBMPlex" in f for f in fonts),
        "per_page_links": [len(p.get_links()) for p in doc],
        "contents_mismatch": contents_mismatch,
        "contents_unreadable": unreadable,
        "blank_pages": blank,
    }
    doc.close()
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--slogan", default="")
    ap.add_argument("--house", action="store_true",
                    help="the house standard: cover · seal · contents · nav · bookmarks")
    ap.add_argument("--no-toc", action="store_true", help="house mode بلا صفحة محتويات")
    args = ap.parse_args()

    md_path = Path(args.md).expanduser()
    out = Path(args.out).expanduser()
    if not md_path.exists():
        raise SystemExit(f"لا يوجد ملف: {md_path}")
    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome غير موجود في: {CHROME}")
    out.parent.mkdir(parents=True, exist_ok=True)

    title = args.title or md_path.stem
    md_text = md_path.read_text(encoding="utf-8")
    body, headings = render_body(md_text)
    work = Path(tempfile.mkdtemp(prefix="md-pdf-"))
    # الكتابة ذرّية: يُبنى في ملف مؤقّت **بجوار الهدف** (نفس نظام الملفات)، ولا
    # يُستبدل الهدف إلا بعد اجتياز كل الفحوص. تشغيل متأخّر أو منهار لا يطمس ملفاً
    # سليماً سُلِّم قبله — وقد كاد يحدث فعلاً حين بقي تشغيل قديم في الخلفية.
    staging = out.with_name(out.name + ".partial.pdf")

    if not args.house:
        html_path = work / f"{md_path.stem}.html"
        html_path.write_text(render(md_text, title), encoding="utf-8")
        done = print_pdf(html_path, staging)
        data = staging.read_bytes() if staging.exists() else b""
        pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
        print(f"[to-pdf] {out}\n  صفحات: {pages} · حجم: {len(data) / 1024:.0f}KB"
              f" · exit: {done.returncode}")
        if done.returncode or not data or pages < 1:
            print(done.stderr[-800:], file=sys.stderr)
            staging.unlink(missing_ok=True)
            raise SystemExit(1)
        staging.replace(out)
        return

    meta = ("مُعدّ من قياس منشور في المستودع — كل رقم في هذا الملف قابل لإعادة "
            "الاشتقاق من دليله")
    want_toc = bool(headings) and not args.no_toc

    def build(toc_entries: list[tuple[str, int]] | None, tag: str) -> Path:
        path = work / f"{md_path.stem}-{tag}.html"
        path.write_text(house_html(title, args.subtitle, args.slogan, body,
                                   toc_entries, meta), encoding="utf-8")
        return path

    import pymupdf
    print_tmp = work / "pass1.pdf"
    print_pdf(build([(re.sub(r"\s+", " ", t).strip(), 0)
                     for _lvl, t in headings][:14] if want_toc else None, "v1"),
              print_tmp)
    probe = pymupdf.open(print_tmp)
    first_content = 1 + (1 if want_toc else 0)
    found = heading_pages(probe, headings, start=first_content)
    probe.close()

    # حلقة تصحيح محدودة: نطبع، نقيس من الملف الناتج نفسه، ونعيد البناء إن خالف
    # الرقمُ المطبوعُ الفهرس. تكراران يكفيان عادةً، والثالث سقف أمان — والبديل
    # (حساب الإزاحات يدوياً) هو ما أنتج فهرساً يقول ٤ بينما الجانبي يقول ٣.
    entries = [(re.sub(r"\s+", " ", t).strip(), p + 1)
               for (_lvl, t), p in zip(headings, found)][:14] if want_toc else None
    info: dict = {}
    for attempt in range(3):
        tag = f"v{attempt + 2}"
        done = print_pdf(build(entries, tag), staging)
        data = staging.read_bytes() if staging.exists() else b""
        if done.returncode or not data:
            print(done.stderr[-800:], file=sys.stderr)
            staging.unlink(missing_ok=True)
            raise SystemExit(1)
        info = house_finish(staging, headings, contents_page=(1 if want_toc else 0))
        if not entries or (not info["contents_mismatch"]
                           and not info["contents_unreadable"]):
            break
        entries = [(text, page) for (text, _), page in
                   zip(entries, info["outline_pages"])]

    data = staging.read_bytes()
    print(f"[to-pdf] {out}")
    print(f"  صفحات: {info['pages']} · حجم: {len(data) / 1024:.0f}KB"
          f" · فهرس: {info['toc']} مدخلاً · روابط: {info['links']}"
          f" · روابط على الذات: {info['self_links']}")
    print(f"  خطوط مدمجة: {', '.join(info['fonts'])}")
    print(f"  روابط لكل صفحة: {info['per_page_links']}")
    failures = []
    if not info["embedded_plex"]:
        failures.append("الخط المنزلي غير مدمج — التصميم لن يُطبع كما رُسم")
    if info["self_links"]:
        failures.append(f"{info['self_links']} رابطاً يشير إلى صفحته — زر لا يعمل")
    if info["contents_mismatch"]:
        failures.append(f"فهرس المحتويات يخالف الفهرس الجانبي: {info['contents_mismatch']}")
    if info["contents_unreadable"]:
        got, want = info["contents_unreadable"]
        failures.append(f"تعذّر التحقق من أرقام المحتويات: قُرئ {got} من {want}")
    if info["blank_pages"]:
        failures.append(f"صفحات فارغة (فيض تخطيط): {info['blank_pages']}")
    if failures:
        staging.unlink(missing_ok=True)
        raise SystemExit(" | ".join(failures))
    # آخر خطوة بعد نجاح كل الفحوص: الملف المؤقّت يحلّ محلّ الهدف. فشلٌ في أي فحص
    # أعلاه يُبقي الملف السابق سليماً، وملفٌ ناقص لا يُسلَّم أبداً.
    staging.replace(out)


if __name__ == "__main__":
    main()
