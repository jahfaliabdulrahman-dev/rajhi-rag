// The front page's few numbers, read at load time from the same tracked files as the story page (story.html).
//   page.json    one page of a real statement as the system read it, names hidden
//   claims.json  the guarded aggregate figures of the same statement's full run
"use strict";

function money(value) {
  return Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function num(text) {
  const span = el("span", String(text), "num");
  span.dir = "ltr";
  return span;
}

function kind(text) {
  return (text || "").split("\n")[0].split(/[([A-Za-z]/)[0].trim();
}

// A few consecutive rows ending just after the first row the chain stopped at: real rows, never made up.
function renderPreview(page) {
  const rows = [...page.rows].sort((a, b) => a.seq - b.seq);
  const flagged = rows.findIndex((r) => !r.chain_ok);
  const end = flagged >= 0 ? Math.min(rows.length, flagged + 2) : rows.length;
  const list = document.getElementById("preview-rows");
  rows.slice(Math.max(0, end - 5), end).forEach((r, i) => {
    const item = el("li", undefined, r.chain_ok ? "ok" : "flagged");
    item.style.setProperty("--i", i);
    const what = el("span", kind(r.desc), "what");
    const amount = el("span", undefined, "amount");
    amount.append(num(money(r.movement)));
    const balance = el("span", undefined, "balance");
    balance.append(num(money(r.balance)));
    const mark = el("span", r.chain_ok ? "✓ ثبت" : "يُراجَع", "mark-chip");
    item.append(what, amount, balance, mark);
    list.append(item);
  });
}

function renderFigures(claims) {
  const list = document.getElementById("proof-figures");
  for (const [value, label] of [
    [claims.pages, "صفحةً ممسوحة قُرئت"],
    [claims.clean_pct, "من الصفوف أثبتها حسابُ الرصيد"],
    [claims.documented_ratio, "صفحةً طابقت مجاميعَها المطبوعة"],
  ]) {
    const item = el("div");
    const dd = el("dd");
    dd.append(num(value));
    item.append(dd, el("dt", label));
    list.append(item);
  }
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function main() {
  try {
    const [page, claims] = await Promise.all(["page.json", "claims.json"].map(fetchJson));
    renderPreview(page);
    renderFigures(claims);
  } catch (error) {
    document.getElementById("load-error").hidden = false;
  }
}

main();
