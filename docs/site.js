/* Signals-Before-Storms: the landing panel's controller.

   The drawing moved to charts.js when story.html started needing the same figures. What is left
   here is this page's state and nothing else: which market, gross or net, which books are
   plotted, which benchmark the paired test runs against, and how the scorecard is sorted.

   The data comes from tools/export_site_data.py, which computes it with the same functions the
   printed scorecard uses. Nothing is recomputed here: this file only decides what to draw. */

import {
  $,
  $$,
  BOOKS,
  STROKE_OF,
  cursorBus,
  episodeDumbbell,
  esc,
  group,
  labelProfile,
  lineChart,
  num,
  pairedForest,
  pct,
  reveal,
  scorecard,
  signed,
  weightStack,
} from "./charts.js";

const MARKETS = ["india", "us"];
const DATA = {};

const state = {
  market: "india",
  cost: "net",
  visible: new Set(["hmm_conditional", "60_40", "equal_weight"]),
  bench: "60_40",
  sort: "sharpe",
  desc: true,
};

/* ------------------------------------------------------------------ panels */

function seriesFor(d, source) {
  return BOOKS.filter(([k]) => state.visible.has(k) && d[source][k]).map(([k, label]) => ({
    key: k,
    label,
    stroke: STROKE_OF[k],
    values: source === "curves" ? d.curves[k][state.cost] : d.drawdowns[k],
  }));
}

function drawStats(d) {
  const t = d.scorecard_net;
  const get = (book, cName) => t.rows[t.index.indexOf(book)][t.columns.indexOf(cName)];
  const lead = "hmm_conditional";
  const p = d.paired["60_40"][lead];
  const tiles = [
    [
      "Max drawdown",
      pct(get(lead, "max_drawdown"), 1),
      `60/40 took ${pct(get("60_40", "max_drawdown"), 1)}`,
    ],
    ["Calmar", num(get(lead, "calmar")), `60/40 managed ${num(get("60_40", "calmar"))}`],
    ["Sharpe", num(get(lead, "sharpe")), `60/40 managed ${num(get("60_40", "sharpe"))}`],
    [
      "Sharpe gap vs 60/40",
      signed(p.d),
      `95% interval ${num(p.ci[0])} to ${num(p.ci[1])}, spans zero`,
    ],
  ];
  $("#stats").innerHTML = tiles
    .map(
      ([k, v, sub]) =>
        `<div class="stat"><span class="stat__k">${k}</span><span class="stat__v">${v}</span><span class="stat__sub">${esc(sub)}</span></div>`,
    )
    .join("");
}

/* ------------------------------------------------------------------ chrome */

function buildToggles(d) {
  $("#books").innerHTML = BOOKS.filter(([k]) => d.curves[k])
    .map(
      ([k, label, kind]) =>
        `<label class="chip${state.visible.has(k) ? " on" : ""}" data-kind="${kind}">
      <input type="checkbox" value="${k}"${state.visible.has(k) ? " checked" : ""}>
      <i style="background:${STROKE_OF[k].c}"></i>${esc(label)}</label>`,
    )
    .join("");
  $$("#books input").forEach((box) =>
    box.addEventListener("change", () => {
      if (box.checked) state.visible.add(box.value);
      else state.visible.delete(box.value);
      box.closest(".chip").classList.toggle("on", box.checked);
      render();
    }),
  );
}

/** Toggle a book from the scorecard as well as from the chips, and keep the two in step. */
function pickBook(key) {
  if (state.visible.has(key)) state.visible.delete(key);
  else state.visible.add(key);
  const box = $(`#books input[value="${CSS.escape(key)}"]`);
  if (box) {
    box.checked = state.visible.has(key);
    box.closest(".chip").classList.toggle("on", box.checked);
  }
  render();
}

function render() {
  const d = DATA[state.market];
  if (!d) return;

  // Every linked chart is rebuilt below, so last render's subscribers point at detached DOM.
  // Clearing first is what stops one closure leaking per chart per toggle.
  cursorBus.clear();

  $$("[data-oos]").forEach((el) => {
    el.textContent = `${d.oos.start} to ${d.oos.end}, n = ${d.oos.n.toLocaleString()}`;
  });
  $$("[data-market-name]").forEach((el) => {
    el.textContent = state.market === "us" ? "US" : "India";
  });

  drawStats(d);
  lineChart($("#chart-equity"), d, {
    series: seriesFor(d, "curves"),
    fmt: (v) => `${v.toFixed(1)}x`,
    bands: true,
    zero: false,
  });
  lineChart($("#chart-drawdown"), d, {
    series: seriesFor(d, "drawdowns"),
    fmt: (v) => `${(v * 100).toFixed(0)}%`,
    bands: false,
    zero: true,
  });
  labelProfile($("#chart-labels"), d);
  pairedForest($("#chart-paired"), d, { bench: state.bench });
  weightStack($("#chart-weights"), d);
  episodeDumbbell($("#chart-episodes"), d);
  scorecard($("#scorecard"), d, {
    cost: state.cost,
    sort: state.sort,
    desc: state.desc,
    visible: state.visible,
    onSort: (c) => {
      state.desc = state.sort === c ? !state.desc : true;
      state.sort = c;
      render();
    },
    onPick: pickBook,
  });
}

async function boot() {
  const loaded = await Promise.all(
    MARKETS.map((m) =>
      fetch(`data/${m}.json`)
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ),
  );
  MARKETS.forEach((m, i) => {
    if (loaded[i]) DATA[m] = loaded[i];
  });
  if (!DATA[state.market]) {
    // A page that silently shows nothing is worse than one that says why. This fires when the
    // page is opened straight off the filesystem, where fetch is blocked by the file:// origin.
    $("#charts").innerHTML =
      '<p class="note">Result data could not be loaded. Serve this directory over HTTP rather than opening the file directly, then reload.</p>';
    return;
  }
  buildToggles(DATA[state.market]);
  group("market", (v) => {
    state.market = v;
    buildToggles(DATA[state.market]);
    render();
  });
  group("cost", (v) => {
    state.cost = v;
    render();
  });
  group("bench", (v) => {
    state.bench = v;
    pairedForest($("#chart-paired"), DATA[state.market], { bench: v });
  });
  render();

  // The two additions sit well below the fold, so they fade in rather than arriving already
  // finished. reveal() calls straight through when prefers-reduced-motion is set.
  ["#chart-weights", "#chart-episodes"].forEach((sel) => {
    const el = $(sel);
    if (el) reveal(el, () => el.classList.add("seen"));
  });
}

boot();
