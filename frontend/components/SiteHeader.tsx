"use client";

import Link from "next/link";
import { SiteHeaderProps } from "@/components/props";

export default function SiteHeader(props: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="hbar">
        <Link href="/" className="brand">
          <div className="mark">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M3 17l5-6 4 3 6-9"
                stroke="#e2bd55"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="18" cy="5" r="2" fill="#e2bd55" />
            </svg>
          </div>
          <b>
            egy<span>-finance-radar</span>
          </b>
        </Link>
        <nav className="tabs">
          <Link
            href="/"
            className={props.activeTab === "dashboard" ? "tab active" : "tab"}
          >
            Dashboard
          </Link>
          <Link
            href="/investigate"
            className={props.activeTab === "investigate" ? "tab active" : "tab"}
          >
            Investigate
          </Link>
        </nav>
        <div className="tagline">
          Egyptian Exchange intelligence · <b>20,000 EGP</b> balanced paper
          portfolio
        </div>
        <div className="hactions">
          <div style={{ textAlign: "right" }}>
            {props.refreshSlot}
            <div
              className="freshness"
              style={{ marginTop: 6, justifyContent: "flex-end" }}
            >
              <span className="dot" />
              {props.freshnessText}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
