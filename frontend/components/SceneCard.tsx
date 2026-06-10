"use client";

import { SceneCardProps } from "@/components/props";
import { Eyebrow } from "@/components/primitives";

/* Backend scene fields are descriptive strings (e.g.
   "~52.0 (8-Jun, +1.3% MoM, −4.9% YoY)"). Split the leading figure off so the
   chip reads like the mockup's clean stat: a big number + a small detail line.
   Falls back to rendering the whole string compactly if there's no leading
   figure to peel off. */
function splitStat(raw?: string): { value: string; detail: string | null } {
  if (!raw) return { value: "—", detail: null };
  const s = raw.trim();
  const m = s.match(/^([~≈]?\s*[+−-]?\d[\d.,]*\s*%?)\s*(.*)$/);
  if (!m) return { value: s, detail: null };
  const detail = m[2].replace(/^[\s—–-]+/, "").trim();
  return { value: m[1].replace(/\s+/g, ""), detail: detail || null };
}

function MacroChip({ label, raw }: { label: string; raw?: string }) {
  const { value, detail } = splitStat(raw);
  const long = value.length > 10; // no clean figure peeled off → render compact
  return (
    <div className="mchip">
      <div className="k">{label}</div>
      <div
        className="v num"
        style={long ? { fontSize: 13, lineHeight: 1.35, whiteSpace: "normal" } : undefined}
      >
        {value}
      </div>
      {!long && detail && <div className="d">{detail}</div>}
    </div>
  );
}

export default function SceneCard({ scene }: SceneCardProps) {
  return (
    <>
      <Eyebrow style={{ marginTop: 34 }}>Market Scene</Eyebrow>
      <section className="card span-12" style={{ marginBottom: 0 }}>
        <div className="scene-head">
          <div className="headline">{scene.headline}</div>
          <span className="asof">as of {scene.as_of}</span>
        </div>
        <div className="macro">
          <MacroChip label="EGP / USD" raw={scene.egp_usd} />
          <MacroChip label="Inflation" raw={scene.inflation} />
          <MacroChip label="Policy Rate" raw={scene.policy_rate} />
          {scene.tbill_12m && <MacroChip label="12m T-Bill" raw={scene.tbill_12m} />}
        </div>
        {scene.tax_note && (
          <p style={{ fontSize: 11, color: "var(--faint)", marginTop: 6 }}>Tax: {scene.tax_note}</p>
        )}
        <div className="twocol">
          <div className="factors tw">
            <h4>
              <span className="fdot" />
              Tailwinds
            </h4>
            <ul className="flist">
              {scene.tailwinds.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="factors rk">
            <h4>
              <span className="fdot" />
              Risks
            </h4>
            <ul className="flist">
              {scene.risks.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </>
  );
}
