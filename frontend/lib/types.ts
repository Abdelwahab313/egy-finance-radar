export type Bucket =
  | "stable_bluechip"
  | "value"
  | "growth"
  | "watchlist"
  | "speculative";

export interface StockMetrics {
  price?: number;
  market_cap?: number;
  pe?: number;
  pb?: number;
  dividend_yield?: number;
  payout_ratio?: number;
  roe?: number;
  eps_growth_3y?: number;
  beta?: number;
  volatility?: number;
  avg_daily_value?: number;
  ret_1m?: number;
  ret_3m?: number;
  ret_1y?: number;
  last_date?: string;
  data_ok?: boolean;
  provenance?: Record<string, string>;
}

export interface Stock {
  symbol: string;
  name: string;
  sector: string;
  eligible: boolean;
  gate_fails: string[];
  bucket: Bucket;
  score: number;
  metrics: StockMetrics;
}

export type Sleeve = "core" | "satellite";

export interface Position {
  symbol: string;
  name: string;
  sector: string;
  bucket: Bucket;
  score: number;
  price: number;
  shares: number;
  notional: number;
  entry_cost: number;
  target_weight: number;
  actual_weight: number;
  signal?: string;
  sleeve?: Sleeve;
  stop_loss?: number | null;
  take_profit?: number | null;
}

export interface TbillSleeve {
  amount_egp: number;
  pct_of_capital: number;
  annual_yield: number;
  expected_annual_income_egp: number;
  note?: string;
}

export interface Plan {
  sleeves: Record<
    string,
    { symbols?: string[]; pct_of_capital?: number; horizon: string; review?: string; rule?: string }
  >;
  sell_rules: string[];
  cadence: { monthly: string; quarterly: string; note?: string };
  expected_income_egp: {
    tbill_annual: number;
    net_dividends_annual: number;
    total_annual: number;
    note?: string;
  };
}

export interface Portfolio {
  starting_capital: number;
  cash_buffer_pct: number;
  equity_pct?: number;
  broker: string;
  tbill_sleeve?: TbillSleeve;
  positions: Position[];
  invested_value: number;
  entry_costs_total: number;
  cash_remaining: number;
  num_positions: number;
  sector_exposure: Record<string, number>;
  sector_group_exposure?: Record<string, number>;
  bucket_exposure: Record<string, number>;
  excluded_by_signal?: string[];
  plan?: Plan;
  notes: string[];
}

export interface HoldingLot {
  symbol: string;
  name?: string;
  sector?: string;
  shares: number;
  entry_price?: number;
  price?: number;
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pct?: number | null;
  signal?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  horizon?: "core" | "tactical" | null;
}

export interface Holdings {
  as_of?: string;
  note?: string;
  lots: HoldingLot[];
  cost_basis_total: number;
  market_value_total: number;
  unrealized_pnl_total: number;
  unrealized_pct_total?: number | null;
  deployed_pct_of_capital: number;
  cash_uninvested: number;
}

export interface Recommendation {
  symbol: string;
  as_of: string | null;
  horizon: "core" | "tactical";
  action: "hold" | "add" | "trim" | "sell";
  rationale?: string | null;
  price_target?: number | null;
  stop_loss?: number | null;
  report_file?: string | null;
}

export interface Scene {
  as_of: string;
  headline: string;
  egp_usd: string;
  inflation: string;
  policy_rate: string;
  tbill_12m?: string;
  tax_note?: string;
  tailwinds: string[];
  risks: string[];
}

export interface DataQuality {
  price_history: string;
  beta_source: string;
  mostly_static_fields: string[];
  caveat: string;
  per_field: Record<string, { live_or_computed: number; static: number }>;
}

export interface Snapshot {
  generated_at: string;
  source: string;
  index_source?: string;
  index_data_ok: boolean;
  live_data_ok_count: number;
  price_data_ok_count?: number;
  data_quality?: DataQuality;
  universe_size: number;
  starting_capital_egp: number;
  scene: Scene;
  stocks: Stock[];
  shortlist: string[];
  portfolio: Portfolio;
  holdings?: Holdings | null;
}
