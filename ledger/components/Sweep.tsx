"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CRISIS,
  T0,
  T1,
  day,
  fmtDate,
  grouped,
  iso,
  monitor,
  r2,
  runSpans,
  simultaneity,
  x,
  type Asset,
} from "@/lib/data";

// The price path is the POINT of this form - it is what lets a reader see a crisis
// band sitting under a RISING line. A 7px saturated rail against a 24px path made
// the rail the dominant mark and buried the argument, so the rail is thinner and
// the row taller.
const ROW = 46;
const RAIL = 5;
// Bottom gutter INSIDE each row. Without it a row's rail sits flush against the next
// row's label and reads as belonging to that market rather than its own.
const PAD = 9;
const GAP = 16;
const AXIS = 30;
const LABEL_W = 132;

/** Sparkline path in 0..1000 x 0..(ROW-RAIL-3) space, scaled to the row's own min/max. */
function sparkPath(a: Asset) {
  const ys = a.prices;
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  const h = ROW - RAIL - PAD - 3;
  const k = hi - lo || 1;
  return ys
    .map((v, i) => {
      const px = x(day(a.dates[i]));
      const py = h - ((v - lo) / k) * h + 1;
      return `${i ? "L" : "M"}${px.toFixed(2)} ${py.toFixed(2)}`;
    })
    .join(" ");
}

export default function Sweep() {
  const sim = useMemo(() => simultaneity(), []);
  const groups = useMemo(() => grouped(), []);

  // Taxonomy order, with a gap between groups. This is the resting state.
  const taxonomy = useMemo(() => {
    const out: { a: Asset; y: number; group: string | null }[] = [];
    let y = 0;
    groups.forEach((g, gi) => {
      g.assets.forEach((a, ai) => {
        out.push({ a, y, group: ai === 0 ? g.label : null });
        y += ROW;
      });
      if (gi < groups.length - 1) y += GAP;
    });
    return out;
  }, [groups]);

  const plateH = taxonomy[taxonomy.length - 1].y + ROW;

  // Onset order: already-in pinned to the top, then the cascade in order of
  // entry, then never-entered at the bottom. Computed, never transcribed.
  const onsetOrder = useMemo(() => {
    const rank = new Map<string, number>();
    let r = 0;
    sim.alreadyIn.forEach((m) => rank.set(m.ticker, r++));
    sim.cascade.forEach((m) => rank.set(m.ticker, r++));
    sim.never.forEach((m) => rank.set(m.ticker, r++));
    return rank;
  }, [sim]);

  const onsetDate = useMemo(() => {
    const m = new Map<string, string>();
    sim.cascade.forEach((c) => m.set(c.ticker, c.onset));
    return m;
  }, [sim]);

  const sectionRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);
  const [reduced, setReduced] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    if (reduced) {
      setP(1); // motion off defaults to the FINISHED state, so nothing is lost
      return;
    }
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const el = sectionRef.current;
        if (!el) return;
        // one getBoundingClientRect per frame for the whole plate, never per row
        const r = el.getBoundingClientRect();
        const total = r.height - window.innerHeight;
        setP(total <= 0 ? 1 : Math.min(1, Math.max(0, -r.top / total)));
      });
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [reduced]);

  const wash = Math.min(1, Math.max(0, (p - 0.15) / 0.3));
  const sorted = p > 0.45;
  const sweep = Math.min(1, Math.max(0, (p - 0.45) / 0.3));

  const wFrom = day(sim.robust.from);
  const wTo = day(sim.robust.to);
  const sweepX = x(wFrom + (wTo - wFrom) * sweep);

  const onMove = (e: React.PointerEvent) => {
    const el = plotRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setCursor(Math.min(1000, Math.max(0, ((e.clientX - r.left) / r.width) * 1000)));
  };

  const cursorDate = cursor === null ? null : T0 + (cursor / 1000) * (T1 - T0);

  const readout = (a: Asset) => {
    if (cursorDate === null) return null;
    const s = runSpans(a).find((r) => r.from <= cursorDate && cursorDate < r.to);
    return s ? monitor.regime_names[s.label] : null;
  };

  const years = useMemo(() => {
    const out: { t: number; y: number }[] = [];
    for (let y = new Date(T0).getUTCFullYear() + 1; y <= new Date(T1).getUTCFullYear(); y++) {
      out.push({ t: day(`${y}-01-01`), y });
    }
    return out;
  }, []);

  const rowY = (a: Asset, taxY: number) =>
    sorted ? (onsetOrder.get(a.ticker) ?? 0) * ROW : taxY;
  const rowDelay = (a: Asset) =>
    reduced ? "0ms" : `${(onsetOrder.get(a.ticker) ?? 0) * 40}ms`;
  const shift = "transform 420ms cubic-bezier(0.2,0,0,1)";

  return (
    <div ref={sectionRef} style={{ height: reduced ? "auto" : "170vh" }}>
      <div style={reduced ? undefined : { position: "sticky", top: 0, paddingTop: "2.5rem" }}>
        <div className="sheet">
          <div className="col-plate">
            <h2 className="section-head">Eleven markets, three years, one plate</h2>
            <div className="rule-draw" style={{ margin: "0.9rem 0 1.1rem" }} />
            <p className="deck">
              Each row is one market: its price path above, its regime rail below. Crisis
              is the only state that washes the whole row, so simultaneity reads as a
              column instead of as eleven separate rails.
            </p>
          </div>
        </div>

        <div className="sheet" style={{ marginTop: "1.5rem" }}>
          <div className="col-plate">
            <div style={{ overflowX: "auto", overflowY: "hidden" }}>
              <div
                style={{ minWidth: 660, position: "relative" }}
                onPointerMove={onMove}
                onPointerLeave={() => setCursor(null)}
              >
                <div style={{ display: "flex" }}>
                  {/* label gutter, sticky so it survives the mobile scroll */}
                  <div
                    style={{
                      width: LABEL_W,
                      flex: `0 0 ${LABEL_W}px`,
                      position: "sticky",
                      left: 0,
                      zIndex: 2,
                      background: "var(--paper)",
                      height: plateH,
                    }}
                  >
                    {taxonomy.map(({ a, y }) => {
                      const r = readout(a);
                      const faded = sorted && sim.never.some((n) => n.ticker === a.ticker);
                      return (
                        <div
                          key={a.ticker}
                          style={{
                            position: "absolute",
                            top: 0,
                            right: 12,
                            height: ROW,
                            transform: `translateY(${rowY(a, y)}px)`,
                            transition: reduced ? "none" : shift,
                            transitionDelay: rowDelay(a),
                            textAlign: "right",
                            willChange: "transform",
                          }}
                        >
                          <div
                            style={{
                              fontSize: 13,
                              fontWeight: 500,
                              lineHeight: 1.15,
                              color: faded ? "var(--ink-faint)" : "var(--ink)",
                            }}
                          >
                            {a.name}
                          </div>
                          <div className="label" style={{ fontSize: 10 }}>
                            {r ?? `${a.ticker}${a.notes.length ? " †" : ""}`}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* plate */}
                  <div ref={plotRef} style={{ flex: 1, position: "relative", height: plateH }}>
                    {taxonomy.map(({ a, y }) => {
                      const spans = runSpans(a);
                      const onset = onsetDate.get(a.ticker);
                      const tick =
                        onset !== undefined && sweep > 0 && x(day(onset)) <= sweepX + 0.5;
                      return (
                        <svg
                          key={a.ticker}
                          viewBox={`0 0 1000 ${ROW}`}
                          preserveAspectRatio="none"
                          width="100%"
                          height={ROW}
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            transform: `translateY(${rowY(a, y)}px)`,
                            transition: reduced ? "none" : shift,
                            transitionDelay: rowDelay(a),
                            display: "block",
                            willChange: "transform",
                          }}
                          aria-hidden
                        >
                          {/* Crisis-only wash: one colour at one alpha, so it cannot
                              corrupt the ordinal encoding. */}
                          {spans
                            .filter((s) => s.label === CRISIS)
                            .map((s, i) => (
                              <rect
                                key={`w${i}`}
                                x={x(s.from)}
                                y={0}
                                width={r2(Math.max(x(s.to) - x(s.from), 0.6))}
                                height={ROW - PAD}
                                fill="var(--r2)"
                                style={{ opacity: `calc(var(--wash) * ${wash})` }}
                              />
                            ))}
                          <path
                            d={sparkPath(a)}
                            fill="none"
                            stroke="var(--ink)"
                            strokeWidth={1.5}
                            vectorEffect="non-scaling-stroke"
                            strokeLinejoin="round"
                          />
                          {spans.map((s, i) => (
                            <rect
                              key={`r${i}`}
                              x={x(s.from)}
                              y={ROW - RAIL - PAD}
                              width={r2(Math.max(x(s.to) - x(s.from), 0.6))}
                              height={RAIL}
                              fill={`var(--r${s.label})`}
                            />
                          ))}
                          {tick && onset && (
                            <rect
                              x={x(day(onset)) - 0.6}
                              y={ROW - RAIL - PAD - 5}
                              width={1.2}
                              height={RAIL + 5}
                              fill="var(--accent)"
                            />
                          )}
                        </svg>
                      );
                    })}

                    {/* overlay: year rules, sweep, crosshair. A separate SVG so the
                        ~1,200 rects above never re-render on pointermove. */}
                    <svg
                      viewBox={`0 0 1000 ${plateH}`}
                      preserveAspectRatio="none"
                      width="100%"
                      height={plateH}
                      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
                      aria-hidden
                    >
                      {years.map((yr) => (
                        <rect
                          key={yr.y}
                          x={x(yr.t)}
                          y={0}
                          width={0.6}
                          height={plateH}
                          fill="var(--ink)"
                          opacity={0.08}
                        />
                      ))}
                      {sweep > 0 && sweep < 1 && (
                        <rect x={sweepX - 0.5} y={0} width={1} height={plateH} fill="var(--accent)" />
                      )}
                      {cursor !== null && (
                        <rect x={cursor - 0.5} y={0} width={1} height={plateH} fill="var(--accent)" />
                      )}
                    </svg>
                  </div>
                </div>

                {/* axis */}
                <div style={{ display: "flex", height: AXIS, alignItems: "flex-start" }}>
                  <div style={{ width: LABEL_W, flex: `0 0 ${LABEL_W}px` }} />
                  <div style={{ flex: 1, position: "relative", paddingTop: 6 }}>
                    <span className="label" style={{ position: "absolute", left: 0, fontSize: 10 }}>
                      {fmtDate(iso(T0))}
                    </span>
                    {years.map((yr) => (
                      <span
                        key={yr.y}
                        className="label"
                        style={{
                          position: "absolute",
                          left: `${x(yr.t) / 10}%`,
                          fontSize: 10,
                          transform: "translateX(-50%)",
                        }}
                      >
                        {yr.y}
                      </span>
                    ))}
                    <span className="label" style={{ position: "absolute", right: 0, fontSize: 10 }}>
                      {cursorDate !== null ? fmtDate(iso(cursorDate)) : fmtDate(iso(T1))}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <p className="caption" style={{ marginTop: "1.1rem" }}>
              {monitor.regime_names.map((n, i) => (
                <span key={n} style={{ marginRight: "1.1rem", whiteSpace: "nowrap" }}>
                  <span className="swatch" style={{ background: `var(--r${i})` }} />
                  {n}
                </span>
              ))}
              <span style={{ display: "block", marginTop: "0.7rem" }}>
                Eleven models were fitted independently, one per market, with no shared
                state variable. The alignment describes one event. It is not a contagion
                claim, and nothing here estimates a link between markets.
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
