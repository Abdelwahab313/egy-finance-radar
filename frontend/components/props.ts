/* Shared prop contracts for the dashboard section components. The page wires
   exactly these; each section component imports its own interface from here so
   the contract can't drift. */

import { Scene, Holdings, Position, Stock, Plan, Recommendation, Bucket } from "@/lib/types";
import { ReactNode } from "react";

export interface SiteHeaderProps {
  /** e.g. "prices 15/15 · β via proxy · YFinanceSource" */
  freshnessText: string;
  activeTab: "dashboard" | "investigate";
  /** the existing RefreshButton, kept in the page to preserve polling logic */
  refreshSlot: ReactNode;
}

export interface HeroBandProps {
  equity: number; // market value of all placed lots
  pnl: number; // unrealized P&L (EGP)
  pnlPct?: number | null; // ratio, e.g. 0.003
  deployedPct: number; // ratio of capital, e.g. 1.09
  costBasis: number;
  overUnder: number; // capital - costBasis (negative = over-deployed)
  cash: number;
  tbillAmount?: number | null;
  tbillYield?: number | null; // ratio, e.g. 0.234
}

export interface SceneCardProps {
  scene: Scene;
}

export interface AccountSummaryProps {
  startingCapital: number;
  equity: number; // model equity (invested_value + entry costs)
  equityPct?: number | null; // ratio
  tbillAmount?: number | null;
  tbillYield?: number | null; // ratio
  tbillIncome?: number | null;
  cash: number;
  broker: string;
}

export interface AllocationDonutProps {
  /** keyed by Bucket enum value → ratio (e.g. { stable_bluechip: 0.435 }) */
  bucket: Record<string, number>;
  /** keyed by sector-group label → ratio (e.g. { Financials: 0.399 }) */
  sector: Record<string, number>;
  /** center label, e.g. "14.4k" */
  centerValue: string;
}

export interface ContributionItem {
  symbol: string;
  pnl: number;
}
export interface ContributionBarsProps {
  items: ContributionItem[];
  net: number;
}

export interface PositionsLedgerProps {
  holdings: Holdings | null;
  positions: Position[];
  bucketExposure: Record<string, number>;
  sectorExposure: Record<string, number>;
  stocks: Stock[];
  shortlist: string[];
  excludedBySignal?: string[];
  modelNotes?: string[];
  source: string;
  recosBySym?: Record<string, Recommendation>;
  /** the existing AddOrderForm, kept in the page to preserve POST logic */
  addOrderSlot: ReactNode;
  /** holdings-table footnote, if any */
  holdingsNote?: string | null;
}

export interface InvestmentPlanProps {
  plan: Plan;
}

/** re-export for component convenience */
export type { Bucket };
