import raw from "@/public/data/monitor.json";

/* ---------------------------------------------------------------- schema -- */

export type Run = { label: number; from: string; to: string };

export type Asset = {
  ticker: string;
  name: string;
  asset_class: "Equity India" | "Equity US" | "Rates" | "Commodity";
  currency: string;
  as_of: string;
  bars: number;
  rows_dropped: number;
  nonpositive_prices: number;
  feature_cols: number;
  notes: string[];
  last_price: number;
  oos: { start: string; end: string; n: number };
  current: { label: number; proba: number[]; sessions_in_run: number; since: string };
  transition: number[][];
  dwell: Record<string, number>;
  label_profile: { columns: string[]; index: string[]; rows: number[][] };
  position: Record<string, number>;
  p_crisis_21: number | null;
  vol_monotone: boolean;
  ret_ordering: "ascending" | "backwards" | "mixed" | "n/e";
  crisis_episodes: number;
  runs: Run[];
  dates: string[];
  prices: number[];
};

export type Monitor = {
  generated: string;
  window: { start: string; chart_from: string };
  stride: number;
  n_states: number;
  regime_names: string[];
  target_vol: number;
  crisis_horizon: number;
  min_episodes: number;
  position_basis: string;
  replication: { vol_monotone: number; backwards: number; judged: number; total: number };
  assets: Asset[];
};

export const monitor = raw as unknown as Monitor;
export const CRISIS = monitor.n_states - 1;

/* ------------------------------------------------------------- taxonomy -- */
/* Rows group 3 / 3 / 5. The ragged final row is the taxonomy, not a layout
   accident, which is why this is a fixed order and not a sort. */

export const GROUPS = [
  { key: "india", label: "INDIA", classes: ["Equity India"] },
  { key: "global", label: "GLOBAL", classes: ["Equity US", "Rates"] },
  { key: "commodity", label: "COMMODITIES", classes: ["Commodity"] },
] as const;

/**
 * The taxonomy above is a fixed order, not a sort, so it names its asset classes literally. That
 * means a market carrying a class this list does not know would be filtered out of every group and
 * vanish from BOTH the instrument list and the Sweep plate, silently, because Sweep builds its rows
 * from this same function. monitor/app.js derives its filter list from the data and cannot do that.
 * Unmatched markets are collected into a trailing group instead, so a new asset class shows up
 * looking unplaced rather than not showing up at all. Empty groups are dropped.
 */
export function grouped(assets: Asset[] = monitor.assets) {
  const known = new Set(GROUPS.flatMap((g) => g.classes as readonly string[]));
  const out: { key: string; label: string; assets: Asset[] }[] = GROUPS.map((g) => ({
    key: g.key,
    label: g.label,
    assets: assets.filter((a) => (g.classes as readonly string[]).includes(a.asset_class)),
  }));
  const rest = assets.filter((a) => !known.has(a.asset_class));
  if (rest.length) out.push({ key: "other", label: "OTHER", assets: rest });
  return out.filter((g) => g.assets.length > 0);
}

/* ----------------------------------------------------------------- time -- */

export const day = (s: string) => Date.parse(s + "T00:00:00Z");
export const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
const DAY_MS = 86_400_000;

export const T0 = day(monitor.window.chart_from);
export const T1 = Math.max(...monitor.assets.map((a) => day(a.as_of)));
export const span = T1 - T0;
/** Round to 2dp and stay a number, so results can still be subtracted. */
export const r2 = (v: number) => Math.round(v * 100) / 100;

/**
 * Date -> 0..1000 plate units, rounded to 2dp.
 *
 * The rounding is not cosmetic. Sweep draws roughly 1,300 rects straight from this, and React
 * serialises whatever float it is handed, so unrounded values shipped attributes like
 * x="286.36779505946936" and made raw coordinates half of the prerendered HTML. The plate is
 * 1000 units wide rendered at 660 to 1000 px, so 0.01 units is under a hundredth of a pixel and
 * nothing moves. sparkPath already rounded its own vertices for exactly this reason.
 *
 * Callers subtracting two of these must round again: 2dp minus 2dp reintroduces IEEE noise
 * (286.37 - 258.01 = 28.360000000000014), which is why r2 is exported alongside.
 */
export const x = (t: number) => r2(((t - T0) / span) * 1000);

/**
 * A run is drawn from its own start to the NEXT run's start, never to its own
 * end. A one-session run has zero calendar width and would otherwise vanish -
 * a measured defect already documented and fixed in monitor/app.js.
 */
export function runSpans(a: Asset) {
  return a.runs.map((r, i) => {
    const from = day(r.from);
    const to = i + 1 < a.runs.length ? day(a.runs[i + 1].from) : day(a.as_of) + DAY_MS;
    return { label: r.label, from, to };
  });
}

/* ------------------------------------------------- simultaneity, measured -- */
/* Every headline on the page is computed here. Nothing is transcribed, because
   the design brief arrived with two claims the data contradicted: "ten of
   eleven" is a two-day artifact, and gold never joined the cascade - it had
   already been in crisis for over a year. */

export type Simultaneity = {
  series: { t: number; n: number }[];
  peak: { n: number; days: number; from: string; to: string; absent: string[] };
  /** the largest count that holds for three weeks or more - the ROBUST claim */
  robust: { n: number; days: number; from: string; to: string };
  cascade: { ticker: string; name: string; onset: string }[];
  alreadyIn: { ticker: string; name: string; since: string; days: number }[];
  never: { ticker: string; name: string }[];
};

export function simultaneity(): Simultaneity {
  const inCrisis = new Map<number, Set<string>>();
  for (const a of monitor.assets) {
    for (const s of runSpans(a)) {
      if (s.label !== CRISIS) continue;
      for (let t = s.from; t < s.to; t += DAY_MS) {
        if (t < T0 || t > T1) continue;
        if (!inCrisis.has(t)) inCrisis.set(t, new Set());
        inCrisis.get(t)!.add(a.ticker);
      }
    }
  }
  const series = [...inCrisis.entries()]
    .map(([t, s]) => ({ t, n: s.size }))
    .sort((p, q) => p.t - q.t);

  const maxN = Math.max(...series.map((d) => d.n));
  const runFor = (k: number) => {
    const ds = series.filter((d) => d.n >= k).map((d) => d.t).sort((p, q) => p - q);
    let best = { len: 0, from: 0, to: 0 };
    let i = 0;
    while (i < ds.length) {
      let j = i;
      while (j + 1 < ds.length && ds[j + 1] - ds[j] <= DAY_MS) j++;
      const len = (ds[j] - ds[i]) / DAY_MS + 1;
      if (len > best.len) best = { len, from: ds[i], to: ds[j] };
      i = j + 1;
    }
    return best;
  };

  const peakRun = runFor(maxN);
  const present = inCrisis.get(peakRun.from)!;
  const absent = monitor.assets.map((a) => a.ticker).filter((t) => !present.has(t));

  // The strongest claim that survives three weeks. Days are not a sample size;
  // a two-day peak resting on a two-day run is an artifact, not a finding.
  let robustN = maxN;
  let robustRun = peakRun;
  while (robustN > 1 && robustRun.len < 21) {
    robustN -= 1;
    robustRun = runFor(robustN);
  }

  const wFrom = robustRun.from;
  const wTo = robustRun.to;
  const cascade: Simultaneity["cascade"] = [];
  const alreadyIn: Simultaneity["alreadyIn"] = [];
  const never: Simultaneity["never"] = [];

  // A market counts as "already in" only if it entered WELL before the cluster,
  // not merely before the window opened. Anchoring on wFrom alone lumped seven
  // markets that entered days earlier in with gold, which had been in Crisis for
  // a year - which flattens the cascade the plate exists to show.
  const GRACE = 30 * DAY_MS;

  for (const a of monitor.assets) {
    const crises = runSpans(a).filter((s) => s.label === CRISIS);
    const covering = crises.find((s) => s.from <= wTo && s.to > wFrom);
    if (!covering) {
      never.push({ ticker: a.ticker, name: a.name });
    } else if (covering.from < wFrom - GRACE) {
      alreadyIn.push({
        ticker: a.ticker,
        name: a.name,
        since: iso(covering.from),
        days: Math.round((covering.to - covering.from) / DAY_MS),
      });
    } else {
      cascade.push({ ticker: a.ticker, name: a.name, onset: iso(covering.from) });
    }
  }
  cascade.sort((p, q) => day(p.onset) - day(q.onset));

  return {
    series,
    peak: { n: maxN, days: peakRun.len, from: iso(peakRun.from), to: iso(peakRun.to), absent },
    robust: { n: robustN, days: robustRun.len, from: iso(wFrom), to: iso(wTo) },
    cascade,
    alreadyIn,
    never,
  };
}

/* ------------------------------------------------------------- profiles -- */

/** Keyed by str(label), never positionally: a quiet market can yield a 2-row
 *  profile against a 3x3 transition, and positional reads would misassign. */
export function profileFor(a: Asset, col: string, label: number): number | null {
  const i = a.label_profile.index.indexOf(String(label));
  const j = a.label_profile.columns.indexOf(col);
  if (i < 0 || j < 0) return null;
  const v = a.label_profile.rows[i]?.[j];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export const pct = (v: number | null, d = 1) =>
  v === null ? "--" : `${(v * 100).toFixed(d)}%`;

export const REGIME_VAR = ["var(--r0)", "var(--r1)", "var(--r2)"];

export const fmtDate = (s: string) =>
  new Date(s + "T00:00:00Z").toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
