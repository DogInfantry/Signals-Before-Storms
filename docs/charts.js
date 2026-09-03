/* Signals-Before-Storms: the shared SVG chart kernel.

   Two pages now draw the same exported results, so the drawing moved here and each page keeps
   only its own state. Native ES modules, because a module is a language feature rather than a
   library: PRODUCT.md rules out a build step and a JS dependency, and this needs neither.

   Every function here is PURE DRAWING. Nothing in this file computes a statistic. The numbers
   arrive already decided from tools/export_site_data.py, which uses the same functions the
   printed scorecard uses, so the page and the README cannot drift apart. A statistic recomputed
   in JS would be a second implementation that can silently disagree, and the one on the page
   would be the untested one.

   Colour comes only from the tokens in style.css, which mirror src/regime_shift/style.py, which
   is validated by tools/validate_palette.py. No hex literal appears below. */

/* ------------------------------------------------------------------ identity */

// Order is fixed so a book keeps its stroke when others are toggled off, and the labels are the
// ones the README uses, spelled for a reader rather than as a dict key.
export const BOOKS = [
  ["hmm_conditional", "HMM, conditional moments", "strategy"],
  ["hmm_drawdown_feat", "HMM + drawdown feature", "strategy"],
  ["vol_rule_ablation", "Volatility rule (no HMM)", "ablation"],
  ["jump_regime", "Jump model", "strategy"],
  ["hmm_vol_targeted", "HMM, volatility targeted", "strategy"],
  ["hmm_unconditional", "HMM, unconditional moments", "strategy"],
  ["60_40", "Static 60/40", "benchmark"],
  ["equal_weight", "Equal weight", "benchmark"],
];

// Two validated hues plus two neutrals, each in solid and dashed. That is eight separable series
// without inventing a categorical palette: style.py only clears its contrast and colour-vision
// floors for the pairs it actually validated, and this reuses those rather than guessing six
// more. Distinction past four series comes from dash, not hue.
export const STROKES = [
  { c: "var(--series-a)", d: "" },
  { c: "var(--series-b)", d: "" },
  { c: "var(--neutral)", d: "5 4" },
  { c: "var(--ink-soft)", d: "2 3" },
  { c: "var(--series-a)", d: "5 4" },
  { c: "var(--series-b)", d: "2 3" },
  { c: "var(--neutral)", d: "" },
  { c: "var(--ink-soft)", d: "5 4" },
];
export const STROKE_OF = Object.fromEntries(BOOKS.map(([k], i) => [k, STROKES[i % STROKES.length]]));
export const NAME_OF = Object.fromEntries(BOOKS.map(([k, l]) => [k, l]));

export const REGIME_NAMES = ["Bull", "Bear", "Crisis"];

// The equity instrument each universe actually holds, for the buy-and-hold reference line.
export const EQUITY_NAME = { india: "NIFTY 50", us: "SPY" };

// w_cash on India, w_bond on the US: the column set genuinely differs by universe, so it is read
// off the payload rather than hardcoded, and only the display spelling lives here.
export const SLEEVE_NAME = {
  w_equity: "Equity",
  w_cash: "Cash",
  w_bond: "Bonds",
  w_gold: "Gold",
};
export const SLEEVE_FILL = {
  w_equity: "var(--series-a)",
  w_cash: "var(--neutral)",
  w_bond: "var(--neutral)",
  w_gold: "var(--series-b)",
};

/* ------------------------------------------------------------------ helpers */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
export const pct = (x, nd = 1) => (x == null ? "n/a" : `${(x * 100).toFixed(nd)}%`);
export const num = (x, nd = 2) => (x == null ? "n/a" : x.toFixed(nd));
export const signed = (x, nd = 2) => (x == null ? "n/a" : `${x > 0 ? "+" : ""}${x.toFixed(nd)}`);
export const col = (frame, name) => frame.columns.indexOf(name);

/* ------------------------------------------------------------------ primitives */

export const PAD = { l: 46, r: 12, t: 10, b: 26 };

export function scaler(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (v) => r0 + ((v - d0) / span) * (r1 - r0);
}

export function extent(arrays) {
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

export function path(values, x, y) {
  let d = "";
  values.forEach((v, i) => {
    if (v == null) return;
    d += `${d ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  });
  return d;
}

export function ticks(lo, hi, count = 4) {
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
  return out;
}

/* ------------------------------------------------------------------ motion

   Three utilities, all ported from ledger/components/Sweep.tsx, which is the version of this
   already proven in production on the sibling site.

   REDUCED MOTION IS NOT A DEGRADED PATH. Sweep.tsx sets its progress to 1 when the query
   matches, so a reader with motion off lands on the FINISHED state and loses nothing. Anything
   here that animates must default to finished, never to empty. */

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Fire once when an element first enters the viewport. What most reveals actually need. */
export function reveal(el, fn, { rootMargin = "0px 0px -12% 0px" } = {}) {
  if (!el) return () => {};
  if (reducedMotion() || !("IntersectionObserver" in window)) {
    fn();
    return () => {};
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        io.disconnect();
        fn();
      }
    },
    { rootMargin, threshold: 0.15 },
  );
  io.observe(el);
  return () => io.disconnect();
}

/** Scroll position through a tall section as 0..1. For the one beat that drives a parameter.
 *
 *  ONE getBoundingClientRect per animation frame for the WHOLE section, never one per mark.
 *  Sweep.tsx measures the plate, not its eleven rows, for exactly this reason. */
export function scrollProgress(el, cb) {
  if (!el) return () => {};
  if (reducedMotion()) {
    cb(1);
    return () => {};
  }
  let frame = 0;
  const tick = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const r = el.getBoundingClientRect();
      const total = r.height - window.innerHeight;
      cb(total <= 0 ? 1 : Math.min(1, Math.max(0, -r.top / total)));
    });
  };
  tick();
  window.addEventListener("scroll", tick, { passive: true });
  window.addEventListener("resize", tick);
  return () => {
    window.removeEventListener("scroll", tick);
    window.removeEventListener("resize", tick);
    if (frame) cancelAnimationFrame(frame);
  };
}

/** Linked brushing. Charts sharing one date axis move one cursor, so a reader comparing an
 *  equity curve against its drawdown is reading the same day in both. The one idea worth taking
 *  from glue-viz, at a handful of lines and no dependency.
 *
 *  Handlers are cleared by the page controller before every full redraw, or each render would
 *  leave its subscribers attached to detached DOM and leak one closure per chart per toggle. */
export const cursorBus = {
  subs: new Set(),
  on(fn) {
    this.subs.add(fn);
    return () => this.subs.delete(fn);
  },
  emit(i) {
    for (const fn of this.subs) fn(i);
  },
  clear() {
    this.subs.clear();
  },
};

/** Cubic ease-out. Bars that decelerate into place read as settling rather than as snapping. */
export const ease = (t) => 1 - (1 - Math.min(1, Math.max(0, t))) ** 3;

/** A mutually exclusive button group, wired to aria-pressed.
 *
 *  Reads the value with getAttribute rather than through dataset. dataset camel-cases its keys,
 *  so dataset["score-market"] is undefined while dataset.scoreMarket is not, and a group named
 *  with more than one word silently handed its callback undefined. That shipped for exactly as
 *  long as every group in this project had a one-word name. It fails loudly nowhere, which is
 *  why it lives here once instead of in each controller. */
export function group(attr, onPick, root = document) {
  const btns = $$(`[data-${attr}]`, root);
  btns.forEach((btn) =>
    btn.addEventListener("click", () => {
      btns.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      onPick(btn.getAttribute(`data-${attr}`));
    }),
  );
}

/* ------------------------------------------------------------------ charts */

/** Regime spans as background washes, mapped from run-length dates onto plot indices. */
export function regimeBands(d, x, h) {
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

/** A multi-series line chart with optional regime shading and a linked hover readout. */
export function lineChart(el, d, { series, fmt, bands, zero, link = true }) {
  if (!el) return;
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

  const place = (i) => {
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
  const clear = () => {
    cross.style.display = "none";
    readout.innerHTML = "";
  };
  const indexAt = (evt) => {
    const box = svg.getBoundingClientRect();
    const px = ((evt.clientX - box.left) / box.width) * W;
    const raw = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (d.dates.length - 1));
    return Math.min(Math.max(raw, 0), d.dates.length - 1);
  };

  // Every linked chart both emits and listens. Emitting also places this chart's own cursor,
  // which is why the pointer handler does not call place() directly: one path, not two.
  if (link) {
    cursorBus.on((i) => (i == null ? clear() : place(i)));
    svg.addEventListener("pointermove", (e) => cursorBus.emit(indexAt(e)));
    svg.addEventListener("pointerleave", () => cursorBus.emit(null));
  } else {
    svg.addEventListener("pointermove", (e) => place(indexAt(e)));
    svg.addEventListener("pointerleave", clear);
  }
}

/** Annualized next-day return and volatility per regime: the finding, as two bars per state.
 *
 *  `progress` drives the two-stage reveal that is the thesis of this project. Volatility rises
 *  first and lands monotone, which is the model doing exactly the job it was given. Then return
 *  rises and lands BACKWARDS. Default 1, so every caller that does not animate gets the finished
 *  chart, and so does a reader with prefers-reduced-motion set. */
export function labelProfile(el, d, { progress = 1 } = {}) {
  if (!el) return;
  const p = d.label_profile;
  const c = (name) => col(p, name);
  const W = 560;
  const H = 250;
  const base = H - 46;
  const gw = (W - PAD.l - PAD.r) / p.rows.length;
  const top = Math.max(...p.rows.flatMap((r) => [r[c("eq_ann_ret")], r[c("eq_ann_vol")]])) * 1.18;
  const y = scaler([0, top], [base, PAD.t]);

  // Volatility occupies the first half of the scroll, return the second.
  const kVol = ease(progress / 0.5);
  const kRet = ease((progress - 0.5) / 0.5);

  const bar = (x0, bw, v, fill, k) => {
    const h = Math.max((base - y(v)) * k, 0);
    return (
      `<rect x="${x0.toFixed(1)}" y="${(base - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" style="fill: ${fill}"></rect>` +
      `<text x="${(x0 + bw / 2).toFixed(1)}" y="${(base - h - 5).toFixed(1)}" class="barlab" text-anchor="middle" opacity="${k.toFixed(2)}">${pct(v, 1)}</text>`
    );
  };

  const bars = p.rows
    .map((r, i) => {
      const x0 = PAD.l + i * gw;
      const bw = gw * 0.3;
      const mid = (x0 + gw / 2).toFixed(1);
      return (
        bar(x0 + gw * 0.12, bw, r[c("eq_ann_ret")], "var(--series-a)", kRet) +
        bar(x0 + gw * 0.5, bw, r[c("eq_ann_vol")], "var(--series-b)", kVol) +
        `<text x="${mid}" y="${H - 28}" class="tick regime-name" text-anchor="middle" style="fill: var(--regime-${i})">${REGIME_NAMES[i] || i}</text>` +
        `<text x="${mid}" y="${H - 14}" class="tick" text-anchor="middle">${r[c("days")]} days, ${r[c("episodes")]} episodes</text>`
      );
    })
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Annualized next-day return and realized volatility by regime label. Volatility rises with the label, exactly as intended. So does return, and that is the wrong direction.">
  <line x1="${PAD.l}" x2="${W - PAD.r}" y1="${base}" y2="${base}" class="zero"></line>
  ${bars}
</svg>
<p class="legend"><span style="opacity:${kRet.toFixed(2)}"><i style="background:var(--series-a)"></i>next-day return</span><span style="opacity:${kVol.toFixed(2)}"><i style="background:var(--series-b)"></i>realized volatility</span></p>`;
}

/** Paired Sharpe differences with their intervals. The question is the gap, not the level. */
export function pairedForest(el, d, { bench = "60_40" } = {}) {
  if (!el) return;
  const rows = BOOKS.filter(([k]) => k !== bench && d.paired[bench][k]).map(([k, label]) => ({
    key: k,
    label,
    ...d.paired[bench][k],
  }));
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
    <text x="${W - 4}" y="${cy + 4}" class="tick" text-anchor="end">${signed(r.d)}</text>`;
    })
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Paired Sharpe difference against the selected benchmark, with 95 percent intervals. Every interval spans zero.">
  <line x1="${x(0).toFixed(1)}" x2="${x(0).toFixed(1)}" y1="6" y2="${H - 26}" class="zero"></line>
  ${marks}
  <text x="${x(0).toFixed(1)}" y="${H - 10}" class="tick" text-anchor="middle">no difference</text>
</svg>`;
}

/** Every book, sortable. Clicking a header re-sorts; the caller decides what a row click does.
 *
 *  Sorting and row-picking are the two things a pivot-table component would have been imported
 *  for. They are a comparator and a click handler, so no component is imported. */
export function scorecard(
  el,
  d,
  { cost = "net", sort = "sharpe", desc = true, visible, onSort, onPick } = {},
) {
  if (!el) return;
  const t = cost === "net" ? d.scorecard_net : d.scorecard_gross;
  const want = ["sharpe", "sortino", "max_drawdown", "calmar", "turnover_ann"];
  const heads = ["Sharpe", "Sortino", "Max drawdown", "Calmar", "Turnover"];
  const key = (i) => {
    if (sort !== "dsr") return t.rows[i][col(t, sort)];
    const def = d.deflation[t.index[i]];
    return def ? def.dsr : -Infinity;
  };
  const order = [...t.index.keys()].sort((a, b) => (desc ? key(b) - key(a) : key(a) - key(b)));

  const cell = (row, c) => {
    const v = row[col(t, c)];
    if (c === "max_drawdown") return pct(v, 1);
    if (c === "turnover_ann") return `${num(v)}x`;
    return num(v);
  };
  const arrow = (c) => (sort === c ? (desc ? " ▾" : " ▴") : "");
  const th = (c, label) =>
    `<th scope="col"><button type="button" data-sort="${c}">${esc(label)}${arrow(c)}</button></th>`;

  const body = order
    .map((i) => {
      const bk = t.index[i];
      const def = d.deflation[bk];
      const on = visible && visible.has(bk);
      const name = esc(NAME_OF[bk] || bk);
      return `<tr${on ? ' class="on"' : ""}>
      <th scope="row">${onPick ? `<button type="button" data-book="${esc(bk)}">${name}</button>` : name}</th>
      ${want.map((c) => `<td>${cell(t.rows[i], c)}</td>`).join("")}
      <td>${def ? num(def.dsr) : "n/a"}</td>
      <td class="ci-cell">${def ? `${num(def.ci[0])} to ${num(def.ci[1])}` : "n/a"}</td>
    </tr>`;
    })
    .join("");

  const rfNote = d.rf ? `the ${pct(d.rf, 2)} the cash sleeve actually paid` : "a zero risk-free rate";
  el.innerHTML = `
<table>
  <caption>Every book, ${cost === "net" ? `net of ${d.costs_bps} bps per rebalance` : "gross of costs"}. Sharpe is measured against ${rfNote}. Click a column to sort${onPick ? ", click a book to plot it" : ""}.</caption>
  <thead><tr><th scope="col">Book</th>${want.map((c, i) => th(c, heads[i])).join("")}${th("dsr", "Deflated Sharpe")}<th scope="col">95% interval</th></tr></thead>
  <tbody>${body}</tbody>
</table>`;

  if (onSort) {
    $$("[data-sort]", el).forEach((b) => b.addEventListener("click", () => onSort(b.dataset.sort)));
  }
  if (onPick) {
    $$("[data-book]", el).forEach((b) => b.addEventListener("click", () => onPick(b.dataset.book)));
  }
}

/** Mean weight per sleeve in each regime. The panel never showed what the strategy HOLDS, which
 *  is what makes the diagnosis legible: this book is not too risky, it is far too de-risked.
 *
 *  A 100 percent stacked bar, direct-labelled inside each segment, with the equity share
 *  repeated below it. Position and text carry the reading and colour only reinforces it, which
 *  is what makes the series-a / neutral / series-b set legitimate for three categories. Measured
 *  with tools/validate_palette.py: worst pair separates by 36.5 dE against a floor of 8, and all
 *  three clear 3:1 against the surface at 5.45, 9.40 and 4.43. */
export function weightStack(el, d) {
  if (!el) return;
  const w = d.mean_weights;
  const W = 560;
  const rowH = 50;
  const H = w.rows.length * rowH + 26;
  const x0 = 66;
  const span = W - x0 - 12;

  const rows = w.rows
    .map((row, i) => {
      const yTop = i * rowH + 8;
      let acc = 0;
      const segs = row
        .map((v, j) => {
          const c = w.columns[j];
          const left = x0 + acc * span;
          const width = v * span;
          acc += v;
          const label =
            width > 62
              ? `<text x="${(left + width / 2).toFixed(1)}" y="${(yTop + 18).toFixed(1)}" class="seg" text-anchor="middle">${esc(SLEEVE_NAME[c] || c)} ${pct(v, 0)}</text>`
              : "";
          return `<rect x="${left.toFixed(1)}" y="${yTop}" width="${Math.max(width, 0.5).toFixed(1)}" height="27" style="fill: ${SLEEVE_FILL[c] || "var(--neutral)"}"></rect>${label}`;
        })
        .join("");
      return (
        segs +
        `<text x="${x0 - 8}" y="${(yTop + 19).toFixed(1)}" class="tick regime-name" text-anchor="end" style="fill: var(--regime-${i})">${REGIME_NAMES[i] || i}</text>` +
        `<text x="${x0}" y="${(yTop + 41).toFixed(1)}" class="tick">equity ${pct(row[col(w, "w_equity")], 0)}</text>`
      );
    })
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mean portfolio weight per sleeve in each regime. Equity never reaches a quarter of the book, even in the calmest state.">
  ${rows}
</svg>`;
}

/** Episodes, not days, and what happens when the largest one is dropped.
 *
 *  Two dots joined by a rule: the label's annualized return over every episode, and its return
 *  with the single longest episode removed. India's crisis label moves +18.4% to +53.6% on 14
 *  episodes, which is the whole "days are not a sample size" argument as a length on the page.
 *  Encoded by position and by open-versus-filled, so it needs no colour at all. */
export function episodeDumbbell(el, d) {
  if (!el) return;
  const p = d.episode_profile;
  const W = 560;
  const rowH = 46;
  const H = p.rows.length * rowH + 44;
  const all = p.rows.flatMap((r) => [r[col(p, "ann_ret")], r[col(p, "ann_ret_ex_largest")]]);
  const lo = Math.min(...all, 0);
  const hi = Math.max(...all);
  const x = scaler([lo - 0.04, hi + 0.08], [104, W - 18]);

  const rows = p.rows
    .map((r, i) => {
      const cy = 22 + i * rowH;
      const a = r[col(p, "ann_ret")];
      const b = r[col(p, "ann_ret_ex_largest")];
      const far = Math.abs(x(b) - x(a)) > 34;
      return `
    <text x="96" y="${cy + 4}" class="tick regime-name" text-anchor="end" style="fill: var(--regime-${i})">${REGIME_NAMES[i] || i}</text>
    <line x1="${x(a).toFixed(1)}" x2="${x(b).toFixed(1)}" y1="${cy}" y2="${cy}" class="dumbbell"></line>
    <circle cx="${x(a).toFixed(1)}" cy="${cy}" r="4.5" class="dot-open"></circle>
    <circle cx="${x(b).toFixed(1)}" cy="${cy}" r="4.5" class="dot-fill"></circle>
    ${far ? `<text x="${x(a).toFixed(1)}" y="${cy - 10}" class="tick" text-anchor="middle">${pct(a, 1)}</text>` : ""}
    <text x="${x(b).toFixed(1)}" y="${cy - 10}" class="barlab" text-anchor="middle">${pct(b, 1)}</text>
    <text x="96" y="${cy + 18}" class="tick" text-anchor="end">${r[col(p, "episodes")]} episodes</text>`;
    })
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Annualized return per regime over all episodes, and again with the single longest episode dropped. The crisis label moves furthest, because it has the fewest episodes.">
  <line x1="${x(0).toFixed(1)}" x2="${x(0).toFixed(1)}" y1="6" y2="${H - 30}" class="zero"></line>
  ${rows}
  <text x="${x(0).toFixed(1)}" y="${H - 14}" class="tick" text-anchor="middle">0%</text>
</svg>
<p class="legend"><span><i class="key-open"></i>all episodes</span><span><i class="key-fill"></i>largest episode dropped</span></p>`;
}

/** Per-session transition probabilities, as a matrix a reader can read a row off.
 *
 *  Shaded by ink opacity rather than by the regime ramp: a cell holds a continuous probability,
 *  and painting it in the ordinal state colours would put two different meanings on one channel.
 *  The row and column headers carry the state colour instead. */
export function transitionHeatmap(el, d) {
  if (!el) return;
  const n = d.transition.length;
  const W = 400;
  const cell = 74;
  const left = 96;
  const topPad = 32;
  const H = topPad + n * cell + 10;

  const heads = d.transition
    .map(
      (_, j) =>
        `<text x="${(left + j * cell + (cell - 3) / 2).toFixed(1)}" y="${topPad - 11}" class="tick regime-name" text-anchor="middle" style="fill: var(--regime-${j})">${REGIME_NAMES[j] || j}</text>`,
    )
    .join("");

  const rowHeads = d.transition
    .map(
      (_, i) =>
        `<text x="${left - 10}" y="${(topPad + i * cell + cell / 2).toFixed(1)}" class="tick regime-name" text-anchor="end" style="fill: var(--regime-${i})">${REGIME_NAMES[i] || i}</text>`,
    )
    .join("");

  const cells = d.transition
    .map((row, i) =>
      row
        .map((v, j) => {
          const x = left + j * cell;
          const y = topPad + i * cell;
          // Square root, so the off-diagonal probabilities stay visible at all against a
          // diagonal that sits above 0.95 on every row of both universes.
          const o = Math.sqrt(v) * 0.82;
          return (
            `<rect x="${x}" y="${y}" width="${cell - 3}" height="${cell - 3}" class="cellbg" opacity="${o.toFixed(3)}"></rect>` +
            `<text x="${x + (cell - 3) / 2}" y="${y + (cell - 3) / 2 + 4}" class="cellv" text-anchor="middle" data-hot="${v > 0.5 ? "1" : "0"}">${(v * 100).toFixed(1)}</text>`
          );
        })
        .join(""),
    )
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Per-session transition probabilities between regimes, in percent. The diagonal is above 95 percent on every row, which is why regimes persist at all.">
  <text x="${left - 10}" y="${topPad - 11}" class="tick" text-anchor="end">from, to</text>
  ${heads}${rowHeads}${cells}
</svg>`;
}

/** How long a state lasts, and how much of the sample it owns. */
export function dwellBars(el, d) {
  if (!el) return;
  const keys = Object.keys(d.dwell).sort();
  const W = 400;
  const rowH = 54;
  const H = keys.length * rowH + 16;
  const x0 = 96;
  const top = Math.max(...keys.map((k) => d.dwell[k])) * 1.3;
  const x = scaler([0, top], [x0, W - 14]);
  const totalDays = keys.reduce((s, k) => s + (d.regime_counts[k] || 0), 0);

  const rows = keys
    .map((k, i) => {
      const y = i * rowH + 12;
      const v = d.dwell[k];
      const days = d.regime_counts[k] || 0;
      const share = totalDays ? days / totalDays : 0;
      return `
    <text x="${x0 - 8}" y="${y + 15}" class="tick regime-name" text-anchor="end" style="fill: var(--regime-${k})">${REGIME_NAMES[+k] || k}</text>
    <rect x="${x0}" y="${y}" width="${Math.max(x(v) - x0, 1).toFixed(1)}" height="21" style="fill: var(--regime-${k})" opacity="0.85"></rect>
    <text x="${(x(v) + 7).toFixed(1)}" y="${y + 15}" class="barlab">${num(v, 1)} sessions</text>
    <text x="${x0}" y="${y + 38}" class="tick">${days} days out of sample, ${pct(share, 0)} of it</text>`;
    })
    .join("");

  el.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mean run length per regime in sessions, and the share of the out-of-sample window each regime occupies.">
  ${rows}
</svg>`;
}

/** Buy and hold, with the walk-forward regime path shaded behind it.
 *
 *  No new drawer: this IS lineChart with one series and bands on, which is why equity_level was
 *  exported in the first place. */
export function regimeOverlay(el, d, { market = "india" } = {}) {
  lineChart(el, d, {
    series: [
      {
        label: `${EQUITY_NAME[market] || "Equity"}, buy and hold`,
        stroke: { c: "var(--ink)", d: "" },
        values: d.equity_level,
      },
    ],
    fmt: (v) => `${v.toFixed(1)}x`,
    bands: true,
    zero: false,
  });
}
