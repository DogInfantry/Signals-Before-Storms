/* Signals-Before-Storms: the charts on the landing page, drawn from real exported results.

   No framework and no build step, because the page is four charts over two JSON files and
   Vercel serves docs/ as static files. Everything is hand-built SVG so it stays sharp on a
   phone, inherits the page's light and dark themes through CSS custom properties, and needs
   no canvas sizing dance.

   The data comes from tools/export_site_data.py, which computes it with the same functions
   the printed scorecard uses. Nothing is recomputed here: this file only draws. */

const MARKETS = ["india", "us"];
const DATA = {};

// Book identity. Order is fixed so a book keeps its colour when others are toggled off, and
// the labels are the ones the README uses, spelled for a reader rather than as a dict key.
const BOOKS = [
  ["hmm_conditional", "HMM, conditional moments", "strategy"],
  ["hmm_drawdown_feat", "HMM + drawdown feature", "strategy"],
  ["vol_rule_ablation", "Volatility rule (no HMM)", "ablation"],
  ["jump_regime", "Jump model", "strategy"],
  ["hmm_vol_targeted", "HMM, volatility targeted", "strategy"],
  ["hmm_unconditional", "HMM, unconditional moments", "strategy"],
  ["60_40", "Static 60/40", "benchmark"],
  ["equal_weight", "Equal weight", "benchmark"],
];

// Two validated hues plus two neutrals, each in solid and dashed. That is eight separable
// series without inventing a categorical palette: src/regime_shift/style.py only clears its
// contrast and colour-vision floors for the pairs it actually validated, and this reuses those
// rather than guessing six more. Distinction past four series comes from dash, not hue.
const STROKES = [
  { c: "var(--series-a)", d: "" },
  { c: "var(--series-b)", d: "" },
  { c: "var(--neutral)", d: "5 4" },
  { c: "var(--ink-soft)", d: "2 3" },
  { c: "var(--series-a)", d: "5 4" },
  { c: "var(--series-b)", d: "2 3" },
  { c: "var(--neutral)", d: "" },
  { c: "var(--ink-soft)", d: "5 4" },
];
const STROKE_OF = Object.fromEntries(BOOKS.map(([k], i) => [k, STROKES[i % STROKES.length]]));

const REGIME_NAMES = ["Bull", "Bear", "Crisis"];

const state = {
  market: "india",
  cost: "net",
  visible: new Set(["hmm_conditional", "60_40", "equal_weight"]),
  bench: "60_40",
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const pct = (x, nd = 1) => (x == null ? "n/a" : `${(x * 100).toFixed(nd)}%`);
const num = (x, nd = 2) => (x == null ? "n/a" : x.toFixed(nd));

/* ------------------------------------------------------------------ chart primitives */

const PAD = { l: 46, r: 12, t: 10, b: 26 };

function scaler(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (v) => r0 + ((v - d0) / span) * (r1 - r0);
}

function extent(arrays) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const a of arrays) {
    for (const v of a) {
      if (v == null) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  return lo === Infinity ? [0, 1] : [lo, hi];
}

function path(values, x, y) {
  let d = "";
  values.forEach((v, i) => {
    if (v == null) return;
    d += `${d ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  });
  return d;
}

function ticks(lo, hi, count = 4) {
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
  return out;
}

/** Regime spans as background washes, mapped from run-length dates onto plot indices. */
function regimeBands(d, x, h) {
  const at = new Map(d.dates.map((s, i) => [s, i]));
  const nearest = (s) => {
    if (at.has(s)) return at.get(s);
    let i = 0;
    while (i < d.dates.length - 1 && d.dates[i] < s) i += 1;
    return i;
  };
  return d.regime_runs
    .map((r) => {
      const i0 = nearest(r.from);
      const i1 = Math.max(nearest(r.to), i0 + 0.6);
      const w = Math.max(x(i1) - x(i0), 1).toFixed(1);
      return `<rect x="${x(i0).toFixed(1)}" y="${PAD.t}" width="${w}" height="${h - PAD.t - PAD.b}" style="fill: var(--regime-${r.label})" opacity="0.16"></rect>`;
    })
    .join("");
}

/** A multi-series line chart with optional regime shading and a hover readout. */
function lineChart(el, d, { series, fmt, bands, zero }) {
  const W = 760;
  const H = el.dataset.tall === "1" ? 330 : 230;
  const x = scaler([0, d.dates.length - 1], [PAD.l, W - PAD.r]);
  const [lo, hi] = extent(series.map((s) => s.values));
  const pad = (hi - lo) * 0.08 || 0.05;
  const yDom = zero ? [Math.min(lo - pad, 0), Math.max(hi + pad, 0)] : [lo - pad, hi + pad];
  const y = scaler(yDom, [H - PAD.b, PAD.t]);

  const grid = ticks(yDom[0], yDom[1])
    .map(
      (v) =>
        `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" class="grid"></line>` +
        `<text x="${PAD.l - 6}" y="${(y(v) + 3.5).toFixed(1)}" class="tick" text-anchor="end">${fmt(v)}</text>`,
    )
    .join("");

  const years = [];
  d.dates.forEach((s, i) => {
    const yr = s.slice(0, 4);
    if (!years.some((t) => t.yr === yr)) years.push({ yr, i });
  });
  const xAxis = years
    .filter((_, k) => k % 2 === 0)
    .map(
      (t) =>
        `<text x="${x(t.i).toFixed(1)}" y="${H - 8}" class="tick" text-anchor="middle">${t.yr}</text>`,
    )
    .join("");

  const lines = series
    .map(
      (s) =>
        `<path d="${path(s.values, x, y)}" fill="none" style="stroke: ${s.stroke.c}" stroke-dasharray="${s.stroke.d}" stroke-width="1.9" stroke-linejoin="round"></path>`,
    )
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(el.dataset.alt || "chart")}">
  ${bands ? regimeBands(d, x, H) : ""}
  ${grid}
  ${zero ? `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}" class="zero"></line>` : ""}
  ${xAxis}
  ${lines}
  <line class="crosshair" x1="0" x2="0" y1="${PAD.t}" y2="${H - PAD.b}" style="display:none"></line>
</svg>
<div class="readout" aria-live="polite"></div>`;

  const svg = $("svg", el);
  const cross = $(".crosshair", el);
  const readout = $(".readout", el);
  const show = (evt) => {
    const box = svg.getBoundingClientRect();
    const px = ((evt.clientX - box.left) / box.width) * W;
    const raw = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (d.dates.length - 1));
    const i = Math.min(Math.max(raw, 0), d.dates.length - 1);
    cross.style.display = "";
    cross.setAttribute("x1", x(i).toFixed(1));
    cross.setAttribute("x2", x(i).toFixed(1));
    readout.innerHTML =
      `<b>${d.dates[i]}</b>` +
      series
        .map(
          (s) =>
            `<span><i style="background:${s.stroke.c}"></i>${esc(s.label)} <b>${fmt(s.values[i])}</b></span>`,
        )
        .join("");
  };
  svg.addEventListener("pointermove", show);
  svg.addEventListener("pointerleave", () => {
    cross.style.display = "none";
    readout.innerHTML = "";
  });
}

/* ------------------------------------------------------------------ panels */

function seriesFor(d, source) {
  return BOOKS.filter(([k]) => state.visible.has(k) && d[source][k]).map(([k, label]) => ({
    key: k,
    label,
    stroke: STROKE_OF[k],
    values: source === "curves" ? d.curves[k][state.cost] : d.drawdowns[k],
  }));
}

function drawEquity(d) {
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
}

/** Annualized next-day return and volatility per regime: the finding, as two bars per state. */
function drawLabelProfile(d) {
  const p = d.label_profile;
  const col = (name) => p.columns.indexOf(name);
  const W = 560;
  const H = 250;
  const gw = (W - PAD.l - PAD.r) / p.rows.length;
  const top = Math.max(...p.rows.flatMap((r) => [r[col("eq_ann_ret")], r[col("eq_ann_vol")]])) * 1.18;
  const y = scaler([0, top], [H - 46, PAD.t]);

  const bars = p.rows
    .map((r, i) => {
      const x0 = PAD.l + i * gw;
      const bw = gw * 0.3;
      const ret = r[col("eq_ann_ret")];
      const vol = r[col("eq_ann_vol")];
      const mid = (x0 + gw / 2).toFixed(1);
      return `
    <rect x="${(x0 + gw * 0.12).toFixed(1)}" y="${y(ret).toFixed(1)}" width="${bw.toFixed(1)}" height="${(H - 46 - y(ret)).toFixed(1)}" style="fill: var(--series-a)"></rect>
    <text x="${(x0 + gw * 0.12 + bw / 2).toFixed(1)}" y="${(y(ret) - 5).toFixed(1)}" class="barlab" text-anchor="middle">${pct(ret, 1)}</text>
    <rect x="${(x0 + gw * 0.5).toFixed(1)}" y="${y(vol).toFixed(1)}" width="${bw.toFixed(1)}" height="${(H - 46 - y(vol)).toFixed(1)}" style="fill: var(--series-b)"></rect>
    <text x="${(x0 + gw * 0.5 + bw / 2).toFixed(1)}" y="${(y(vol) - 5).toFixed(1)}" class="barlab" text-anchor="middle">${pct(vol, 1)}</text>
    <text x="${mid}" y="${H - 28}" class="tick regime-name" style="fill: var(--regime-${i})">${REGIME_NAMES[i] || i}</text>
    <text x="${mid}" y="${H - 14}" class="tick" text-anchor="middle">${r[col("days")]} days, ${r[col("episodes")]} episodes</text>`;
    })
    .join("");

  $("#chart-labels").innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Annualized next-day return and realized volatility by regime label">
  <line x1="${PAD.l}" x2="${W - PAD.r}" y1="${H - 46}" y2="${H - 46}" class="zero"></line>
  ${bars}
</svg>
<p class="legend"><span><i style="background:var(--series-a)"></i>next-day return</span><span><i style="background:var(--series-b)"></i>realized volatility</span></p>`;
}

/** Paired Sharpe differences with their intervals. The question is the gap, not the level. */
function drawPaired(d) {
  const rows = BOOKS.filter(([k]) => k !== state.bench && d.paired[state.bench][k]).map(
    ([k, label]) => ({ key: k, label, ...d.paired[state.bench][k] }),
  );
  const W = 560;
  const rowH = 26;
  const H = rows.length * rowH + 42;
  const lo = Math.min(...rows.map((r) => r.ci[0]), 0);
  const hi = Math.max(...rows.map((r) => r.ci[1]), 0);
  const x = scaler([lo - 0.05, hi + 0.05], [200, W - 34]);

  const marks = rows
    .map((r, i) => {
      const cy = 18 + i * rowH;
      const excludes = r.ci[0] > 0 || r.ci[1] < 0;
      return `
    <text x="192" y="${cy + 4}" class="tick" text-anchor="end">${esc(r.label)}</text>
    <line x1="${x(r.ci[0]).toFixed(1)}" x2="${x(r.ci[1]).toFixed(1)}" y1="${cy}" y2="${cy}" class="ci"></line>
    <circle cx="${x(r.d).toFixed(1)}" cy="${cy}" r="4" style="fill: ${excludes ? "var(--series-a)" : "var(--neutral)"}"></circle>
    <text x="${W - 4}" y="${cy + 4}" class="tick" text-anchor="end">${r.d > 0 ? "+" : ""}${num(r.d)}</text>`;
    })
    .join("");

  $("#chart-paired").innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Paired Sharpe difference against the selected benchmark, with 95 percent intervals">
  <line x1="${x(0).toFixed(1)}" x2="${x(0).toFixed(1)}" y1="6" y2="${H - 26}" class="zero"></line>
  ${marks}
  <text x="${x(0).toFixed(1)}" y="${H - 10}" class="tick" text-anchor="middle">no difference</text>
</svg>`;
}

function drawScorecard(d) {
  const t = state.cost === "net" ? d.scorecard_net : d.scorecard_gross;
  const want = ["sharpe", "sortino", "max_drawdown", "calmar", "turnover_ann"];
  const heads = ["Sharpe", "Sortino", "Max drawdown", "Calmar", "Turnover"];
  const si = t.columns.indexOf("sharpe");
  const order = [...t.index.keys()].sort((a, b) => t.rows[b][si] - t.rows[a][si]);
  const nameOf = Object.fromEntries(BOOKS.map(([k, l]) => [k, l]));

  const body = order
    .map((i) => {
      const key = t.index[i];
      const row = t.rows[i];
      const cell = (c) => {
        const v = row[t.columns.indexOf(c)];
        if (c === "max_drawdown") return pct(v, 1);
        if (c === "turnover_ann") return `${num(v)}x`;
        return num(v);
      };
      const def = d.deflation[key];
      return `<tr${state.visible.has(key) ? ' class="on"' : ""}>
      <th scope="row">${esc(nameOf[key] || key)}</th>
      ${want.map((c) => `<td>${cell(c)}</td>`).join("")}
      <td>${def ? num(def.dsr) : "n/a"}</td>
      <td class="ci-cell">${def ? `${num(def.ci[0])} to ${num(def.ci[1])}` : "n/a"}</td>
    </tr>`;
    })
    .join("");

  const rfNote = d.rf
    ? `the ${pct(d.rf, 2)} the cash sleeve actually paid`
    : "a zero risk-free rate";
  $("#scorecard").innerHTML = `
<table>
  <caption>Every book, ${state.cost === "net" ? `net of ${d.costs_bps} bps per rebalance` : "gross of costs"}. Sharpe is measured against ${rfNote}.</caption>
  <thead><tr><th scope="col">Book</th>${heads.map((h) => `<th scope="col">${h}</th>`).join("")}<th scope="col">Deflated Sharpe</th><th scope="col">95% interval</th></tr></thead>
  <tbody>${body}</tbody>
</table>`;
}

function drawStats(d) {
  const t = d.scorecard_net;
  const get = (book, col) => t.rows[t.index.indexOf(book)][t.columns.indexOf(col)];
  const lead = "hmm_conditional";
  const p = d.paired["60_40"][lead];
  const tiles = [
    ["Max drawdown", pct(get(lead, "max_drawdown"), 1), `60/40 took ${pct(get("60_40", "max_drawdown"), 1)}`],
    ["Calmar", num(get(lead, "calmar")), `60/40 managed ${num(get("60_40", "calmar"))}`],
    ["Sharpe", num(get(lead, "sharpe")), `60/40 managed ${num(get("60_40", "sharpe"))}`],
    [
      "Sharpe gap vs 60/40",
      `${p.d > 0 ? "+" : ""}${num(p.d)}`,
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

function render() {
  const d = DATA[state.market];
  if (!d) return;
  $$("[data-oos]").forEach((el) => {
    el.textContent = `${d.oos.start} to ${d.oos.end}, n = ${d.oos.n.toLocaleString()}`;
  });
  $$("[data-market-name]").forEach((el) => {
    el.textContent = state.market === "us" ? "US" : "India";
  });
  drawStats(d);
  drawEquity(d);
  drawLabelProfile(d);
  drawPaired(d);
  drawScorecard(d);
}

function group(attr, onPick) {
  $$(`[data-${attr}]`).forEach((btn) =>
    btn.addEventListener("click", () => {
      $$(`[data-${attr}]`).forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      onPick(btn.dataset[attr]);
    }),
  );
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
    drawPaired(DATA[state.market]);
  });
  render();
}

boot();
