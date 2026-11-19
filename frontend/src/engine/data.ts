import Papa from 'papaparse';
import type { RawBar, SourceProfile, StoredDataset } from './contracts';

export const PROVIDER_PROFILES: Record<string, SourceProfile> = {
  XAUUSD: {
    instrument_id: 'XAUUSD', source: 'dukascopy_public', source_symbol: 'DUKASCOPY:XAU/USD', asset_class: 'spot',
    timeframe_minutes: 1, timestamp_timezone: 'UTC', timestamp_unit: 's', price_precision: 3, tick_size: 0.001,
    available_volume_type: 'provider', data_license: 'Dukascopy™ personal non-commercial use; no public redistribution', publish_allowed: false, is_demo: false,
    calendar: { timezone: 'America/New_York', verified: true, sessions: [{ weekdays: [0, 1, 2, 3, 6], open_minute: 1080, close_minute: 1020 }], closed_dates: [] },
  },
  NAS100: {
    instrument_id: 'NAS100', source: 'dukascopy_public', source_symbol: 'DUKASCOPY:USATECH.IDX/USD', asset_class: 'cfd',
    timeframe_minutes: 1, timestamp_timezone: 'UTC', timestamp_unit: 's', price_precision: 3, tick_size: 0.001,
    available_volume_type: 'provider', data_license: 'Dukascopy™ personal non-commercial use; no public redistribution', publish_allowed: false, is_demo: false,
    calendar: { timezone: 'America/Chicago', verified: true, sessions: [{ weekdays: [0, 1, 2, 3, 6], open_minute: 1020, close_minute: 915 }], closed_dates: [] },
  },
};

export async function hash(value: unknown) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
}

const formatters = new Map<string, Intl.DateTimeFormat>();
const offsets = new Map<string, number>();
export function localParts(time: number, zone: string) {
  const hour = Math.floor(time / 3600) * 3600;
  const key = `${zone}/${hour}`;
  let offset = offsets.get(key);
  if (offset == null) {
    let formatter = formatters.get(zone);
    if (!formatter) {
      formatter = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
      formatters.set(zone, formatter);
    }
    const parts = Object.fromEntries(formatter.formatToParts(hour * 1000).map(x => [x.type, x.value]));
    offset = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour), Number(parts.minute)) / 1000 - hour;
    offsets.set(key, offset);
  }
  const local = new Date((time + offset) * 1000);
  return { weekday: (local.getUTCDay() + 6) % 7, minute: local.getUTCHours() * 60 + local.getUTCMinutes(), date: local.toISOString().slice(0, 10) };
}

export function inSession(time: number, profile: SourceProfile) {
  const p = localParts(time, profile.calendar.timezone);
  if (profile.calendar.closed_dates.includes(p.date)) return false;
  const sessions = profile.calendar.overrides?.[p.date] ?? profile.calendar.sessions;
  return sessions.some(s => s.close_minute > s.open_minute
    ? s.weekdays.includes(p.weekday) && p.minute >= s.open_minute && p.minute < s.close_minute
    : (s.weekdays.includes(p.weekday) && p.minute >= s.open_minute) || (s.weekdays.includes((p.weekday + 6) % 7) && p.minute < s.close_minute));
}

export function normalizeBars(bars: RawBar[], profile: SourceProfile, now = Date.now() / 1000) {
  const rows = new Map<number, RawBar>();
  let duplicates = 0, partial = 0;
  const step = profile.timeframe_minutes * 60;
  for (const b of bars) {
    if (![b.time, b.open, b.high, b.low, b.close].every(Number.isFinite) || b.time % step !== 0 || Math.min(b.open, b.high, b.low, b.close) <= 0 || b.high < Math.max(b.open, b.close, b.low) || b.low > Math.min(b.open, b.close, b.high)) throw new Error(`Некорректная свеча ${b.time}. Импорт отклонён.`);
    if (b.volume != null && (!Number.isFinite(b.volume) || b.volume < 0)) throw new Error(`Некорректный объём ${b.time}`);
    if (b.time + step > now) { partial++; continue; }
    const old = rows.get(b.time);
    if (old) {
      if (old.open !== b.open || old.high !== b.high || old.low !== b.low || old.close !== b.close || old.volume !== b.volume) throw new Error(`Конфликт двух версий свечи ${new Date(b.time * 1000).toISOString()}. История не изменена.`);
      duplicates++;
    } else rows.set(b.time, b);
  }
  return { bars: [...rows.values()].sort((a, b) => a.time - b.time), duplicates, partial };
}

export function parseCSV(text: string, profile: SourceProfile) {
  new Intl.DateTimeFormat('en', { timeZone: profile.timestamp_timezone }).format();
  const parsed = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: 'greedy', transformHeader: h => h.replace(/^\uFEFF/, '').trim().toLowerCase() });
  if (parsed.errors.length) throw new Error(`CSV: ${parsed.errors[0].message}`);
  const fields = parsed.meta.fields ?? [];
  const timeField = ['time', 'timestamp', 'date', 'datetime'].find(f => fields.includes(f));
  if (!timeField || !['open', 'high', 'low', 'close'].every(f => fields.includes(f))) throw new Error('Нужны time/timestamp/date, open, high, low, close. Регистр заголовков не важен.');
  const bars = parsed.data.map(row => {
    const rawTime = row[timeField].trim();
    let time: number;
    if (/^\d+(\.\d+)?$/.test(rawTime)) time = Number(rawTime) / (profile.timestamp_unit === 'ms' ? 1000 : 1);
    else {
      // A naïve local clock is ambiguous across DST. UTC can be made explicit safely.
      const explicit = /([zZ]|[+-]\d\d:?\d\d)$/.test(rawTime);
      if (!explicit && profile.timestamp_timezone !== 'UTC') throw new Error('Для локального времени без UTC-offset экспортируй UTC/Unix timestamps. Неоднозначные DST-метки не угадываются.');
      time = Date.parse(explicit ? rawTime : `${rawTime.replace(' ', 'T')}Z`) / 1000;
    }
    const volume = row.volume?.trim();
    return { time, open: Number(row.open), high: Number(row.high), low: Number(row.low), close: Number(row.close), volume: volume ? Number(volume) : null };
  });
  return normalizeBars(bars, profile);
}

export function quality(source: StoredDataset, now = Date.now() / 1000) {
  const { bars, profile } = source;
  if (!bars.length) throw new Error('Нет закрытых свечей для исследования');
  const start = bars[0].time, end = bars.at(-1)!.time;
  const actual = new Set(bars.map(b => b.time));
  let expected = 0, found = 0, missing = 0, off = 0;
  const examples: string[] = [];
  for (let t = start; t <= end; t += profile.timeframe_minutes * 60) {
    if (!inSession(t, profile)) { if (actual.has(t)) off++; continue; }
    expected++;
    if (actual.has(t)) found++;
    else { missing++; if (examples.length < 20) examples.push(new Date(t * 1000).toISOString()); }
  }
  const age = Math.max(0, (now - end - profile.timeframe_minutes * 60) / 60);
  const flags = [...(!profile.calendar.verified ? ['CALENDAR_UNVERIFIED'] : []), ...(missing ? ['MISSING_BARS'] : []), ...(off ? ['OUTSIDE_SESSION'] : []), ...(age > 5 ? ['DATA_STALE'] : []), ...(source.errors.length ? ['SOURCE_ERRORS'] : [])];
  return { status: flags[0] ?? 'REAL_DATA', flags, rows: bars.length, coverage: expected ? found / expected : null, missing_bars: missing, missing_examples: examples, off_session_bars: off, first_bar_utc: new Date(start * 1000).toISOString(), last_bar_close_utc: new Date((end + profile.timeframe_minutes * 60) * 1000).toISOString(), age_minutes: age, history_completeness: 'OBSERVED_SPAN_ONLY', expected_bars: expected };
}

export function aggregateBars(bars: RawBar[], profile: SourceProfile, minutes: number) {
  const size = minutes * 60, sourceStep = profile.timeframe_minutes * 60;
  if (minutes < profile.timeframe_minutes || minutes % profile.timeframe_minutes) return { bars: [] as RawBar[], incomplete: 0 };
  const buckets = new Map<number, RawBar[]>();
  for (const bar of bars) {
    const time = Math.floor(bar.time / size) * size;
    const bucket = buckets.get(time) ?? []; bucket.push(bar); buckets.set(time, bucket);
  }
  let incomplete = 0;
  const result: RawBar[] = [];
  for (const [time, group] of buckets) {
    if (group.length !== size / sourceStep || group[0].time !== time || group.at(-1)!.time !== time + size - sourceStep || !group.every(b => inSession(b.time, profile))) { incomplete++; continue; }
    const volumes = group.flatMap(b => b.volume == null ? [] : [b.volume]);
    result.push({ time, open: group[0].open, high: Math.max(...group.map(b => b.high)), low: Math.min(...group.map(b => b.low)), close: group.at(-1)!.close, volume: volumes.length ? volumes.reduce((a, b) => a + b, 0) : null });
  }
  return { bars: result, incomplete };
}

export function parseProviderResponse(text: string, callback: string): RawBar[] {
  const prefix = `${callback}(`;
  const clean = text.trim();
  if (!clean.startsWith(prefix) || !/\);?$/.test(clean)) throw new Error('Поставщик вернул неожиданный ответ; котировки не подменяются.');
  const raw: unknown = JSON.parse(clean.slice(prefix.length).replace(/\);?$/, ''));
  if (!Array.isArray(raw)) throw new Error('Поставщик не вернул массив свечей');
  return raw.map((row: unknown) => {
    if (!Array.isArray(row) || row.length < 6) throw new Error('Неверный формат OHLC источника');
    return { time: Number(row[0]) / 1000, open: Number(row[1]), high: Number(row[2]), low: Number(row[3]), close: Number(row[4]), volume: row[5] == null ? null : Number(row[5]) };
  });
}

export function sourceURL(profile: SourceProfile, from: number, callback: string, limit = 30000) {
  if (profile.source !== 'dukascopy_public' || !Object.values(PROVIDER_PROFILES).some(p => p.source_symbol === profile.source_symbol)) throw new Error('Автозагрузка доступна для подтверждённых профилей Dukascopy');
  const url = new URL('https://freeserv.dukascopy.com/2.0/index.php');
  const params = { path: 'chart/json3', splits: 'true', stocks: 'true', time_direction: 'N', jsonp: callback, last_update: String(Math.floor(from * 1000)), offer_side: 'B', instrument: profile.source_symbol.slice('DUKASCOPY:'.length), interval: '1MIN', limit: String(limit) };
  url.search = new URLSearchParams(params).toString();
  return url.toString();
}
