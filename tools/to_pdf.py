#!/usr/bin/env python3
"""Markdown → Arabic/RTL PDF (Chrome headless) — a reusable habit, not a one-off.

Why Chrome: fpdf2 has no true Arabic shaping (letters come out disconnected) and
WeasyPrint needs a pango fix on macOS. Chrome prints `dir="rtl"` HTML with correct
glyph shaping, `@page` margins, and page counters, with no font hacks.

    python3 tools/to_pdf.py --md docs/WHO_IS_THIS_FOR.md \
        --out ~/Downloads/who-is-this-for-ar.pdf --title "لمن بُني هذا"

Deliberately small: headings, paragraphs, blockquote, lists, tables, bold, inline
code, rules. Anything richer belongs in an HTML template, not here — a converter
that guesses is a converter that quietly drops a paragraph.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
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
.doc-footer { margin-top: 8mm; padding-top: 3mm; border-top: 0.8pt solid #d9dee9;
              font-size: 8.5pt; color: #7b8496; }
"""


def inline(text: str) -> str:
    """Bold, inline code — and HTML-escape everything else."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def render(md_text: str, title: str) -> str:
    """Markdown body → HTML. Table rows are detected by their leading pipe."""
    parts: list[str] = [
        "<!DOCTYPE html>", '<html lang="ar" dir="rtl">', "<head>",
        '<meta charset="UTF-8">', f"<title>{html.escape(title)}</title>",
        f"<style>{CSS}</style>", "</head>", "<body>",
    ]
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
            parts.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
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
            parts.append(f"<h3>{inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            close_list()
            parts.append(f"<h2>{inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            close_list()
            parts.append(f"<h1>{inline(stripped[2:])}</h1>")
        elif stripped.startswith("> "):
            close_list()
            parts.append(f"<blockquote><p>{inline(stripped[2:])}</p></blockquote>")
        elif stripped in ("---", "***", "___"):
            close_list()
            parts.append("<hr>")
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
    parts.append("</body></html>")
    return "\n".join(parts)


def print_pdf(html_path: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
         f"--print-to-pdf={out}", "--no-pdf-header-footer",
         html_path.as_uri()],
        capture_output=True, text=True, timeout=120)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    md_path = Path(args.md).expanduser()
    out = Path(args.out).expanduser()
    if not md_path.exists():
        raise SystemExit(f"لا يوجد ملف: {md_path}")
    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome غير موجود في: {CHROME}")

    title = args.title or md_path.stem
    work = Path(tempfile.mkdtemp(prefix="md-pdf-"))
    html_path = work / f"{md_path.stem}.html"
    html_path.write_text(render(md_path.read_text(encoding="utf-8"), title),
                         encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = print_pdf(html_path, out)

    data = out.read_bytes() if out.exists() else b""
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    print(f"[to-pdf] {out}")
    print(f"  صفحات: {pages} · حجم: {len(data) / 1024:.0f}KB · exit: {done.returncode}"
          f" · HTML: {html_path}")
    if done.returncode != 0 or not data:
        print(done.stderr[-800:], file=sys.stderr)
        raise SystemExit(1)
    if pages < 1:
        raise SystemExit("PDF بلا صفحات — فشل الطباعة")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
