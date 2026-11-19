import type { RawBar, ScenarioInput, ScenarioResult, Settings, StoredDataset } from './contracts';
import { bootstrapDaily, iso, knownVolatility, makeSamples, validateSettings } from './research';

export function observedTouch(bars: RawBar[], direction: 'long' | 'short', tp: number, sl: number) {
  let tpTouch = false, slTouch = false;
  let first: 'TP' | 'SL' | 'AMBIGUOUS' | 'NEITHER' = 'NEITHER';
  for (const bar of bars) {
    const take = direction === 'long' ? bar.high >= tp : bar.low <= tp;
    const stop = direction === 'long' ? bar.low <= sl : bar.high >= sl;
    tpTouch ||= take; slTouch ||= stop;
    if (first === 'NEITHER' && (take || stop)) first = take && stop ? 'AMBIGUOUS' : take ? 'TP' : 'SL';
  }
  return { first, tpTouch, slTouch };
}

export function evaluateScenario(source: StoredDataset, input: ScenarioInput, settings: Settings): ScenarioResult {
  validateSettings(settings);
  if (source.profile.timeframe_minutes !== 1) throw new Error('Для порядка TP/SL нужна M1-история. Импорт M15/H1 сохраняет диапазоны, но не определяет порядок касаний.');
  const { direction, entry, tp, sl, cost_points, minutes } = input;
  if (![15, 60, 240].includes(minutes)) throw new Error('Выбери M15, H1 или H4');
  if (![entry, tp, sl, cost_points].every(Number.isFinite) || Math.min(entry, tp, sl) <= 0 || cost_points < 0 || (direction === 'long' ? !(sl < entry && entry < tp) : !(tp < entry && entry < sl))) throw new Error('Проверь порядок Entry, TP, SL и издержки');
  const samples = makeSamples(source, minutes).slice(-settings.lookback);
  if (samples.length < settings.min_train) throw new Error(`Для сценария нужно минимум ${settings.min_train} полных исторических окон`);
  const recentScale = knownVolatility(source.bars, 60).at(-1)! * Math.sqrt(minutes);
  const risk = Math.abs(entry - sl), reward = Math.abs(tp - entry), rr = reward / risk, costR = cost_points / risk;
  let takeFirst = 0, stopFirst = 0, neither = 0, ambiguous = 0, takeTouch = 0, stopTouch = 0, lowerR = 0, upperR = 0;
  const points: { time: number; value: number }[] = [];
  for (const sample of samples) {
    const factor = entry / sample.anchor * (input.volatility_scaled ? recentScale / sample.scale : 1);
    const mapped = source.bars.slice(sample.first, sample.last + 1).map(b => ({ ...b, open: entry + (b.open - sample.anchor) * factor, high: entry + (b.high - sample.anchor) * factor, low: entry + (b.low - sample.anchor) * factor, close: entry + (b.close - sample.anchor) * factor }));
    const outcome = observedTouch(mapped, direction, tp, sl);
    if (outcome.tpTouch) takeTouch++;
    if (outcome.slTouch) stopTouch++;
    let low: number, high: number;
    if (outcome.first === 'TP') { takeFirst++; low = high = rr - costR; }
    else if (outcome.first === 'SL') { stopFirst++; low = high = -1 - costR; }
    else if (outcome.first === 'AMBIGUOUS') { ambiguous++; low = -1 - costR; high = rr - costR; }
    else { neither++; const movement = mapped.at(-1)!.close - entry; low = high = (direction === 'long' ? movement : -movement) / risk - costR; }
    lowerR += low; upperR += high; points.push({ time: sample.time, value: low });
  }
  const bootstrap = bootstrapDaily(points, settings.bootstrap_repetitions);
  return { sample_n: samples.length, days: bootstrap.days, tp_first: takeFirst / samples.length, sl_first: stopFirst / samples.length, neither: neither / samples.length, ambiguous: ambiguous / samples.length, tp_touch: takeTouch / samples.length, sl_touch: stopTouch / samples.length, rr, mean_r_lower: lowerR / samples.length, mean_r_upper: upperR / samples.length, mean_r_ci95: bootstrap.ci95, ambiguous_fraction: ambiguous / samples.length, sample_from_utc: iso(samples[0].time), sample_to_utc: iso(samples.at(-1)!.end), source_symbol: source.profile.source_symbol, input, mode: 'historical_replay', warning: 'Это частоты и результат исторических сценариев, не проверенные вероятности будущей сделки. Entry считается начальной ценой уже открытой позиции; отложенный вход не моделируется. Издержки заданы пользователем; gap/slippage исполнения за пределами этих предположений не воспроизводятся.' };
}
