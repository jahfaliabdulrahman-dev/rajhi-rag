// Every number on this page is read here from the showcase statement's ledger (the system's own reading,
// exported by tools/ledger.py). None is typed into the page: tests/test_pages_site.py holds that.
"use strict";

const LEDGER = "statement_showcase.ledger.json";

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
  const span = el("span", text, "num");
  span.dir = "ltr";
  return span;
}

function cell(row, content, header) {
  const td = el(header ? "th" : "td");
  if (header) td.scope = "row";
  if (content instanceof Node) td.append(content); else td.textContent = content;
  row.append(td);
}

function firstLine(text) {
  return (text || "").split("\n")[0];
}

function renderReading(rows) {
  const body = document.querySelector("#reading tbody");
  for (const r of rows.filter((x) => x.page === 1).slice(0, 6)) {
    const tr = el("tr");
    cell(tr, firstLine(r.desc), true);
    cell(tr, r.printed_movement ? num(r.printed_movement) : "—");
    cell(tr, r.movement ? num(money(r.movement)) : "—");
    cell(tr, num(money(r.balance)));
    body.append(tr);
  }
}

function link(prev, r) {
  const li = el("li", undefined, r.chain_ok ? "ok" : "flagged");
  const kind = r.side === "credit" ? "إيداع" : "سحب";
  const line = el("p");
  line.append("الرصيد قبله ", num(money(prev.balance)), ` · ${kind} `, num(money(r.movement)),
              " ⇒ الرصيد ", num(money(r.balance)));
  li.append(el("strong", firstLine(r.desc)), line);
  if (r.chain_ok) {
    li.append(el("p", "✓ ثبت بالسلسلة", "verdict"));
  } else {
    const why = el("p", undefined, "verdict");
    why.append("✗ فرقُ الرصيدين ", num(money(r.derived_movement)), " والمبلغُ المطبوع ",
               num(money(r.movement)), " — لا يطابقان، فيُعرض الصفُّ عليك");
    li.append(why);
  }
  return li;
}

function renderChain(rows) {
  const list = document.getElementById("chain");
  const flagged = rows.findIndex((r) => !r.chain_ok);
  // The red row is never made up: with no flagged row in this reading, the chain shows proven links only.
  const end = flagged > 0 ? flagged : Math.min(3, rows.length - 1);
  for (let i = Math.max(1, end - 2); i <= end; i++) {
    if (!rows[i].opening) list.append(link(rows[i - 1], rows[i]));
  }
  const proven = rows.filter((r) => r.chain_ok && !r.opening).length;
  const opening = rows.filter((r) => r.opening).length;
  const shown = rows.filter((r) => !r.chain_ok).length;
  const tally = document.getElementById("chain-tally");
  tally.append("حركاتٌ أثبتتها السلسلة: ", num(String(proven)), " · رصيدٌ افتتاحيّ: ", num(String(opening)),
               " · صفوفٌ تُعرض عليك: ", num(String(shown)));
}

function renderFooters(footers) {
  const body = document.querySelector("#footers tbody");
  const pages = Object.values(footers).sort((a, b) => a.page - b.page);
  for (const f of pages) {
    const tr = el("tr", undefined, f.verdict === "ok" ? "ok" : "flagged");
    cell(tr, num(String(f.page)), true);
    cell(tr, num(f.debits));
    cell(tr, num(f.credits));
    cell(tr, f.verdict === "ok" ? "✓ يطابق" : "✗ لا يطابق");
    body.append(tr);
  }
  return pages;
}

function renderStats(data, pages) {
  const list = document.getElementById("stats");
  const matched = pages.filter((f) => f.verdict === "ok").length;
  for (const [label, value] of [
    ["صفوفٌ مقروءة", String(data.rows.length)],
    ["صفحات", String(data.n_pages)],
    ["ذيولٌ طابقت", `${matched}/${pages.length}`],
    ["قُرئ في", data.read_on],
  ]) {
    const item = el("div");
    item.append(el("dt", label));
    const dd = el("dd");
    dd.append(num(value));
    item.append(dd);
    list.append(item);
  }
}

async function main() {
  try {
    const response = await fetch(LEDGER);
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    const rows = [...data.rows].sort((a, b) => a.seq - b.seq);
    renderReading(rows);
    renderChain(rows);
    renderStats(data, renderFooters(data.footers));
  } catch (error) {
    document.getElementById("load-error").hidden = false;
  }
}

main();
