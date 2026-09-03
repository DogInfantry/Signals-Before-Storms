import Sweep from "@/components/Sweep";
import {
  CRISIS,
  fmtDate,
  grouped,
  monitor,
  pct,
  profileFor,
  simultaneity,
  type Asset,
} from "@/lib/data";

/* ------------------------------------------------------------ slopegraph -- */
/* Two plates identical in every respect except the variable plotted. The reader
   performs the comparison instead of being told the conclusion, which is the
   only version of this claim that survives scepticism. */

function Slope({ col, assets }: { col: string; assets: Asset[] }) {
  const vals = assets.map((a) => [0, 1, 2].map((l) => profileFor(a, col, l)));
  const flat = vals.flat().filter((v): v is number => v !== null);
  const lo = Math.min(...flat, 0);
  const hi = Math.max(...flat);
  const k = hi - lo || 1;
  const H = 34;
  const y = (v: number) => H - ((v - lo) / k) * (H - 9) - 4;

  return (
    <div style={{ display: "grid", gap: "0.2rem" }}>
      {assets.map((a, i) => {
        const pts = vals[i];
        const ok = pts.every((v) => v !== null);
        return (
          <div
            key={a.ticker}
            style={{
              display: "grid",
              gridTemplateColumns: "6.5rem 1fr",
              gap: "0.6rem",
              alignItems: "center",
              borderBottom: "1px solid var(--rule)",
            }}
          >
            <div className="label" style={{ fontSize: 10, textAlign: "right" }}>
              {a.name}
            </div>
            <svg viewBox={`0 0 100 ${H}`} width="100%" height={H} aria-hidden>
              {ok && (
                <polyline
                  points={pts.map((v, j) => `${10 + j * 40},${y(v as number)}`).join(" ")}
                  fill="none"
                  stroke="var(--ink)"
                  strokeWidth={1.4}
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {pts.map((v, j) =>
                v === null ? null : (
                  <circle key={j} cx={10 + j * 40} cy={y(v)} r={3} fill={`var(--r${j})`} />
                ),
              )}
            </svg>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ page -- */

export default function Page() {
  const sim = simultaneity();
  const rep = monitor.replication;
  const assets = monitor.assets;
  const asOf = assets.map((a) => a.as_of).sort().at(-1)!;
  const oosN = Math.max(...assets.map((a) => a.oos.n));

  // Counts come from the exported `replication` block, never recomputed here, so this page and the
  // monitor cannot state one statistic two ways. `replication` carries only the backwards count, so
  // the ascending and unordered split is TALLIED from each market's own exported `ret_ordering`
  // verdict. Counting labels the exporter already assigned is not re-deriving them.
  const byOrdering = (k: Asset["ret_ordering"]) => assets.filter((a) => a.ret_ordering === k);
  const ascendingOn = byOrdering("ascending");
  const backwards = byOrdering("backwards");
  const ascending = ascendingOn.length;
  const unordered = byOrdering("mixed").length;
  const inCrisisNow = assets.filter((a) => a.current.label === CRISIS);

  return (
    <main>
      {/* --------------------------------------------------------- folio -- */}
      <header className="sheet" style={{ paddingTop: "1.6rem", paddingBottom: "1.6rem" }}>
        <div
          className="col-full"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: "1.5rem",
            flexWrap: "wrap",
            borderBottom: "1px solid var(--rule)",
            paddingBottom: "0.9rem",
          }}
        >
          <span style={{ fontSize: "1.15rem", fontWeight: 500, letterSpacing: "-0.01em" }}>
            The Storm Ledger
          </span>
          <span className="folio">
            {assets.length} markets &middot; {monitor.n_states} states &middot; as of{" "}
            {fmtDate(asOf)}
          </span>
        </div>
      </header>

      {/* ---------------------------------------------------------- lede -- */}
      <section className="sheet">
        <div className="col-text">
          <h1 className="display">The model works. The strategy does not.</h1>
          <p className="standfirst" style={{ marginTop: "1.4rem" }}>
            A hidden Markov model sorts each session into three volatility states, refit
            out of sample on every market independently. It succeeds at what it was built
            for and fails at what it was hoped to do.
          </p>
          <p style={{ marginTop: "1.6rem", maxWidth: "62ch" }}>
            Across {assets.length} markets and{" "}
            <span className="num">{oosN.toLocaleString("en-GB")}</span> out-of-sample
            sessions, volatility rises monotonically through the three states on{" "}
            <span className="num">
              {rep.vol_monotone} of {rep.total}
            </span>
            . Return does not. It carries no ordering at all on{" "}
            <span className="num">
              {unordered} of {rep.judged}
            </span>
            , and where an ordering does appear it points both ways: ascending on{" "}
            <span className="num">{ascending}</span>, backwards on{" "}
            <span className="num">{rep.backwards}</span>. The states rank risk. They do
            not rank return, and a strategy that trades them as though they did loses to a
            static sixty-forty.
          </p>
        </div>
        <aside className="col-note">
          <p className="margin-note">
            Every number here is computed from the same export that drives the live
            monitor, so the two cannot disagree. Labels are decoded causally inside an
            expanding walk-forward, with a one-day execution lag.
          </p>
        </aside>
      </section>

      {/* ------------------------------------------------------ the sweep -- */}
      <section>
        <Sweep />
      </section>

      {/* ---------------------------------------------------- the cascade -- */}
      <section className="sheet">
        <div className="col-text">
          <h2 className="section-head">What the plate shows</h2>
          <div className="rule-draw" style={{ margin: "0.9rem 0 1.1rem" }} />
          <p>
            Between {fmtDate(sim.robust.from)} and {fmtDate(sim.robust.to)},{" "}
            <span className="num">{sim.robust.n}</span> of {assets.length} markets sat in
            Crisis at once, and held there for{" "}
            <span className="num">{sim.robust.days}</span> days. Eleven models that share
            no state variable agreed on one month.
          </p>
          <p style={{ marginTop: "1rem" }}>
            Then look again at the price paths inside that band. Several of them are
            rising. That is the finding: these states rank violence, not direction, and
            de-risking into the darkest one sells the rebound along with the crash.
          </p>
        </div>
        <aside className="col-note">
          <p className="label" style={{ marginBottom: "0.6rem" }}>
            ORDER OF ENTRY
          </p>
          {sim.alreadyIn.map((m) => (
            <p key={m.ticker} className="margin-note" style={{ marginBottom: "0.35rem" }}>
              <span className="num">{m.ticker}</span> already in Crisis, since{" "}
              {fmtDate(m.since)}
            </p>
          ))}
          {sim.cascade.map((m) => (
            <p key={m.ticker} className="margin-note" style={{ marginBottom: "0.35rem" }}>
              <span className="num">{m.ticker}</span> {fmtDate(m.onset)}
            </p>
          ))}
          {sim.never.map((m) => (
            <p key={m.ticker} className="margin-note" style={{ marginBottom: "0.35rem" }}>
              <span className="num">{m.ticker}</span> never entered
            </p>
          ))}
          <p className="margin-note" style={{ marginTop: "0.9rem", fontStyle: "italic" }}>
            The count peaks briefly at {sim.peak.n} of {assets.length} on{" "}
            {fmtDate(sim.peak.from)}, but only for {sim.peak.days} days, on the back of a
            single two-day run. Days are not a sample size, so the month-long figure is
            the one quoted here.
          </p>
        </aside>
      </section>

      {/* ----------------------------------------------- twin slopegraphs -- */}
      <section className="sheet">
        <div className="col-text">
          <h2 className="section-head">The same eleven markets, twice</h2>
          <div className="rule-draw" style={{ margin: "0.9rem 0 1.1rem" }} />
          <p className="deck">
            Both plates are built identically and differ in exactly one variable. Left,
            annualised volatility by state. Right, annualised return by state. Read down
            each column and the argument makes itself.
          </p>
        </div>
        <div className="col-plate" style={{ marginTop: "1.8rem" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "clamp(1.5rem, 4vw, 3.5rem)",
            }}
          >
            <div>
              <p className="label" style={{ marginBottom: "0.9rem" }}>
                ANNUALISED VOLATILITY &middot; RISES ON {rep.vol_monotone}/{rep.total}
              </p>
              <Slope col="eq_ann_vol" assets={assets} />
            </div>
            <div>
              <p className="label" style={{ marginBottom: "0.9rem" }}>
                ANNUALISED RETURN &middot; NO ORDERING ON {unordered}/{rep.judged}
              </p>
              <Slope col="eq_ann_ret" assets={assets} />
            </div>
          </div>
          <p className="caption" style={{ marginTop: "1.2rem" }}>
            Each line runs {monitor.regime_names.join(" to ")}, left to right; dots carry
            the state colour. Markets with fewer than {monitor.min_episodes} crisis
            episodes are excluded from the return verdict, because an ordering read off
            two episodes is not an ordering.
            {backwards.length > 0 && (
              <> Backwards on {backwards.map((a) => a.ticker).join(", ")}.</>
            )}
            {ascendingOn.length > 0 && (
              <> Ascending on {ascendingOn.map((a) => a.ticker).join(", ")}.</>
            )}
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------- instruments -- */}
      <section className="sheet">
        <div className="col-text">
          <h2 className="section-head">Where each market stands today</h2>
          <div className="rule-draw" style={{ margin: "0.9rem 0 1.1rem" }} />
          <p className="deck">
            State, how long it has held, and the position size implied by holding a
            constant {pct(monitor.target_vol, 0)} risk budget. That last figure is
            arithmetic on a measured volatility, not a backtested position.
          </p>
        </div>

        <div className="col-plate" style={{ marginTop: "1.6rem" }}>
          {grouped().map((g) => (
            <div key={g.key} style={{ marginBottom: "1.8rem" }}>
              <p className="label" style={{ marginBottom: "0.5rem" }}>
                {g.label}
              </p>
              {g.assets.map((a) => {
                const vol = profileFor(a, "eq_ann_vol", a.current.label);
                const size = a.position[String(a.current.label)];
                return (
                  <div
                    key={a.ticker}
                    className="row-rule instrument"
                  >
                    <div>
                      <span style={{ fontWeight: 500 }}>{a.name}</span>{" "}
                      <span className="label" style={{ fontSize: 10 }}>
                        {a.ticker}
                      </span>
                    </div>
                    <div className="data">
                      <span
                        className="swatch"
                        style={{ background: `var(--r${a.current.label})` }}
                      />
                      {monitor.regime_names[a.current.label]}
                    </div>
                    <div className="data" style={{ color: "var(--ink-soft)" }}>
                      {a.current.sessions_in_run} sessions &middot; since{" "}
                      {fmtDate(a.current.since)}
                    </div>
                    <div className="data" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {pct(vol)} vol
                      <span style={{ color: "var(--ink-faint)" }}> &rarr; </span>
                      {size === undefined ? "--" : pct(size, 0)}
                      {size !== undefined && size >= 1 && (
                        <span style={{ color: "var(--ink-faint)" }}> capped</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
          <p className="caption">
            {inCrisisNow.length} of {assets.length} markets are in Crisis as of{" "}
            {fmtDate(asOf)}
            {inCrisisNow.length > 0 && <>: {inCrisisNow.map((a) => a.name).join(", ")}</>}.
            Position size is {monitor.position_basis}, capped at one; the cap is drawn
            rather than hidden.
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------- colophon -- */}
      <footer
        className="sheet"
        style={{ marginTop: "clamp(4rem,10vw,7rem)", paddingBottom: "4rem" }}
      >
        <div className="col-text">
          <div className="rule-draw" style={{ marginBottom: "1.1rem" }} />
          <p className="margin-note">
            Three-state Gaussian HMM on causal momentum and realised-volatility features,
            standardised on the training fold only, refit inside an expanding
            walk-forward, decoded causally, executed at a one-day lag. Regime colours are
            an ordinal lightness ramp validated for contrast and colour-vision
            separation. Sample {fmtDate(monitor.window.start)} to {fmtDate(asOf)}.
          </p>
          <p className="margin-note" style={{ marginTop: "0.9rem" }}>
            <a href="https://signals-before-storms.vercel.app">The research</a> &middot;{" "}
            <a href="https://github.com/DogInfantry/Signals-Before-Storms">The code</a>
          </p>
          {assets.some((a) => a.notes.length > 0) && (
            <p
              className="margin-note"
              style={{ marginTop: "0.9rem", color: "var(--ink-faint)" }}
            >
              {assets
                .filter((a) => a.notes.length > 0)
                .map((a) => `† ${a.ticker}: ${a.notes.join("; ")}`)
                .join("   ")}
            </p>
          )}
        </div>
      </footer>
    </main>
  );
}
