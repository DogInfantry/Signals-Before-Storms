/* Regime Monitor.
 *
 * Hand-built SVG, no framework, no build step, no external request, so the Vercel project stays
 * a plain static Root Directory.
 *
 * The page RENDERS verdicts, it never COMPUTES them. `vol_monotone`, `ret_ordering` and
 * `p_crisis_21` all arrive decided from tools/export_monitor_data.py. Recomputing a claim in
 * JS would mean two implementations of the same statistic that can silently disagree, and the
 * one on the page would be the untested one.
 */

const REGIME_COLOR = ["var(--regime-0)", "var(--regime-1)", "var(--regime-2)"];
const state = { data: null, filter: "All", open: null };

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (x, nd = 1) => (x === null || x === undefined ? "n/a" : (x * 100).toFixed(nd) + "%");

/** Probabilities only. A small nonzero probability rounded to "0%" claims impossibility, which
 *  is a different and much stronger statement than "unlikely" -- and it is the claim a reader
 *  acts on. Floor it instead of rounding it away. */
const prob = (x) => {
  if (x === null || x === undefined) return "n/a";
  if (x > 0 && x < 0.01) return "<1%";
  if (x < 1 && x > 0.99) return ">99%";
  return (x * 100).toFixed(0) + "%";
};
const day = (s) => new Date(s + "T00:00:00Z").getTime();

function fmtDate(s) {
  const d = new Date(s + "T00:00:00Z");
  return d.toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

/* -- sparkline ------------------------------------------------------------ */

/** Price line with regime bands behind it. Bands are clipped to the chart window, but the
 *  payload keeps each run's TRUE start, so a regime that began before the window still reports
 *  its real start date in the readout even though the band starts at the left edge. */
function sparkline(asset) {
  const W = 320, H = 64, P = 2;
  const xs = asset.dates.map(day);
  const ys = asset.prices;
  if (!xs.length) return "";

  const x0 = xs[0], x1 = xs[xs.length - 1];
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const sx = (v) => ((v - x0) / (x1 - x0 || 1)) * W;
  const sy = (v) => H - P - ((v - lo) / (hi - lo || 1)) * (H - 2 * P);

  // Each run is shaded up to the NEXT run's START, not to its own end. Shading to its own end
  // gives a one-session run zero calendar width, so it is dropped entirely and leaves a white
  // stripe where a regime certainly was. Measured before this fix: band coverage ran 68-96% of
  // the axis, worst on the fastest-flipping markets (NIFTY 50, 3.6-session mean dwell, rendered
  // 18 bands where the label path holds roughly 190). Chaining to the next start also closes
  // the weekend gap between consecutive runs, and makes coverage total by construction.
  const runs = asset.runs;
  const bands = runs.map((r, i) => {
    const from = day(r.from);
    const to = i + 1 < runs.length ? day(runs[i + 1].from) : day(r.to) + 864e5;
    const a = Math.max(sx(from), 0);
    const b = Math.min(sx(to), W);
    if (b <= a) return "";
    return `<rect x="${a.toFixed(2)}" y="0" width="${Math.max(b - a, 0.5).toFixed(2)}"
      height="${H}" fill="${REGIME_COLOR[r.label]}" opacity=".18"/>`;
  }).join("");

  const d = ys.map((v, i) => `${i ? "L" : "M"}${sx(xs[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"
    aria-label="${esc(asset.name)} price over the display window, shaded by volatility regime">
    ${bands}<path d="${d}" fill="none" stroke="var(--ink)" stroke-width="1.2"
      vector-effect="non-scaling-stroke"/></svg>`;
}

/* -- card ----------------------------------------------------------------- */

function currentVol(asset) {
  const lp = asset.label_profile;
  const row = lp.index.indexOf(String(asset.current.label));
  return row < 0 ? null : lp.rows[row][lp.columns.indexOf("eq_ann_vol")];
}

function card(asset, names) {
  const c = asset.current;
  const conf = c.proba[c.label];
  const vol = currentVol(asset);
  const size = asset.position[String(c.label)];
  const crisis = state.data.n_states - 1;

  // Already in Crisis? "Will it enter Crisis" is trivially ~1 and says nothing, so the exporter
  // ships null and the card answers the question that IS still open: how long these last.
  const risk = c.label === crisis
    ? { k: `Typical ${names[crisis]} stay`, v: `${asset.dwell[String(crisis)] ?? "n/a"} sessions` }
    : {
        k: `${names[crisis]} within ${state.data.crisis_horizon} sessions`,
        v: prob(asset.p_crisis_21),
      };

  return `<button class="card" data-ticker="${esc(asset.ticker)}"
      aria-expanded="${state.open === asset.ticker}">
    <div class="card__head">
      <div>
        <div class="card__name">${esc(asset.name)}</div>
        <div class="card__meta">${esc(asset.ticker)} &middot; ${esc(asset.asset_class)}</div>
      </div>
      <span class="chip chip--${c.label}"
        style="background:${REGIME_COLOR[c.label]}">${esc(names[c.label])}</span>
    </div>
    <div class="conf">
      <span>${prob(conf)} confident</span>
      <span class="conf__bar"><span class="conf__fill"
        style="width:${(conf * 100).toFixed(1)}%;background:${REGIME_COLOR[c.label]}"></span></span>
    </div>
    ${sparkline(asset)}
    <div class="readout">
      <div><div class="readout__k">In regime</div>
        <div class="readout__v">${c.sessions_in_run} sessions</div></div>
      <div><div class="readout__k">Since</div>
        <div class="readout__v">${fmtDate(c.since)}</div></div>
      <div><div class="readout__k">Regime vol</div>
        <div class="readout__v">${pct(vol)}</div></div>
      <div><div class="readout__k">Implied size</div>
        <div class="readout__v">${size === null || size === undefined ? "n/a" : pct(size, 0)}</div></div>
      <div style="grid-column:1/-1"><div class="readout__k">${esc(risk.k)}</div>
        <div class="readout__v">${esc(risk.v)}</div></div>
    </div>
  </button>`;
}

/* -- expanded detail ------------------------------------------------------ */

function detail(asset, names) {
  const lp = asset.label_profile;
  const col = (n) => lp.columns.indexOf(n);

  const tmat = `<table class="tmat"><thead><tr><th>from \\ to</th>
    ${names.map((n) => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody>
    ${asset.transition.map((row, i) => `<tr><th>${esc(names[i])}</th>${row.map((v) =>
      `<td>${(v * 100).toFixed(1)}</td>`).join("")}</tr>`).join("")}
    </tbody></table>`;

  const profile = `<table><thead><tr><th>Regime</th><th>Ann. return</th><th>Ann. vol</th>
    <th>Days</th><th>Episodes</th><th>Size</th></tr></thead><tbody>
    ${lp.index.map((k, r) => `<tr>
      <th><span class="chip chip--${+k}"
        style="background:${REGIME_COLOR[+k]}">${esc(names[+k])}</span></th>
      <td>${pct(lp.rows[r][col("eq_ann_ret")])}</td>
      <td>${pct(lp.rows[r][col("eq_ann_vol")])}</td>
      <td>${lp.rows[r][col("days")]}</td>
      <td>${lp.rows[r][col("episodes")]}</td>
      <td>${asset.position[k] === null || asset.position[k] === undefined
        ? "n/a" : pct(asset.position[k], 0)}</td>
    </tr>`).join("")}</tbody></table>`;

  const notes = asset.notes.map((n) => `<p class="note">${esc(n)}</p>`).join("");

  return `<div class="detail">
    <h3>${esc(asset.name)} &middot; ${esc(asset.ticker)}</h3>
    <p class="detail__sub">${asset.bars} sessions priced, ${asset.oos.n} labelled out of sample
      from ${fmtDate(asset.oos.start)}. Newest completed session ${fmtDate(asset.as_of)}.</p>
    <div class="detail__grid">
      <div>
        <h4>Transition matrix, % chance per session</h4>
        <div class="scroll">${tmat}</div>
        <p class="detail__sub" style="margin:.6rem 0 0">Read a row: given today's regime, where
          tomorrow lands. The diagonal is persistence, which is why regimes last at all. Counted
          off the out-of-sample label path above, not read out of the model's fitted parameter,
          so it describes the bands actually drawn on the chart.</p>
      </div>
      <div>
        <h4>What each regime did next, at the traded one-day lag</h4>
        <div class="scroll">${profile}</div>
        <p class="detail__sub" style="margin:.6rem 0 0">Volatility is what the model sorts on, so
          it orders. Whether <em>return</em> orders is the open question, and episodes are the
          sample size that supports any answer to it, not days.</p>
      </div>
    </div>
    ${notes}
  </div>`;
}

/* -- replication table ---------------------------------------------------- */

const VERDICT = {
  backwards: ['<span class="verdict-b">backwards</span>', "calm pays least, violent pays most"],
  ascending: ['<span class="verdict-a">ascending</span>', "calm pays most, as intuition expects"],
  mixed: ['<span class="verdict-n">unordered</span>', "no monotone ranking either way"],
  "n/e": ['<span class="verdict-n">n/e</span>', "too few crisis episodes to judge"],
};

function replication() {
  const d = state.data, r = d.replication, names = d.regime_names;
  const other = r.judged - r.backwards;

  $("#replication-lede").innerHTML =
    `The volatility ordering replicates completely: realized volatility rises with the state on
     <strong>${r.vol_monotone} of ${r.total}</strong> markets. The <em>return</em> ordering does
     not. It runs backwards on <strong>${r.backwards} of ${r.judged}</strong> and some other way
     on ${other}. That is the stronger negative, and it sharpens the research finding rather than
     softening it: these states do not rank returns at all, and the backwards ordering measured
     on two universes was one draw from an unordered distribution rather than a law. A ranking
     that changes sign from market to market cannot be traded in either direction.`;

  $("#repl-table").innerHTML = `<thead><tr>
      <th>Market</th><th>Vol ordering</th><th>Return ordering</th>
      ${names.map((n) => `<th>${esc(n)} return</th>`).join("")}
      <th>Crisis episodes</th></tr></thead><tbody>
    ${d.assets.map((a) => {
      const lp = a.label_profile, ci = lp.columns.indexOf("eq_ann_ret");
      const cells = names.map((_, k) => {
        const row = lp.index.indexOf(String(k));
        return `<td>${row < 0 ? "n/a" : pct(lp.rows[row][ci])}</td>`;
      }).join("");
      return `<tr><th>${esc(a.name)}</th>
        <td>${a.vol_monotone ? "monotone" : '<span class="verdict-n">no</span>'}</td>
        <td title="${esc(VERDICT[a.ret_ordering][1])}">${VERDICT[a.ret_ordering][0]}</td>
        ${cells}<td>${a.crisis_episodes}</td></tr>`;
    }).join("")}</tbody>`;
}

/* -- render --------------------------------------------------------------- */

function render() {
  const d = state.data, names = d.regime_names;
  const shown = d.assets.filter((a) => state.filter === "All" || a.asset_class === state.filter);

  $("#board").innerHTML = shown.map((a) =>
    card(a, names) + (state.open === a.ticker ? detail(a, names) : "")).join("");

  $("#board").querySelectorAll(".card").forEach((el) => {
    el.addEventListener("click", () => {
      state.open = state.open === el.dataset.ticker ? null : el.dataset.ticker;
      render();
    });
  });
}

function tiles() {
  const d = state.data, names = d.regime_names, crisis = d.n_states - 1;
  const inCrisis = d.assets.filter((a) => a.current.label === crisis);
  const calm = d.assets.filter((a) => a.current.label === 0).length;

  const t = [
    ["Markets tracked", d.assets.length,
      `${new Set(d.assets.map((a) => a.asset_class)).size} asset classes`],
    [`In ${names[crisis]} now`, inCrisis.length,
      inCrisis.length ? inCrisis.map((a) => a.ticker).join(", ") : "none"],
    [`In ${names[0]} now`, calm, "risk budget unconstrained"],
    ["Vol ordering holds", `${d.replication.vol_monotone}/${d.replication.total}`,
      "what the model is for"],
    ["Return ordering backwards", `${d.replication.backwards}/${d.replication.judged}`,
      "what it was hoped to be"],
  ];
  $("#tiles").innerHTML = t.map(([k, v, s]) =>
    `<div class="tile"><div class="tile__k">${esc(k)}</div>
      <div class="tile__v">${esc(v)}</div><div class="tile__s">${esc(s)}</div></div>`).join("");
}

function filters() {
  const classes = ["All", ...new Set(state.data.assets.map((a) => a.asset_class))];
  $("#filters").innerHTML = classes.map((c) =>
    `<button data-class="${esc(c)}" aria-pressed="${c === state.filter}">${esc(c)}</button>`).join("");
  $("#filters").querySelectorAll("button").forEach((b) => {
    b.addEventListener("click", () => {
      state.filter = b.dataset.class;
      state.open = null;
      filters();
      render();
    });
  });
}

async function boot() {
  let d = null;
  try {
    const r = await fetch("data/monitor.json");
    d = r.ok ? await r.json() : null;
  } catch (e) {
    d = null;
  }
  if (!d) {
    $("#stamp").textContent = "data unavailable";
    $("#board").innerHTML =
      '<p class="note">Result data could not be loaded. Serve this directory over HTTP: ' +
      "<code>python -m http.server --directory monitor</code></p>";
    return;
  }
  state.data = d;

  const asOf = d.assets.map((a) => a.as_of).sort().pop();
  $("#stamp").textContent =
    `as of ${fmtDate(asOf)} · ${d.assets.length} markets · ` +
    `${d.target_vol * 100}% target vol · built ${d.generated}`;

  tiles();
  filters();
  render();
  replication();
}

boot();
