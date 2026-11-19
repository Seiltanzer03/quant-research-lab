import type { Dashboard, Forecast, Horizon, Metrics, Model } from '../types';
import { CONFIDENCES, DEFAULT_SETTINGS, MODEL_VERSION } from './contracts';
import type { PaperForecast, Progress, RawBar, Settings, StoredDataset } from './contracts';
import { aggregateBars, hash, inSession, quality } from './data';

export type Sample = { time: number; end: number; anchor: number; high: number; low: number; close: number; scale: number; up: number; down: number; first: number; last: number };
type Evaluation = { time: number; regime: string; coverage: Record<string, boolean>; width: number; score: number; pinball: number };
export const iso = (time: number) => new Date(time * 1000).toISOString();
export function quantile(values: number[], q: number) {
  if (!values.length) throw new Error('Недостаточно наблюдений');
  const ordered = values.slice().sort((a, b) => a - b);
  return ordered[Math.min(ordered.length - 1, Math.ceil(q * (ordered.length - 1)))];
}
const mean = (values: number[]) => values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
export function validateSettings(settings: Settings) {
  if (!Object.values(settings).every(Number.isFinite) || !Number.isInteger(settings.min_train) || !Number.isInteger(settings.lookback) || settings.min_train < 50 || settings.min_train > 1000 || settings.lookback < settings.min_train || settings.lookback > 10000 || settings.train_fraction !== .6 || settings.validation_fraction !== .2 || settings.bootstrap_repetitions !== 400) throw new Error('Некорректные параметры исследования');
}

export function knownVolatility(bars: RawBar[], step: number) {
  let variance = 0;
  const result = new Float64Array(bars.length);
  for (let i = 1; i < bars.length; i++) {
    if (bars[i].time - bars[i - 1].time === step) {
      const r = bars[i].close / bars[i - 1].close - 1;
      variance = variance === 0 ? r * r : 0.06 * r * r + 0.94 * variance;
    }
    result[i] = Math.sqrt(variance);
  }
  return result;
}

export function makeSamples(source: StoredDataset, minutes: number, leadMinutes = 0): Sample[] {
  const raw = source.bars, step = source.profile.timeframe_minutes * 60;
  const { bars } = aggregateBars(raw, source.profile, minutes);
  const index = new Map(raw.map((b, i) => [b.time, i]));
  const scale = knownVolatility(raw, step);
  const samples: Sample[] = [];
  for (const bar of bars) {
    const anchorIndex = index.get(bar.time - leadMinutes * 60 - step);
    const first = index.get(bar.time), last = index.get(bar.time + minutes * 60 - step);
    if (anchorIndex == null || first == null || last == null || scale[anchorIndex] <= 0) continue;
    const anchor = raw[anchorIndex].close;
    samples.push({ time: bar.time, end: bar.time + minutes * 60, anchor, high: bar.high, low: bar.low, close: bar.close, scale: scale[anchorIndex] * Math.sqrt(minutes / source.profile.timeframe_minutes), up: Math.max(0, bar.high / anchor - 1), down: Math.max(0, 1 - bar.low / anchor), first, last });
  }
  return samples;
}

export function predict(history: Sample[], target: Pick<Sample, 'time' | 'anchor' | 'scale'>, model: 'B0' | 'B1', settings: Settings, availableAt = target.time) {
  const known = history.filter(s => s.end <= availableAt).slice(-settings.lookback);
  const hour = new Date(target.time * 1000).getUTCHours();
  const seasonal = known.filter(s => new Date(s.time * 1000).getUTCHours() === hour);
  const chosen = seasonal.length >= settings.min_train ? seasonal : known;
  if (chosen.length < settings.min_train) throw new Error(`Нужно минимум ${settings.min_train} завершённых обучающих окон`);
  const up = chosen.map(s => s.up / (model === 'B1' ? s.scale : 1)).sort((a, b) => a - b);
  const down = chosen.map(s => s.down / (model === 'B1' ? s.scale : 1)).sort((a, b) => a - b);
  const intervals: Record<string, { lower: number; upper: number }> = {};
  for (const confidence of CONFIDENCES) {
    const q = Math.ceil((1 - (1 - confidence) / 2) * (chosen.length - 1));
    const multiplier = model === 'B1' ? target.scale : 1;
    intervals[String(confidence)] = { lower: Math.max(0, target.anchor * (1 - down[q] * multiplier)), upper: target.anchor * (1 + up[q] * multiplier) };
  }
  return { intervals, n: chosen.length, group: seasonal.length >= settings.min_train ? 'hour_utc' : 'pooled', training_end_utc: iso(chosen.at(-1)!.end) };
}

export function envelopeScore(lower: number, upper: number, low: number, high: number, confidence = 0.9) {
  return upper - lower + 2 / (1 - confidence) * (Math.max(0, lower - low) + Math.max(0, high - upper));
}
function pinball(y: number, q: number, level = .95) { const r = y - q; return Math.max(level * r, (level - 1) * r); }

function summarize(rows: Evaluation[]): Metrics {
  const coverage = Object.fromEntries(CONFIDENCES.map(c => [String(c), mean(rows.map(r => r.coverage[String(c)] ? 1 : 0))]));
  const months = [...new Set(rows.map(r => iso(r.time).slice(0, 7)))];
  const hours = [...new Set(rows.map(r => new Date(r.time * 1000).getUTCHours()))].sort((a, b) => a - b);
  return { n: rows.length, coverage, mean_width_90: mean(rows.map(r => r.width)), median_width_90: rows.length ? quantile(rows.map(r => r.width), .5) : 0, score_90_bps: mean(rows.map(r => r.score)), pinball_90_bps: mean(rows.map(r => r.pinball)),
    by_regime: ['low', 'normal', 'high'].map(regime => { const selected = rows.filter(r => r.regime === regime); return { regime, n: selected.length, coverage_90: selected.length ? mean(selected.map(r => r.coverage['0.9'] ? 1 : 0)) : null }; }),
    by_month: months.map(month => { const selected = rows.filter(r => iso(r.time).startsWith(month)); return { month, n: selected.length, coverage_90: mean(selected.map(r => r.coverage['0.9'] ? 1 : 0)), score_90_bps: mean(selected.map(r => r.score)) }; }),
    by_hour: hours.map(hour => { const selected = rows.filter(r => new Date(r.time * 1000).getUTCHours() === hour); return { hour_utc: hour, n: selected.length, coverage_90: mean(selected.map(r => r.coverage['0.9'] ? 1 : 0)) }; }),
  };
}

export function bootstrapDaily(rows: { time: number; value: number }[], repetitions = 400) {
  const blocks = new Map<string, { sum: number; n: number }>();
  for (const row of rows) { const key = iso(row.time).slice(0, 10); const block = blocks.get(key) ?? { sum: 0, n: 0 }; block.sum += row.value; block.n++; blocks.set(key, block); }
  const groups = [...blocks.values()];
  if (groups.length < 5) return { days: groups.length, ci95: null };
  let seed = 42;
  const random = () => { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return (seed >>> 0) / 4294967296; };
  const draws: number[] = [];
  for (let r = 0; r < repetitions; r++) {
    let sum = 0, n = 0;
    for (let i = 0; i < groups.length; i++) { const group = groups[Math.floor(random() * groups.length)]; sum += group.sum; n += group.n; }
    draws.push(sum / n);
  }
  return { days: groups.length, ci95: [quantile(draws, .025), quantile(draws, .975)] };
}

export async function researchHorizon(source: StoredDataset, minutes: number, settings: Settings, datasetHash: string, onProgress?: (p: Progress) => void): Promise<Horizon> {
  const aggregated = aggregateBars(source.bars, source.profile, minutes);
  const samples = makeSamples(source, minutes);
  const minCount = Math.max(180, Math.ceil(settings.min_train / settings.train_fraction) + 10);
  const basic = { minutes, bars: aggregated.bars.slice(-220), history: [], models: [], live_forecast: null, n_bars: aggregated.bars.length, incomplete_windows_excluded: aggregated.incomplete };
  if (samples.length < minCount) return { ...basic, status: 'INSUFFICIENT_DATA' };
  const validationStart = Math.max(settings.min_train, Math.floor(samples.length * settings.train_fraction));
  const testStart = Math.floor(samples.length * (settings.train_fraction + settings.validation_fraction));
  const runId = await hash({ datasetHash, settings, minutes, version: MODEL_VERSION });
  const issued = new Date().toISOString();
  const tests: Record<string, Evaluation[]> = { B0: [], B1: [] }, validations: Record<string, Evaluation[]> = { B0: [], B1: [] };
  const journal: Forecast[] = [];
  for (let i = validationStart; i < samples.length; i++) {
    const target = samples[i], history = samples.slice(Math.max(0, i - settings.lookback), i);
    const pastScale = history.map(s => s.scale).sort((a, b) => a - b);
    const lowerScale = pastScale[Math.floor((pastScale.length - 1) * .33)], upperScale = pastScale[Math.floor((pastScale.length - 1) * .67)];
    const regime = target.scale < lowerScale ? 'low' : target.scale > upperScale ? 'high' : 'normal';
    for (const name of ['B0', 'B1'] as const) {
      const prediction = predict(history, target, name, settings);
      const bounds = prediction.intervals['0.9'];
      const evaluation: Evaluation = { time: target.time, regime, coverage: Object.fromEntries(CONFIDENCES.map(c => [String(c), prediction.intervals[String(c)].lower <= target.low && prediction.intervals[String(c)].upper >= target.high])), width: bounds.upper - bounds.lower,
        score: envelopeScore(bounds.lower, bounds.upper, target.low, target.high) / target.anchor * 10000,
        pinball: (pinball(target.up, bounds.upper / target.anchor - 1) + pinball(target.down, 1 - bounds.lower / target.anchor)) * 10000 };
      (i >= testStart ? tests[name] : validations[name]).push(evaluation);
      if (i >= testStart && i >= samples.length - 180 && name === 'B0') {
        journal.push({ forecast_id: `${runId.slice(0, 20)}-${name}-${target.time}`, run_id: runId, model_version: `${name}_${MODEL_VERSION}`, mode: 'historical_simulation', issued_at_utc: issued, available_at_utc: issued, as_of_utc: iso(target.time), horizon_start_utc: iso(target.time), horizon_end_utc: iso(target.end), anchor_price: target.anchor, forecast_quantiles: prediction.intervals, training_n: prediction.n, training_group: prediction.group, regime, quality_status: 'BACKTEST_ONLY', outcome: { realized_high: target.high, realized_low: target.low, realized_close: target.close, joint_covered_90: evaluation.coverage['0.9'], score_90_bps: evaluation.score } });
      }
    }
    if (i % 100 === 0) { onProgress?.({ stage: 'research', current: i - validationStart, total: samples.length - validationStart, message: `${minutes} мин: проверено ${i - validationStart} из ${samples.length - validationStart} окон` }); await new Promise<void>(resolve => setTimeout(resolve, 0)); }
  }
  const models: Model[] = (['B0', 'B1'] as const).map(name => {
    const metrics = summarize(tests[name]);
    const reasons = ['FORWARD_EVIDENCE_MISSING'];
    if (metrics.n < 500) reasons.push('OOS_N_BELOW_500');
    if (metrics.coverage['0.9'] < .87 || metrics.coverage['0.9'] > .93) reasons.push('COVERAGE_OUTSIDE_87_93');
    if (metrics.by_regime.some(r => r.n >= 50 && Math.abs((r.coverage_90 ?? 0) - .9) > .07)) reasons.push('REGIME_CALIBRATION_FAILED');
    return { id: `${name}_${MODEL_VERSION}`, name: name === 'B0' ? 'Сезонные исторические квантили' : 'Квантили с EWMA-масштабом', role: name === 'B0' ? 'baseline' : 'challenger', test: metrics, validation: summarize(validations[name]), gate: { status: 'BACKTEST_ONLY', approved: false, reasons } };
  });
  if (tests.B0.length !== tests.B1.length || tests.B0.some((r, i) => r.time !== tests.B1[i].time)) throw new Error('Несовпадающие timestamps в сравнении моделей');
  const differences = tests.B0.map((r, i) => ({ time: r.time, value: r.score - tests.B1[i].score }));
  const bootstrap = bootstrapDaily(differences, settings.bootstrap_repetitions);
  const comparable = Math.abs(models[0].test.coverage['0.9'] - models[1].test.coverage['0.9']) <= .02;
  return { ...basic, status: 'BACKTEST_ONLY', run_id: runId, history: journal, models, forward_count: 0, split: { validation_start_utc: iso(samples[validationStart].time), test_start_utc: iso(samples[testStart].time), last_label_end_utc: iso(samples.at(-1)!.end) }, paired: { n: differences.length, day_blocks: bootstrap.days, ci95: bootstrap.ci95, mean_score_improvement_bps: mean(differences.map(d => d.value)), coverage_comparable: comparable, superiority_proven: Boolean(comparable && differences.length >= 500 && bootstrap.ci95 && bootstrap.ci95[0] > 0) } };
}

export async function runResearch(source: StoredDataset, settings: Settings = DEFAULT_SETTINGS, onProgress?: (p: Progress) => void): Promise<Dashboard> {
  validateSettings(settings);
  onProgress?.({ stage: 'quality', current: 0, total: source.bars.length, message: 'Проверяю UTC-сетку, календарь и полноту исходной истории' });
  const report = quality(source);
  const datasetHash = await hash({ profile: source.profile, bars: source.bars });
  const horizons: Record<string, Horizon> = {};
  for (const minutes of [15, 60, 240]) horizons[String(minutes)] = await researchHorizon(source, minutes, settings, datasetHash, onProgress);
  return { research_settings: structuredClone(settings), schema_version: '2.0', generated_at_utc: new Date().toISOString(), mode: 'RESEARCH', git_sha: import.meta.env.VITE_GIT_SHA ?? MODEL_VERSION, operational_status: report.age_minutes <= 5 ? 'DATA_AVAILABLE' : 'HISTORICAL_DATA', datasets: [{ dataset_id: source.id, dataset_hash: datasetHash, profile: { ...source.profile }, quality: report, latest_close: source.bars.at(-1)!.close, horizons }], modules: [], limitations: ['Метрики — историческая проверка фиксированных алгоритмов, не подтверждение доходности.', 'Прогноз до события фиксируется отдельно от исторической симуляции.'] };
}

export async function issuePaper(source: StoredDataset, minutes: number, settings: Settings, now = Date.now() / 1000): Promise<PaperForecast> {
  validateSettings(settings);
  if (![15, 60, 240].includes(minutes)) throw new Error('Выбери M15, H1 или H4');
  if (source.profile.timeframe_minutes !== 1 || !source.profile.calendar.verified) throw new Error('Для forward-прогноза нужны M1 и подтверждённый календарь');
  const last = source.bars.at(-1);
  if (!last || now - last.time - 60 > 180 || now < last.time + 60) throw new Error('Источник устарел: нужна закрытая M1 не старше 3 минут');
  const start = (Math.floor(now / (minutes * 60)) + 1) * minutes * 60, end = start + minutes * 60;
  for (let t = start; t < end; t += 60) if (!inSession(t, source.profile)) throw new Error('Следующая полная свеча пересекает перерыв торговой сессии');
  const lastIndex = source.bars.length - 1;
  for (let i = Math.max(1, lastIndex - 240); i <= lastIndex; i++) if (source.bars[i].time - source.bars[i - 1].time !== 60) throw new Error('В критическом M1-окне есть пропуск: прогноз заблокирован');
  const lead = (start - last.time - 60) / 60;
  const samples = makeSamples(source, minutes, lead).filter(s => s.end <= now);
  const volatility = knownVolatility(source.bars, 60)[lastIndex] * Math.sqrt(minutes);
  const prediction = predict(samples, { time: start, anchor: last.close, scale: volatility }, 'B0', settings, now);
  const forecastId = await hash(`${source.id}/${minutes}/${start}/${MODEL_VERSION}`);
  const datasetHash = await hash({ profile: source.profile, bars: source.bars });
  const issued = Date.now() / 1000;
  if (issued >= start) throw new Error('Расчёт завершился после начала окна. Обнови прогноз для следующей свечи.');
  return { forecast_id: forecastId, dataset_id: source.id, model_version: `B0_lead_${lead}m_${MODEL_VERSION}`, source_id: source.profile.source_symbol, instrument_id: source.profile.instrument_id, issued_at_utc: iso(issued), available_at_utc: iso(issued), as_of_utc: iso(last.time + 60), horizon_start_utc: iso(start), horizon_end_utc: iso(end), timeframe_minutes: minutes, lead_minutes: lead, anchor_price: last.close, training_n: prediction.n, dataset_hash: datasetHash, settings: structuredClone(settings), mode: 'forward_paper', quality_status: 'PAPER_VALIDATING', forecast_quantiles: prediction.intervals, is_trading_qualified: false, eligible_for_forward_validation: true };
}

export function evaluatePaper(forecast: PaperForecast, source: StoredDataset): PaperForecast['outcome'] | null {
  if (forecast.dataset_id !== source.id || forecast.outcome) return forecast.outcome ?? null;
  const start = Date.parse(forecast.horizon_start_utc) / 1000, end = Date.parse(forecast.horizon_end_utc) / 1000;
  if (Date.parse(forecast.available_at_utc) / 1000 >= start) throw new Error('Поздняя запись не может получить forward-оценку');
  const bars = source.bars.filter(b => b.time >= start && b.time < end);
  if (bars.length !== forecast.timeframe_minutes || bars.some((b, i) => b.time !== start + i * 60) || bars.at(-1)!.time + 60 > Date.now() / 1000) return null;
  const low = Math.min(...bars.map(b => b.low)), high = Math.max(...bars.map(b => b.high)), bounds = forecast.forecast_quantiles['0.9'];
  return { realized_high: high, realized_low: low, realized_close: bars.at(-1)!.close, evaluated_at_utc: new Date().toISOString(), joint_covered_90: bounds.lower <= low && high <= bounds.upper };
}
