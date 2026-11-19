import 'fake-indexeddb/auto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SourceProfile, StoredDataset } from './contracts';
import { DEFAULT_SETTINGS } from './contracts';
import { aggregateBars, inSession, normalizeBars, parseCSV, parseProviderResponse, PROVIDER_PROFILES, quality, sourceURL } from './data';
import { bootstrapDaily, evaluatePaper, issuePaper, makeSamples, predict, researchHorizon } from './research';
import { evaluateScenario, observedTouch } from './scenario';
import { appendPaper, loadWorkspace, saveRun, saveSource } from './storage';
import { downloadSource } from './provider';

const profile: SourceProfile = { ...structuredClone(PROVIDER_PROFILES.XAUUSD), source: 'test_fixture_only', source_symbol: 'TEST:UNIT_FIXTURE', calendar: { timezone: 'UTC', verified: true, sessions: [{ weekdays: [0, 1, 2, 3, 4, 5, 6], open_minute: 0, close_minute: 1440 }], closed_dates: [] } };
function fixture(n = 5760, end = Date.parse('2026-11-18T10:00:00Z') / 1000): StoredDataset {
  let price = 100;
  const bars = Array.from({ length: n }, (_, i) => {
    const open = price; price *= 1 + Math.sin(i * .13) * .0003 + Math.cos(i * .43) * .00015;
    return { time: end - (n - i) * 60, open, high: Math.max(open, price) + .02, low: Math.min(open, price) - .02, close: price, volume: null };
  });
  return { id: 'unit-source', profile: structuredClone(profile), bars, fetched_at_utc: new Date().toISOString(), requested_from_utc: new Date(bars[0].time * 1000).toISOString(), requested_to_utc: new Date(end * 1000).toISOString(), errors: [] };
}
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe('Real data contracts', () => {
  it('requires valid OHLC, removes identical duplicates and rejects conflicts', () => {
    const source = fixture(10);
    expect(normalizeBars([...source.bars, source.bars[0]], profile).duplicates).toBe(1);
    expect(() => normalizeBars([...source.bars, { ...source.bars[0], high: 200 }], profile)).toThrow('Конфликт');
    expect(() => normalizeBars([{ ...source.bars[0], high: 1 }], profile)).toThrow('Некорректная');
  });
  it('does not use unfinished candles or guess a naïve DST clock', () => {
    const source = fixture(10);
    expect(normalizeBars(source.bars, profile, source.bars[4].time + 30).bars).toHaveLength(4);
    expect(() => parseCSV('time,open,high,low,close\n2026-11-01 01:30:00,100,101,99,100', { ...profile, timestamp_timezone: 'America/New_York' })).toThrow('UTC-offset');
    expect(parseCSV('time,open,high,low,close\n2026-11-01T00:00:00Z,100,101,99,100', profile).bars[0].volume).toBeNull();
  });
  it('keeps provider instruments distinct and calendars use DST', () => {
    expect(sourceURL(PROVIDER_PROFILES.NAS100, 1, 'callback')).toContain('instrument=USATECH.IDX%2FUSD');
    expect(PROVIDER_PROFILES.NAS100.source_symbol).not.toContain('NQ');
    expect(inSession(Date.parse('2026-03-01T23:00:00Z') / 1000, PROVIDER_PROFILES.XAUUSD)).toBe(true);
    expect(inSession(Date.parse('2026-03-08T22:00:00Z') / 1000, PROVIDER_PROFILES.XAUUSD)).toBe(true);
    expect(inSession(Date.parse('2026-03-08T21:30:00Z') / 1000, PROVIDER_PROFILES.XAUUSD)).toBe(false);
  });
  it.each([15, 60, 240])('aggregates M1 into complete %i-minute bars against an independent reference', minutes => {
    const source = fixture(960, Date.parse('2026-11-18T16:00:00Z') / 1000);
    const actual = aggregateBars(source.bars, profile, minutes);
    expect(actual.incomplete).toBe(0);
    actual.bars.forEach((bar, i) => {
      const group = source.bars.slice(i * minutes, (i + 1) * minutes);
      expect(bar.open).toBe(group[0].open); expect(bar.close).toBe(group.at(-1)!.close);
      expect(bar.high).toBe(Math.max(...group.map(b => b.high))); expect(bar.low).toBe(Math.min(...group.map(b => b.low)));
    });
  });
  it('reports gaps and excludes their aggregated windows', () => {
    const source = fixture(960, Date.parse('2026-11-18T16:00:00Z') / 1000);
    source.bars.splice(12, 1);
    expect(quality(source).missing_bars).toBe(1);
    expect(aggregateBars(source.bars, profile, 15).incomplete).toBe(1);
  });
  it('parses JSONP as data without evaluating provider code', () => {
    expect(parseProviderResponse('cb([[1609459200000,100,101,99,100,null]]);', 'cb')[0]).toEqual({ time: 1609459200, open: 100, high: 101, low: 99, close: 100, volume: null });
    expect(() => parseProviderResponse('alert("wrong callback")', 'cb')).toThrow();
  });
});

describe('Range research and forward records', () => {
  it('future OHLC changes cannot alter an earlier prediction', () => {
    const source = fixture(), samples = makeSamples(source, 15), target = samples[220];
    const mutated = structuredClone(source);
    for (const bar of mutated.bars) if (bar.time >= target.time) { bar.open *= 2; bar.high *= 2; bar.low *= 2; bar.close *= 2; }
    const changed = makeSamples(mutated, 15), modifiedTarget = changed.find(s => s.time === target.time)!;
    for (const model of ['B0', 'B1'] as const) expect(predict(samples, target, model, DEFAULT_SETTINGS)).toEqual(predict(changed, modifiedTarget, model, DEFAULT_SETTINGS));
  });
  it('checks high AND low, keeps nested intervals and paired timestamps', async () => {
    const source = fixture();
    const report = await researchHorizon(source, 15, DEFAULT_SETTINGS, 'fixture-hash');
    expect(report.models[0].test.n).toBe(report.models[1].test.n);
    expect(report.paired?.n).toBe(report.models[0].test.n);
    expect(report.history.length).toBeGreaterThan(0);
    for (const row of report.history) {
      const q = row.forecast_quantiles['0.9'];
      expect(row.outcome.joint_covered_90).toBe(q.lower <= row.outcome.realized_low && q.upper >= row.outcome.realized_high);
      expect(row.mode).toBe('historical_simulation');
      expect(row.forecast_quantiles['0.95'].lower).toBeLessThanOrEqual(q.lower);
      expect(row.forecast_quantiles['0.95'].upper).toBeGreaterThanOrEqual(q.upper);
    }
    expect(report.models.every(m => !m.gate.approved)).toBe(true);
    expect(bootstrapDaily([{ time: 1, value: 1 }]).ci95).toBeNull();
  });
  it('issues before the next bar with an explicit lead; stale or gapped inputs fail', async () => {
    const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-19T10:00:05Z'));
    const source = fixture(5760, Date.parse('2026-11-19T10:00:00Z') / 1000);
    const record = await issuePaper(source, 15, DEFAULT_SETTINGS);
    expect(Date.parse(record.available_at_utc)).toBeLessThan(Date.parse(record.horizon_start_utc));
    expect(record.lead_minutes).toBe(15);
    expect(record.is_trading_qualified).toBe(false);
    expect(evaluatePaper(record, source)).toBeNull();
    const gapped = structuredClone(source); gapped.bars.splice(gapped.bars.length - 20, 1);
    await expect(issuePaper(gapped, 15, DEFAULT_SETTINGS)).rejects.toThrow('пропуск');
    clock.mockReturnValue(Date.parse('2026-11-19T11:00:00Z'));
    await expect(issuePaper(source, 15, DEFAULT_SETTINGS)).rejects.toThrow('устарел');
  });
  it('persists sources without removing earlier bars and never overwrites a paper record', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-19T10:00:05Z'));
    const source = fixture(5760, Date.parse('2026-11-19T10:00:00Z') / 1000);
    await saveSource(source);
    const later = await saveSource({ ...source, bars: source.bars.slice(-10) });
    expect(later.bars).toHaveLength(source.bars.length);
    const forecast = await issuePaper(source, 15, DEFAULT_SETTINGS);
    await appendPaper(forecast);
    const old = await appendPaper({ ...forecast, anchor_price: 999 });
    expect(old.anchor_price).toBe(forecast.anchor_price);
    expect((await loadWorkspace()).paper.find(p => p.forecast_id === forecast.forecast_id)?.anchor_price).toBe(forecast.anchor_price);
  });
  it('re-running one snapshot returns the original saved simulation timestamps', async () => {
    const source = fixture();
    const horizon = await researchHorizon(source, 15, DEFAULT_SETTINGS, 'same-snapshot');
    const report = { schema_version: '2.0', generated_at_utc: '2026-11-19T10:00:00Z', mode: 'RESEARCH', git_sha: 'test', operational_status: 'HISTORICAL_DATA', datasets: [{ dataset_id: source.id, dataset_hash: 'same-snapshot', profile: source.profile, quality: quality(source), latest_close: 100, horizons: { '15': horizon } }], modules: [], limitations: [] };
    const first = await saveRun(source, report, DEFAULT_SETTINGS);
    const next = await saveRun(source, { ...report, generated_at_utc: '2026-11-19T11:00:00Z' }, DEFAULT_SETTINGS);
    expect(next).toEqual(first);
  });
});

describe('Scenario replay', () => {
  it('does not resolve same-M1 double hits as wins', () => {
    const bars = [{ time: 0, open: 100, high: 120, low: 80, close: 100, volume: null }];
    expect(observedTouch(bars, 'long', 110, 90).first).toBe('AMBIGUOUS');
    expect(observedTouch(bars, 'short', 90, 110).first).toBe('AMBIGUOUS');
  });
  it('includes time exit, costs and pessimistic/optimistic ambiguity bounds', () => {
    const source = fixture();
    const result = evaluateScenario(source, { direction: 'long', entry: 100, tp: 100.05, sl: 99.95, cost_points: .005, minutes: 15, volatility_scaled: true }, DEFAULT_SETTINGS);
    expect(result.tp_first + result.sl_first + result.neither + result.ambiguous).toBeCloseTo(1);
    expect(result.mean_r_lower).toBeLessThanOrEqual(result.mean_r_upper);
    expect(result.mode).toBe('historical_replay');
    expect(() => evaluateScenario({ ...source, profile: { ...profile, timeframe_minutes: 15 } }, result.input, DEFAULT_SETTINGS)).toThrow('M1');
  });
});

describe('Provider download contract', () => {
  it('does not stop at a short page or turn rate limits into demo data', async () => {
    const start = Date.parse('2026-11-18T00:00:00Z') / 1000;
    let page = 0;
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const callback = new URL(url).searchParams.get('jsonp');
      const rows = page < 2 ? [0, 1].map(i => [(start + (page * 2 + i) * 60) * 1000, 100, 101, 99, 100, 1]) : [];
      page++;
      return new Response(`${callback}(${JSON.stringify(rows)});`, { status: 200 });
    }));
    const source = await downloadSource('XAUUSD', '2026-11-18', '2026-11-18', undefined, new AbortController().signal, () => {});
    expect(source.bars).toHaveLength(4); expect(page).toBe(3); expect(source.profile.is_demo).toBe(false);
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 429 })));
    await expect(downloadSource('XAUUSD', '2026-11-18', '2026-11-18', undefined, new AbortController().signal, () => {})).rejects.toThrow('429');
    vi.unstubAllGlobals();
  });
});
