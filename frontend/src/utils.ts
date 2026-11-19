import Papa from 'papaparse';

export const pct = (value: number | null | undefined, digits = 1) => value == null ? '—' : `${(value * 100).toFixed(digits)}%`;
export const number = (value: number | null | undefined, digits = 2) => value == null ? '—' : value.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const stamp = (value?: string, zone = 'Europe/Moscow') => value ? new Intl.DateTimeFormat('ru-RU', { timeZone: zone, year: 'numeric', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—';

export function riskReward(direction: string, entry: number, tp: number, sl: number): number | null {
  if (![entry, tp, sl].every(v => Number.isFinite(v) && v > 0)) return null;
  if (direction === 'long' ? !(sl < entry && entry < tp) : !(tp < entry && entry < sl)) return null;
  return Math.abs(tp - entry) / Math.abs(entry - sl);
}

export function inspectCSV(text: string) {
  const parsed = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: 'greedy', transformHeader: h => h.replace(/^\uFEFF/, '').trim().toLowerCase() });
  const fields = parsed.meta.fields ?? [];
  const missing = ['time', 'open', 'high', 'low', 'close'].filter(k => !fields.includes(k));
  let invalid = 0;
  const seen = new Set<string>();
  let duplicates = 0;
  for (const row of parsed.data) {
    const values = ['open', 'high', 'low', 'close'].map(k => Number(row[k]));
    const [o, h, l, c] = values;
    const numericTime = row.time != null && row.time.trim() !== '' && Number.isFinite(Number(row.time));
    const validTime = numericTime || Number.isFinite(Date.parse(row.time));
    if (!validTime || !values.every(v => Number.isFinite(v) && v > 0) || h < Math.max(o, c, l) || l > Math.min(o, c, h)) invalid++;
    if (seen.has(row.time)) duplicates++;
    seen.add(row.time);
  }
  return { rows: parsed.data.length, fields, invalid, duplicates, errors: parsed.errors.map(e => e.message), missing, preview: parsed.data.slice(0, 5) };
}

export function download(name: string, text: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
