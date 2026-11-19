import manifest from './archive-manifest.json';
import type { Progress, RawBar, SourceProfile, StoredDataset } from './contracts';
import type { Dashboard } from '../types';
import { hash, normalizeBars } from './data';

export const ARCHIVE_PERIOD = { from: '2024-01-01', to: '2025-12-31' };
export const ARCHIVE_PROFILES: Record<'XAUUSD' | 'NAS100', SourceProfile> = {
  XAUUSD: {
    instrument_id: 'XAUUSD', source: 'evtl_archive_2024_2025_v1', source_symbol: 'EVTL:XAUUSD', asset_class: 'spot',
    timeframe_minutes: 5, timestamp_timezone: 'UTC', timestamp_unit: 's', price_precision: 3, tick_size: .001,
    available_volume_type: 'provider', data_license: 'EV Trading Labs: free use with attribution, https://evtradelabs.com/data; Dukascopy-derived Bid archive, M5 2024–2025', publish_allowed: true, is_demo: false,
    calendar: { timezone: 'UTC', verified: false, sessions: [{ weekdays: [0, 1, 2, 3, 4, 5, 6], open_minute: 0, close_minute: 1440 }], closed_dates: [] },
  },
  NAS100: {
    instrument_id: 'NAS100', source: 'evtl_archive_2024_2025_v1', source_symbol: 'EVTL:NQ', asset_class: 'cfd',
    timeframe_minutes: 5, timestamp_timezone: 'UTC', timestamp_unit: 's', price_precision: 3, tick_size: .001,
    available_volume_type: 'provider', data_license: 'EV Trading Labs: free use with attribution, https://evtradelabs.com/data; Dukascopy-derived Nasdaq 100 dataset NQ, not a CME NQ future; Bid M5 2024–2025', publish_allowed: true, is_demo: false,
    calendar: { timezone: 'UTC', verified: false, sessions: [{ weekdays: [0, 1, 2, 3, 4, 5, 6], open_minute: 0, close_minute: 1440 }], closed_dates: [] },
  },
};

export function parseArchiveJSON(text: string): RawBar[] {
  const rows: unknown = JSON.parse(text);
  if (!Array.isArray(rows)) throw new Error('Архив источника не содержит массив OHLC');
  return rows.map(row => ({ time: Number(row.ts), open: Number(row.o), high: Number(row.h), low: Number(row.l), close: Number(row.c), volume: row.v == null ? null : Number(row.v) }));
}

export async function archiveDataset(instrument: 'XAUUSD' | 'NAS100', bars: RawBar[]): Promise<StoredDataset> {
  const profile = structuredClone(ARCHIVE_PROFILES[instrument]);
  return { id: (await hash(profile)).slice(0, 24), profile, bars: normalizeBars(bars, profile).bars, fetched_at_utc: new Date().toISOString(), requested_from_utc: `${ARCHIVE_PERIOD.from}T00:00:00.000Z`, requested_to_utc: '2026-01-01T00:00:00.000Z', errors: [] };
}

export async function loadReference(instrument: 'XAUUSD' | 'NAS100', signal: AbortSignal, onProgress: (p: Progress) => void) {
  const files = manifest[instrument];
  const bars: RawBar[] = [];
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    onProgress({ stage: 'download', current: i, total: files.length, message: `Загружаю настоящий архив ${file.original_name}` });
    const response = await fetch(`${import.meta.env.BASE_URL}quotes/${file.file}`, { signal, credentials: 'omit', cache: 'force-cache' });
    if (!response.ok) throw new Error(`Архив ${file.original_name}: HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const checksum = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
    if (checksum !== file.sha256) throw new Error('Контрольная сумма архива не совпала. Расчёт остановлен.');
    const text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
    const rows = parseArchiveJSON(text);
    if (rows.length !== file.rows) throw new Error('Число свечей не совпало с паспортом источника');
    bars.push(...rows);
  }
  return archiveDataset(instrument, bars);
}

export async function loadPreparedReport(instrument: 'XAUUSD' | 'NAS100', source: StoredDataset, signal: AbortSignal): Promise<Dashboard | null> {
  const response = await fetch(`${import.meta.env.BASE_URL}quotes/ready-${instrument}.json`, { signal, credentials: 'omit' });
  if (!response.ok) return null;
  const report = await response.json() as Dashboard;
  if (report.schema_version !== '2.1' || report.datasets?.[0]?.dataset_hash !== await hash({ profile: source.profile, bars: source.bars })) return null;
  return report;
}
