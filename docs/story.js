/* Signals-Before-Storms: the research log's controller.

   story.html shipped as prose with ten pasted plates and no script at all, while the exported
   results sat in the same directory unread. This draws those plates live from data/*.json, using
   the same kernel the landing panel uses, so a figure in the log and the same figure on the panel
   cannot disagree.

   PROGRESSIVE ENHANCEMENT, NOT REPLACEMENT. Every mount below already contains its committed
   static plate. A drawer overwrites that only once it has data in hand, so a reader with
   JavaScript off, or on file:// where fetch is blocked, sees exactly what the page showed before
   this file existed. No image was deleted from docs/img/.

   NO GLOBAL MARKET SWITCH, deliberately. The log is a chronological India narrative and its prose
   quotes India numbers throughout. A switch that swapped every figure to the US would put the
   figures out of step with the sentences beside them, which is the exact defect this project
   spends its length fixing. Only the scorecards, where the prose already presents both universes
   side by side, are switchable. */

import {
  $,
  $$,
  BOOKS,
  STROKE_OF,
  cursorBus,
  dwellBars,
  episodeDumbbell,
  group,
  labelProfile,
  lineChart,
  pairedForest,
  reducedMotion,
  reveal,
  regimeOverlay,
  scorecard,
  scrollProgress,
  transitionHeatmap,
  weightStack,
} from "./charts.js";

const MARKETS = ["india", "us"];
const DATA = {};

// The log's own universe. Every figure but the scorecard is pinned to it, matching the prose.
const HOME = "india";

const state = {
  bench: "60_40",
  scoreMarket: "india",
  cost: "net",
  sort: "sharpe",
  desc: true,
  visible: new Set(["hmm_conditional", "60_40", "equal_weight"]),
};

// The equity and drawdown pair in the scorecards entry is the one place the log lets a reader
// choose what to plot, so it keeps its own visible set rather than showing all eight at once.
function seriesFor(d, source) {
  return BOOKS.filter(([k]) => state.visible.has(k) && d[source][k]).map(([k, label]) => ({
    key: k,
    label,
    stroke: STROKE_OF[k],
    values: source === "curves" ? d.curves[k][state.cost] : d.drawdowns[k],
  }));
}

/* ------------------------------------------------------------------ figures

   One entry per data-fig value in the markup. Each receives the mount and the payload for the
   market that mount declares, so adding a figure to the page is an attribute in the HTML, not a
   code change in two places. */

const FIGURES = {
  transition: (el, d) => transitionHeatmap(el, d),
  dwell: (el, d) => dwellBars(el, d),
  labels: (el, d) => labelProfile(el, d),
  weights: (el, d) => weightStack(el, d),
  episodes: (el, d) => episodeDumbbell(el, d),
  paired: (el, d) => pairedForest(el, d, { bench: state.bench }),
  overlay: (el, d) => regimeOverlay(el, d, { market: HOME }),
  curves: (el, d) =>
    lineChart(el, d, {
      series: seriesFor(d, "curves"),
      fmt: (v) => `${v.toFixed(1)}x`,
      bands: true,
      zero: false,
    }),
  drawdowns: (el, d) =>
    lineChart(el, d, {
      series: seriesFor(d, "drawdowns"),
      fmt: (v) => `${(v * 100).toFixed(0)}%`,
      bands: false,
      zero: true,
    }),
  scorecard: (el, d) =>
    scorecard(el, d, {
      cost: state.cost,
      sort: state.sort,
      desc: state.desc,
      visible: state.visible,
      onSort: (c) => {
        state.desc = state.sort === c ? !state.desc : true;
        state.sort = c;
        drawAll();
      },
    }),
};

function payloadFor(el) {
  const want = el.dataset.fig === "scorecard" ? state.scoreMarket : el.dataset.market || HOME;
  return DATA[want];
}

/** Draw every mount that has both a drawer and a payload. A mount whose data never arrived keeps
 *  the static plate it shipped with, which is the whole point of the fallback. */
function drawAll() {
  cursorBus.clear();
  $$("[data-fig]").forEach((el) => {
    const fn = FIGURES[el.dataset.fig];
    const d = payloadFor(el);
    if (!fn || !d) return;
    el.classList.add("is-live");
    fn(el, d);
  });
  $$("[data-oos-story]").forEach((el) => {
    const d = DATA[state.scoreMarket];
    if (d) el.textContent = `${d.oos.start} to ${d.oos.end}, n = ${d.oos.n.toLocaleString()}`;
  });
}

/* ------------------------------------------------------------------ the beat

   Entry 02 is the thesis of the whole project and it arrived as a flat SVG. It now plays in two
   stages: the volatility bars rise first and land monotone, the model doing exactly the job it
   was given, and only then do the return bars rise and land backwards.

   Timed off a viewport entry rather than scrubbed off scroll position. Scrubbing would need the
   entry stretched to around 170vh to have any travel to scrub through, and doing that to one
   section of an eight-entry research log would push the rest of the argument a screen and a half
   further down for every reader. The beat is worth a second; it is not worth the page. */
function playLabelBeat(el, d) {
  if (reducedMotion()) {
    labelProfile(el, d);
    return;
  }
  const DURATION = 1700;
  let t0 = null;
  const step = (now) => {
    if (t0 === null) t0 = now;
    const p = Math.min(1, (now - t0) / DURATION);
    labelProfile(el, d, { progress: p });
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ------------------------------------------------------------------ the rail

   A 2,800-word log needs a way to be scanned as well as read. The rail is an index of entries
   with the current one marked, plus a hairline showing how far through the log the reader is.
   It adds a way in without removing a word, which matters because the retraction, the
   pre-registered criteria and the episode counting ARE the deliverable on this page. */

function buildRail() {
  const heads = $$("section.entry > h2[id]");
  if (heads.length < 3) return;
  const rail = document.createElement("nav");
  rail.className = "rail";
  rail.setAttribute("aria-label", "Index of entries");
  rail.innerHTML =
    '<span class="rail__bar"><span class="rail__fill"></span></span><ol>' +
    heads
      .map(
        (h, i) =>
          `<li><a href="#${h.id}" data-rail="${h.id}" title="${h.textContent}"><b>${String(i + 1).padStart(2, "0")}</b><span class="vh">${h.textContent}</span></a></li>`,
      )
      .join("") +
    "</ol>";
  document.body.appendChild(rail);

  const links = new Map($$("[data-rail]", rail).map((a) => [a.dataset.rail, a]));
  const mark = (id) => links.forEach((a, k) => a.classList.toggle("on", k === id));
  mark(heads[0].id);

  // Clicking the rail marks its own target immediately. The observer below watches a band a
  // little down from the top of the viewport, and an anchor jump lands the heading ABOVE that
  // band, so without this the reader clicks entry 06 and the marker stays on 01.
  links.forEach((a, id) => a.addEventListener("click", () => mark(id)));

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit) mark(hit.target.id);
      },
      { rootMargin: "0px 0px -68% 0px" },
    );
    heads.forEach((h) => io.observe(h));
  }

  const fill = $(".rail__fill", rail);
  scrollProgress($(".log") || document.body, (p) => {
    fill.style.transform = `scaleY(${Math.max(p, 0.02).toFixed(3)})`;
  });
}

/* ------------------------------------------------------------------ chrome */

function buildBookToggles() {
  const host = $("#story-books");
  if (!host) return;
  const d = DATA[state.scoreMarket];
  if (!d) return;
  host.innerHTML = BOOKS.filter(([k]) => d.curves[k])
    .map(
      ([k, label, kind]) =>
        `<label class="chip${state.visible.has(k) ? " on" : ""}" data-kind="${kind}">
      <input type="checkbox" value="${k}"${state.visible.has(k) ? " checked" : ""}>
      <i style="background:${STROKE_OF[k].c}"></i>${label}</label>`,
    )
    .join("");
  $$("#story-books input").forEach((box) =>
    box.addEventListener("change", () => {
      if (box.checked) state.visible.add(box.value);
      else state.visible.delete(box.value);
      box.closest(".chip").classList.toggle("on", box.checked);
      drawAll();
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

  // No data means no enhancement, and the committed plates stay exactly as they are. The page
  // still reads completely, which is why this returns quietly instead of announcing a failure.
  if (!DATA[HOME]) return;

  document.body.classList.add("has-live");
  buildRail();
  buildBookToggles();

  group("bench", (v) => {
    state.bench = v;
    drawAll();
  });
  group("score-market", (v) => {
    state.scoreMarket = v;
    buildBookToggles();
    drawAll();
  });
  group("story-cost", (v) => {
    state.cost = v;
    drawAll();
  });

  drawAll();

  // The label profile is drawn complete by drawAll above, so it is already correct before this
  // runs. reveal() then replays it as the two-stage beat when it comes into view, and calls
  // straight through to the finished state when motion is reduced.
  const beat = $('[data-fig="labels"]');
  if (beat) reveal(beat, () => playLabelBeat(beat, DATA[HOME]));

  // Everything else simply fades up on first sight.
  $$("[data-fig]").forEach((el) => {
    if (el === beat) return;
    reveal(el, () => el.classList.add("seen"));
  });
}

boot();
