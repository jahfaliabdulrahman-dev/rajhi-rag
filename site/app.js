// Every number on this page is read here, at load time, from a tracked file. None is typed into the page;
// tests/test_pages_site.py holds that. The four files, each a link to its source in the repository:
//   statement_showcase.ledger.json  the system's own reading of the synthetic statement (tools/ledger.py)
//   pypdfloader.json                LangChain's PyPDFLoader on the same PDF (docs/measurements/)
//   plain-read.json                 the same model with a plain request, no chain and no footer (tools/measure_plain_read.py)
//   claims.json                     the guarded aggregate figures of the real 629-page run (tools/render_claims.py)
"use strict";

const SOURCES = {
  ledger: "statement_showcase.ledger.json",
  loader: "pypdfloader.json",
  plain: "plain-read.json",
  claims: "claims.json",
};
const ORDINALS = ["الأولى", "الثانية", "الثالثة", "الرابعة"];

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

// Text and numbers in one line: strings stay text, anything else becomes an isolated number.
function line(node, ...parts) {
  node.append(...parts.map((p) => (typeof p === "string" ? p : num(p.value))));
  return node;
}
const n = (value) => ({ value });

function cell(row, content, header) {
  const td = el(header ? "th" : "td");
  if (header) td.scope = "row";
  if (content instanceof Node) td.append(content); else td.textContent = content;
  row.append(td);
}

function firstLine(text) {
  return (text || "").split("\n")[0];
}

function renderCatch(rows) {
  const i = rows.findIndex((r) => !r.chain_ok && r.movement);
  // The row is never made up: with no row flagged in this reading, the section stays hidden.
  if (i < 1) return;
  const prev = rows[i - 1];
  const r = rows[i];
  document.getElementById("catch-desc").textContent = `«${firstLine(r.desc)}»`;
  const figures = document.getElementById("catch-figures");
  for (const [label, value] of [
    ["الرصيدُ قبله", money(prev.balance)],
    ["الرصيدُ بعده", money(r.balance)],
    [r.side === "credit" ? "الإيداعُ كما قُرئ" : "السحبُ كما قُرئ", money(r.movement)],
  ]) {
    const item = el("div");
    item.append(el("dt", label));
    const dd = el("dd");
    dd.append(num(value));
    item.append(dd);
    figures.append(item);
  }
  line(document.getElementById("catch-answer"),
       "لا يطابق. الفرقُ بين الرصيدين ", n(money(r.derived_movement)), "، والمقروء ", n(money(r.movement)),
       ": رقمان تبادلا موضعَيهما.");
  document.getElementById("catch").hidden = false;
}

function runSentence(run, index, rows) {
  const pages = run.pages.filter((p) => p.balances_expected > 0);
  const worst = pages.reduce((a, b) => (b.balances_matched / b.balances_expected < a.balances_matched / a.balances_expected ? b : a));
  const node = el("li");
  node.append(el("strong", `المرّة ${ORDINALS[index] || index + 1}: `));
  if (worst.balances_matched < worst.balances_expected) {
    line(node, "أرصدةُ الصفحة ", n(worst.page), ": ", n(worst.balances_matched), " من ", n(worst.balances_expected),
         " تطابق الكشف. ");
    node.append(worst.breaks_inside_the_answer === 0
      ? "والجوابُ متّسقٌ مع نفسه، فلا شيء فيه يدلّ على الخطأ. "
      : "وفي الجواب تناقضٌ لم يذكره. ");
  } else {
    node.append("أرصدةُ الصفحات كلُّها تطابق الكشف. ");
  }
  for (const f of run.pages.flatMap((p) => p.flagged)) {
    const name = firstLine((rows.find((r) => r.seq === f.seq) || {}).desc);
    if (f.answer_has_printed_amount) {
      node.append(`وجاء صفُّ «${name}» بالقراءة الخاطئة نفسها التي أخطأها قارئُ النظام، ولم يذكر الجوابُ ذلك.`);
    } else if (f.answer_has_balance_difference) {
      node.append(`وقرأ صفَّ «${name}» صحيحًا.`);
    }
  }
  return node;
}

function renderHard(loader, plain, rows) {
  const chars = loader.characters_per_page.reduce((a, b) => a + b, 0);
  line(document.getElementById("fact-loader"),
       "محمّلُ PyPDFLoader في LangChain، أوّلُ خطوةٍ في سلسلة RAG التي درسناها، يعيد من الملفّ ", n(loader.documents),
       " مستندات، وعددُ الحروف فيها ", n(chars), ".");
  // Whether the two answers differed is read from the runs, not asserted.
  const shape = (run) => run.pages.map((p) => `${p.page}:${p.balances_matched}:${p.amounts_matched}`).join("|");
  const differed = plain.runs.length > 1 && new Set(plain.runs.map(shape)).size > 1;
  document.getElementById("fact-plain").textContent =
    "ثمّ أُرسلت الصفحاتُ نفسُها إلى النموذج نفسه الذي يقرأ به النظام، بطلبٍ بسيط: «استخرج كلَّ حركةٍ JSON»، بلا سلسلةٍ ولا تذييل." +
    (plain.runs.length > 1 ? (differed ? " والطلبُ نفسُه أُعيد، فاختلف الجوابان:" : " والطلبُ نفسُه أُعيد، فجاء الجوابُ نفسُه:") : "");
  ["fact-run-1", "fact-run-2"].forEach((id, i) => {
    const slot = document.getElementById(id);
    if (plain.runs[i]) slot.replaceWith(runSentence(plain.runs[i], i, rows)); else slot.remove();
  });
  const spent = plain.runs.reduce((a, r) => a + r.spent, 0);
  line(document.getElementById("fact-cost"), "كلفةُ القياسين ", n(`$${spent.toFixed(3)}`), " · النموذج ", n(plain.runs[0].model));
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

function renderChain(rows) {
  const proven = rows.filter((r) => r.chain_ok && !r.opening).length;
  const opening = rows.filter((r) => r.opening).length;
  const shown = rows.filter((r) => !r.chain_ok).length;
  line(document.getElementById("chain-tally"), "حركاتٌ أثبتتها السلسلة: ", n(proven), " · رصيدٌ افتتاحيّ: ", n(opening),
       " · صفوفٌ تُعرض عليك: ", n(shown));
}

function renderFooters(footers) {
  const body = document.querySelector("#footers tbody");
  for (const f of Object.values(footers).sort((a, b) => a.page - b.page)) {
    const tr = el("tr", undefined, f.verdict === "ok" ? "ok" : "flagged");
    cell(tr, num(f.page), true);
    cell(tr, num(f.debits));
    cell(tr, num(f.credits));
    cell(tr, f.verdict === "ok" ? "✓ يطابق" : "✗ لا يطابق");
    body.append(tr);
  }
}

function renderReal(claims) {
  const list = document.getElementById("real-stats");
  for (const [label, value] of [
    ["صفحةٌ ممسوحة", claims.pages],
    ["صفوفٌ أثبتتها السلسلة", claims.clean_ratio],
    ["نسبتُها", claims.clean_pct],
    ["صفحاتٌ طابقت ذيولها", claims.documented_ratio],
  ]) {
    const item = el("div");
    item.append(el("dt", label));
    const dd = el("dd");
    dd.append(num(value));
    item.append(dd);
    list.append(item);
  }
  const unproven = claims.mismatch + claims.gap + claims.absent + claims.unchecked;
  line(document.getElementById("real-unproven"),
       "ولم تُثبت ", n(unproven), " صفحة، ولكلٍّ منها في التقرير اسمُها وسببُها: تخالف إطارها المطبوع ",
       n(claims.mismatch), " · فجوةٌ في الترقيم ", n(claims.gap), " · بلا سطر إجماليّاتٍ مقروء ", n(claims.absent),
       " · غيرُ محسومة ", n(claims.unchecked), ".");
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function main() {
  try {
    const [ledger, loader, plain, claims] = await Promise.all(Object.values(SOURCES).map(fetchJson));
    const rows = [...ledger.rows].sort((a, b) => a.seq - b.seq);
    renderCatch(rows);
    renderHard(loader, plain, rows);
    renderReading(rows);
    renderChain(rows);
    renderFooters(ledger.footers);
    renderReal(claims);
  } catch (error) {
    document.getElementById("load-error").hidden = false;
  }
}

main();
