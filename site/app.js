// Every number on this page is read here, at load time, from a tracked file. None is typed into the page;
// tests/test_pages_site.py holds that. The four files, each a link to its source in the repository:
//   page.json         one page of a real statement as the system read it, names hidden (tools/publish_real_page.py)
//   pypdfloader.json  LangChain's PyPDFLoader on the same statement (docs/measurements/)
//   plain-read.json   the same model with a plain request on the same page, counts only (tools/measure_plain_read.py)
//   claims.json       the guarded aggregate figures of the same statement's full run (tools/render_claims.py)
"use strict";

const SOURCES = {
  page: "page.json",
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

// "a of b" kept on one line: the two numbers and the word between them never wrap apart.
function outOf(a, b) {
  const span = el("span", undefined, "pair");
  span.append(num(a), " من ", num(b));
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

// The kind of movement: the description's first line up to its first bracket or Latin letter.
function kind(text) {
  return firstLine(text).split(/[([A-Za-z]/)[0].trim();
}

// How a misread amount differs from the balances' difference, said from the digits themselves.
function howItDiffers(read, derived) {
  const a = money(read).replace(/\D/g, "");
  const b = money(derived).replace(/\D/g, "");
  if (a.length === b.length) {
    const at = [...a].map((d, i) => (d === b[i] ? -1 : i)).filter((i) => i >= 0);
    if (at.length === 1) return "رقمٌ واحدٌ قُرئ خطأً";
    if (at.length === 2 && at[1] === at[0] + 1 && a[at[0]] === b[at[1]] && a[at[1]] === b[at[0]]) {
      return "رقمان تبادلا موضعَيهما";
    }
  }
  return "قراءةٌ تخالف فرقَ الرصيدين";
}

function renderCatch(rows) {
  const i = rows.findIndex((r) => r.chain_ok === false && r.movement);
  // The row is never made up: with no row flagged on this page, the section stays hidden.
  if (i < 1) return;
  const prev = rows[i - 1];
  const r = rows[i];
  const debit = r.side === "debit";
  const sum = document.getElementById("catch-sum");
  for (const [op, label, value, last] of [
    ["", "الرصيدُ قبله", prev.balance, false],
    [debit ? "−" : "+", debit ? "السحبُ كما قرأه النظام" : "الإيداعُ كما قرأه النظام", r.movement, false],
    ["=", "الرصيدُ بعده", r.balance, true],
  ]) {
    const row = el("div", undefined, last ? "line result" : "line");
    const name = el("span", label, "label");
    if (last) name.append(el("span", "؟", "ask"));
    row.append(name, el("span", op, "op"), num(money(value)));
    sum.append(row);
  }
  line(document.getElementById("catch-answer"),
       "لا يطابق. الفرقُ بين الرصيدين ", n(money(r.derived_movement)), "، والنظامُ قرأ ", n(money(r.movement)),
       `: ${howItDiffers(r.movement, r.derived_movement)}.`);
  document.getElementById("catch").hidden = false;
}

function runSentence(run, index, rows) {
  const node = el("li");
  node.append(el("strong", `المرّة ${ORDINALS[index] || index + 1}: `));
  const t = run.totals;
  if (t.rows_returned < t.rows_expected) {
    node.append("أعاد من الصفوف ", outOf(t.rows_returned, t.rows_expected), ". ");
  }
  if (t.balances_matched === t.balances_expected && t.amounts_matched === t.amounts_expected) {
    node.append("صحّت أرصدتُه ومبالغُه كلُّها، ", outOf(t.amounts_matched, t.amounts_expected), ". ");
  } else {
    node.append("صحّ من الأرصدة ", outOf(t.balances_matched, t.balances_expected), "، ومن المبالغ ",
                outOf(t.amounts_matched, t.amounts_expected), ". ");
    node.append(t.breaks_inside_the_answer === 0
      ? "والجوابُ متّسقٌ مع نفسه، فلا شيء فيه يدلّ على الخطأ. "
      : "وفي جوابه تناقضٌ لم يذكره. ");
  }
  for (const f of run.pages.flatMap((p) => p.flagged)) {
    if (!rows.some((r) => r.seq === f.seq)) continue;
    if (f.answer_has_balance_difference) {
      node.append("ومنها قرأ صحيحًا الصفَّ الذي أخطأه قارئُ النظام.");
    } else if (f.answer_has_systems_reading) {
      node.append("وأخطأ الصفَّ الذي أخطأه قارئُ النظام، بالقراءة نفسها، ولم يذكر ذلك.");
    } else {
      node.append("وجاء الصفُّ الذي أخطأه قارئُ النظام بقراءةٍ ثالثة.");
    }
  }
  return node;
}

function renderHard(loader, plain, rows) {
  const first = document.getElementById("step-loader");
  first.append(el("strong", "المحاولة الأولى: "));
  line(first, "محمّلُ PyPDFLoader في LangChain، أوّلُ خطوةٍ في سلسلة RAG التي درسناها. أعاد من الكشف ",
       n(loader.documents), " مستندًا، وعددُ الحروف فيها كلّها ", n(loader.characters_total),
       loader.characters_total === 0 ? ": لا نصَّ يُقرأ." : ".");
  const plainStep = document.getElementById("step-plain");
  plainStep.append(el("strong", "المحاولة الثانية: "),
    "الصفحةُ نفسُها إلى النموذج نفسه الذي يقرأ به النظام، بطلبٍ بسيط: «استخرج كلَّ حركةٍ JSON»، بلا سلسلةٍ ولا تذييل." +
    (plain.runs.length > 1 ? " وأُعيد الطلبُ نفسُه:" : ""));
  ["fact-run-1", "fact-run-2"].forEach((id, i) => {
    const slot = document.getElementById(id);
    if (plain.runs[i]) slot.replaceWith(runSentence(plain.runs[i], i, rows)); else slot.remove();
  });
  const spent = plain.runs.reduce((a, r) => a + r.spent, 0);
  line(document.getElementById("fact-cost"), "كلفةُ القراءتين ", n(`$${spent.toFixed(3)}`), " · النموذج ", n(plain.runs[0].model));
}

function renderReading(page) {
  line(document.getElementById("scan-caption"), "الصفحةُ ", n(page.page), " من كشفٍ طولُه ", n(page.n_pages),
       " صفحة. اضغط الصورة لتراها بحجمها.");
  const body = document.querySelector("#reading tbody");
  for (const r of page.rows) {
    const tr = el("tr", undefined, r.chain_ok ? "ok" : "flagged");
    cell(tr, kind(r.desc), true);
    cell(tr, r.movement ? num(money(r.movement)) : "—");
    cell(tr, num(money(r.balance)));
    cell(tr, r.chain_ok ? "✓" : "✗ يُراجَع");
    body.append(tr);
  }
}

function renderChain(page) {
  const proven = page.rows.filter((r) => r.chain_ok).length;
  const shown = page.rows.filter((r) => !r.chain_ok).length;
  line(document.getElementById("chain-tally"), "في هذه الصفحة: حركاتٌ أثبتتها السلسلة ", n(proven),
       " · صفوفٌ تُعرض للمراجعة ", n(shown));
  // Which figure is wrong is read from the break's shape, not from the footer: a break between two rows the
  // chain holds means the balances on both sides agree with their neighbours, so the amount read is the odd one.
  const i = page.rows.findIndex((r) => !r.chain_ok);
  const isolated = shown === 1 && i > 0 && i < page.rows.length - 1 && page.rows[i - 1].chain_ok && page.rows[i + 1].chain_ok;
  if (isolated) {
    document.getElementById("chain-why").textContent =
      "والصفُّ المعروض بين صفّين يُثبتهما الحساب، فالرصيدان على طرفيه يتّفقان مع ما قبلهما وما بعدهما، والمخالفُ هو المبلغُ المقروء.";
  }
  const verdict = document.getElementById("footer-verdict");
  if (page.footer.verdict !== "ok") {
    verdict.textContent = "ذيلُ هذه الصفحة: ✗ لا يطابق.";
    verdict.classList.add("flagged");
    return;
  }
  verdict.textContent = "ذيلُ هذه الصفحة: ✓ يطابق: مجموعا المدين والدائن ورصيدُ آخر الصفحة كما طُبعت.";
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
  // The guarded source declares two readings, not one (reader_stamp): the split is published beside the headline.
  const [unstampedOk, unstamped] = String(claims.split_unstamped).split("/");
  const [stampedOk, stamped] = String(claims.split_stamped).split("/");
  line(document.getElementById("real-stamps"),
       "وهي قراءتان لا واحدة: ", n(unstamped), " صفحةً قُرئت قبل أن يُختَم إصدارُ القارئ، طابق منها ذيولَه ", n(unstampedOk),
       "، و", n(stamped), " بالقارئ المختوم، طابق منها ", n(stampedOk),
       ". فالأرقامُ أعلاه تجمعهما، ولا تُنسب كلُّها إلى إصدارٍ واحد.");
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function main() {
  try {
    const [page, loader, plain, claims] = await Promise.all(Object.values(SOURCES).map(fetchJson));
    const rows = [...page.rows].sort((a, b) => a.seq - b.seq);
    renderCatch(rows);
    renderHard(loader, plain, rows);
    renderReading({ ...page, rows });
    renderChain({ ...page, rows });
    renderReal(claims);
  } catch (error) {
    document.getElementById("load-error").hidden = false;
  }
}

main();
