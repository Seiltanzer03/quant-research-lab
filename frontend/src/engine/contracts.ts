export type Instrument = 'XAUUSD' | 'NAS100' | 'SPX500' | 'XAGUSD' | 'GC_F' | 'NQ_F';
export type RawBar = { time: number; open: number; high: number; low: number; close: number; volume: number | null };
export type Session = { weekdays: number[]; open_minute: number; close_minute: number };
export type SourceProfile = {
  instrument_id: Instrument; source: string; source_symbol: string; asset_class: 'spot' | 'cfd' | 'index' | 'futures';
  timeframe_minutes: 1 | 5 | 15 | 60; timestamp_timezone: string; timestamp_unit: 's' | 'ms';
  price_precision: number; tick_size: number; available_volume_type: string;
  data_license: string; publish_allowed: boolean; is_demo: false;
  calendar: { timezone: string; verified: boolean; sessions: Session[]; closed_dates: string[]; overrides?: Record<string, Session[]> };
};
export type Settings = { lookback: number; min_train: number; train_fraction: number; validation_fraction: number; bootstrap_repetitions: number };
export const DEFAULT_SETTINGS: Settings = { lookback: 1000, min_train: 100, train_fraction: 0.6, validation_fraction: 0.2, bootstrap_repetitions: 400 };
export const MODEL_VERSION = 'browser_ranges_v3';
export const CONFIDENCES = [0.5, 0.8, 0.9, 0.95];
export type Progress = { stage: 'download' | 'quality' | 'research' | 'scenario'; current: number; total: number; message: string };
export type StoredDataset = { id: string; profile: SourceProfile; bars: RawBar[]; fetched_at_utc: string; requested_from_utc: string; requested_to_utc: string; errors: string[] };
export type ScenarioInput = { direction: 'long' | 'short'; entry: number; tp: number; sl: number; cost_points: number; minutes: number; volatility_scaled: boolean };
export type ScenarioResult = {
  sample_n: number; days: number; tp_first: number; sl_first: number; neither: number; ambiguous: number;
  tp_touch: number; sl_touch: number; rr: number; mean_r_lower: number; mean_r_upper: number;
  mean_r_ci95: number[] | null; ambiguous_fraction: number; sample_from_utc: string; sample_to_utc: string;
  source_symbol: string; input: ScenarioInput; mode: 'historical_replay'; warning: string;
  data_resolution_minutes: number;
};
export type PaperForecast = {
  forecast_id: string; dataset_id: string; model_version: string; source_id: string; instrument_id: string;
  issued_at_utc: string; available_at_utc: string; as_of_utc: string; horizon_start_utc: string; horizon_end_utc: string;
  timeframe_minutes: number; lead_minutes: number; anchor_price: number; training_n: number; dataset_hash: string;
  mode: 'forward_paper'; quality_status: 'PAPER_VALIDATING'; forecast_quantiles: Record<string, { lower: number; upper: number }>;
  is_trading_qualified: false; eligible_for_forward_validation: true;
  settings: Settings;
  outcome?: { realized_high: number; realized_low: number; realized_close: number; evaluated_at_utc: string; joint_covered_90: boolean };
};
