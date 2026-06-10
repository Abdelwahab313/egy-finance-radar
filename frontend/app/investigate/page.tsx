"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ReportMeta = { symbol: string; date: string; filename: string };
type Status = "idle" | "running" | "done" | "error";

export default function InvestigatePage() {
  const [symbol, setSymbol] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadReports = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/reports`);
      if (r.ok) setReports(await r.json());
    } catch {
      /* backend down — handled by the action error */
    }
  }, []);

  const openReport = useCallback(async (filename: string) => {
    setActive(filename);
    setMarkdown(null);
    const r = await fetch(`${API}/api/reports/${filename}`);
    if (r.ok) {
      const j = await r.json();
      setMarkdown(j.markdown);
    } else {
      setMarkdown(`*Could not load ${filename} (API ${r.status}).*`);
    }
  }, []);

  useEffect(() => {
    loadReports();
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, [loadReports]);

  const startPolling = useCallback(
    (filename: string) => {
      if (poll.current) clearInterval(poll.current);
      poll.current = setInterval(async () => {
        try {
          const r = await fetch(
            `${API}/api/investigate/status?filename=${encodeURIComponent(filename)}`
          );
          const j = await r.json();
          if (j.status === "done") {
            if (poll.current) clearInterval(poll.current);
            setStatus("done");
            setStatusMsg(null);
            await loadReports();
            await openReport(filename);
          } else if (j.status === "error" || j.status === "unknown") {
            if (poll.current) clearInterval(poll.current);
            setStatus("error");
            setStatusMsg(j.error ?? "Investigation failed.");
          }
        } catch (e) {
          if (poll.current) clearInterval(poll.current);
          setStatus("error");
          setStatusMsg(`Lost contact with the backend at ${API}.`);
        }
      }, 3000);
    },
    [loadReports, openReport]
  );

  const investigate = useCallback(async () => {
    const sym = symbol.trim().toUpperCase();
    if (!/^[A-Z0-9]{1,8}$/.test(sym)) {
      setStatus("error");
      setStatusMsg("Enter a valid symbol (1–8 letters/digits), e.g. ELSH.");
      return;
    }
    setStatus("running");
    setStatusMsg(`Investigating ${sym} — fetching data and researching the web…`);
    setMarkdown(null);
    setActive(null);
    try {
      const r = await fetch(`${API}/api/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym }),
      });
      if (!r.ok) throw new Error(`API ${r.status}`);
      const j = await r.json();
      if (j.status === "done") {
        setStatus("done");
        setStatusMsg(null);
        await loadReports();
        await openReport(j.filename);
      } else {
        startPolling(j.filename);
      }
    } catch (e: unknown) {
      setStatus("error");
      const msg = e instanceof Error ? e.message : String(e);
      setStatusMsg(
        `Could not reach the backend at ${API}. Start it with: uvicorn app.main:app --port 8000. [${msg}]`
      );
    }
  }, [symbol, loadReports, openReport, startPolling]);

  // group reports by symbol, newest first
  const grouped = reports.reduce<Record<string, ReportMeta[]>>((acc, r) => {
    (acc[r.symbol] ??= []).push(r);
    return acc;
  }, {});

  return (
    <main className="min-h-screen max-w-6xl mx-auto px-4 py-8 flex flex-col gap-6">
      <Nav />
      <header>
        <h1 className="text-2xl font-bold tracking-tight">
          Stock <span className="text-[var(--accent)]">Investigation</span>
        </h1>
        <p className="text-sm text-[var(--muted)]">
          Type an EGX symbol — an agent validates the data, researches the web, and writes a full
          analyst report.
        </p>
      </header>

      {/* Input */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-5">
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && status !== "running" && investigate()}
            placeholder="e.g. ELSH"
            maxLength={8}
            className="flex-1 min-w-[12rem] rounded-lg bg-[var(--bg)] border border-[var(--border)] px-4 py-2.5 uppercase tracking-wide outline-none focus:border-[var(--accent)]"
          />
          <button
            onClick={investigate}
            disabled={status === "running"}
            className="rounded-lg bg-[var(--accent)] text-black font-semibold px-5 py-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === "running" ? "Investigating…" : "Investigate"}
          </button>
        </div>
        {statusMsg && (
          <p
            className={`mt-3 text-sm flex items-center gap-2 ${
              status === "error" ? "text-[var(--red)]" : "text-[var(--muted)]"
            }`}
          >
            {status === "running" && <Spinner />}
            {statusMsg}
          </p>
        )}
      </section>

      <div className="grid lg:grid-cols-[16rem_1fr] gap-6">
        {/* Past reports */}
        <aside className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-4 h-fit">
          <h2 className="text-xs uppercase tracking-widest text-[var(--muted)] mb-3">
            Past reports
          </h2>
          {reports.length === 0 ? (
            <p className="text-xs text-[var(--muted)]">No reports yet.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {Object.entries(grouped).map(([sym, items]) => (
                <div key={sym}>
                  <div className="text-sm font-semibold">{sym}</div>
                  <div className="flex flex-col gap-1 mt-1">
                    {items.map((r) => (
                      <button
                        key={r.filename}
                        onClick={() => openReport(r.filename)}
                        className={`text-left text-xs rounded px-2 py-1 hover:bg-[var(--panel-2)] ${
                          active === r.filename
                            ? "bg-[var(--panel-2)] text-[var(--accent)]"
                            : "text-[var(--muted)]"
                        }`}
                      >
                        {r.date}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Report view */}
        <section className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-6 min-h-[20rem]">
          {markdown ? (
            <article className="report-md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
            </article>
          ) : (
            <div className="text-[var(--muted)] text-sm flex items-center justify-center h-full">
              {status === "running"
                ? "The report will appear here when the agent finishes."
                : "Select a past report, or investigate a symbol to generate one."}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function Nav() {
  return (
    <nav className="flex items-center gap-4 text-sm">
      <Link href="/" className="text-[var(--muted)] hover:text-[var(--text)]">
        Dashboard
      </Link>
      <span className="text-[var(--border)]">·</span>
      <Link href="/investigate" className="text-[var(--accent)] font-medium">
        Investigate
      </Link>
    </nav>
  );
}

function Spinner() {
  return (
    <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-[var(--muted)] border-t-transparent animate-spin" />
  );
}
