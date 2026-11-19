export type Bounds = { lower: number; upper: number };
export type Bar = { time: number; open: number; high: number; low: number; close: number };
export type Forecast = {
  forecast_id: string; run_id: string; model_version: string; mode: string;
  issued_at_utc: string; available_at_utc: string; as_of_utc: string;
  horizon_start_utc: string; horizon_end_utc: string; anchor_price: number;
  forecast_quantiles: Record<string, Bounds>; training_n: number; training_group: string;
  regime: string; quality_status: string;
  outcome: { realized_high: number; realized_low: number; realized_close: number; joint_covered_90: boolean; score_90_bps: number };
};
export type Metrics = {
  n: number; coverage: Record<string, number>; mean_width_90: number; median_width_90: number;
  score_90_bps: number; pinball_90_bps: number;
  by_regime: { regime: string; n: number; coverage_90: number | null }[];
  by_month: { month: string; n: number; coverage_90: number; score_90_bps: number }[];
  by_hour: { hour_utc: number; n: number; coverage_90: number }[];
};
export type Model = { id: string; name: string; role: string; test: Metrics; validation: Metrics; gate: { status: string; approved: boolean; reasons: string[] } };
export type Horizon = {
  minutes: number; status: string; bars: Bar[]; history: Forecast[]; models: Model[];
  live_forecast: null; forward_count?: number; n_bars?: number; incomplete_windows_excluded: number;
  run_id?: string; split?: { validation_start_utc: string; test_start_utc: string; last_label_end_utc: string };
  paired?: { n: number; day_blocks: number; ci95: number[] | null; mean_score_improvement_bps?: number; coverage_comparable: boolean; superiority_proven: boolean };
};
export type Profile = {
  instrument_id: string; source: string; source_symbol: string; asset_class: string;
  is_demo: boolean; data_license: string; publish_allowed: boolean; timeframe_minutes: number;
  price_precision: number; available_volume_type: string;
  calendar: { timezone: string; verified: boolean; sessions: unknown[]; closed_dates: string[] };
};
export type Dataset = {
  dataset_id: string; dataset_hash: string; profile: Profile; latest_close: number | null;
  quality: { status: string; flags: string[]; rows: number; coverage: number | null; missing_bars: number; missing_examples: string[]; off_session_bars: number; first_bar_utc: string; last_bar_close_utc: string; age_minutes: number; history_completeness: string };
  horizons: Record<string, Horizon>;
};
export type Dashboard = {
  schema_version: string; generated_at_utc: string; mode: string; git_sha: string;
  datasets: Dataset[]; limitations: string[]; operational_status: string;
  modules: { id: string; name: string; status: string }[];
};
