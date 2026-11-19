import type { Progress, StoredDataset } from './contracts';
import { hash, normalizeBars, parseProviderResponse, PROVIDER_PROFILES, sourceURL } from './data';

function jsonp(url: string, callback: string, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    const frame = document.createElement('iframe');
    const channel = crypto.randomUUID();
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.contentWindow || event.data?.channel !== channel) return;
      cleanup();
      if (event.data.error) reject(new Error('Публичный источник не ответил на запрос котировок'));
      else resolve(`${callback}(${JSON.stringify(event.data.value)});`);
    };
    const cleanup = () => { clearTimeout(timeout); frame.remove(); window.removeEventListener('message', receive); signal.removeEventListener('abort', abort); };
    const abort = () => { cleanup(); reject(new Error('Загрузка отменена')); };
    const timeout = setTimeout(() => { cleanup(); reject(new Error('Поставщик не ответил за 20 секунд. Кэш и загруженные CSV сохранены.')); }, 20000);
    frame.hidden = true;
    frame.setAttribute('sandbox', 'allow-scripts');
    frame.srcdoc = `<!doctype html><meta charset="utf-8"><script>window[${JSON.stringify(callback)}]=function(value){parent.postMessage({channel:${JSON.stringify(channel)},value:value},'*')};var s=document.createElement('script');s.src=${JSON.stringify(url)};s.referrerPolicy='strict-origin';s.onerror=function(){parent.postMessage({channel:${JSON.stringify(channel)},error:true},'*')};document.head.append(s);</script>`;
    window.addEventListener('message', receive);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort(); else document.body.append(frame);
  });
}

export async function fetchProviderText(url: string, callback: string, signal: AbortSignal) {
  try {
    const response = await fetch(url, { signal, cache: 'no-store', credentials: 'omit' });
    if (!response.ok) throw new Error(response.status === 429 ? 'Источник ограничил запросы (HTTP 429). Автоматические повторы остановлены.' : `Источник ответил HTTP ${response.status}`);
    const text = await response.text();
    if (!text.trim()) throw new Error(`Источник вернул пустой ответ HTTP ${response.status}`);
    return text;
  } catch (error) {
    if (signal.aborted) throw new Error('Загрузка отменена');
    // The provider intentionally supports JSONP for its public chart API.
    // Never switch protocols after an observed HTTP rejection/rate limit.
    if (!(error instanceof TypeError)) throw error;
    return jsonp(url, callback, signal);
  }
}

export async function downloadSource(instrument: 'XAUUSD' | 'NAS100', from: string, to: string, existing: StoredDataset | undefined, signal: AbortSignal, onProgress: (progress: Progress) => void): Promise<StoredDataset> {
  const profile = PROVIDER_PROFILES[instrument];
  const start = Date.parse(`${from}T00:00:00Z`) / 1000;
  const end = Math.min(Date.parse(`${to}T00:00:00Z`) / 1000 + 86400, Date.now() / 1000);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || end - start > 366 * 86400) throw new Error('Выбери корректный период до 366 дней');
  const id = (await hash(profile)).slice(0, 24);
  const collected = existing?.id === id ? existing.bars.filter(b => b.time >= start && b.time < end) : [];
  const coveredUntil = collected.at(-1)?.time;
  let cursor = coveredUntil && collected[0].time <= start + 4 * 86400 ? Math.max(start, coveredUntil - 3600) : start;
  let batch = 0;
  const maximumBatches = Math.min(200, Math.ceil((end - cursor) / (60 * 1000)) + 3);
  while (cursor < end) {
    if (signal.aborted) throw new Error('Загрузка отменена');
    if (batch >= maximumBatches) throw new Error('Источник не завершил диапазон в ожидаемом числе пакетов');
    const callback = `quantlab_${crypto.randomUUID().replaceAll('-', '')}`;
    onProgress({ stage: 'download', current: Math.max(0, cursor - start), total: end - start, message: `${profile.source_symbol}: пакет ${batch + 1}, ${new Date(cursor * 1000).toISOString().slice(0, 16)} UTC` });
    const text = await fetchProviderText(sourceURL(profile, cursor, callback), callback, signal);
    const rows = parseProviderResponse(text, callback);
    if (!rows.length) break;
    const selected = rows.filter(b => b.time >= start && b.time < end);
    collected.push(...selected);
    const last = rows.at(-1)!.time;
    if (last < cursor) throw new Error('Время источника не продвигается. Загрузка остановлена.');
    cursor = last + 60; batch++;
    if (last >= end - 60 || rows[0].time >= end) break;
    await new Promise<void>(resolve => setTimeout(resolve, 250));
  }
  const normalized = normalizeBars(collected, profile);
  if (!normalized.bars.length) throw new Error('Источник не вернул закрытых свечей за выбранный период. Никакие демоданные не подставлены.');
  return { id, profile: structuredClone(profile), bars: normalized.bars, fetched_at_utc: new Date().toISOString(), requested_from_utc: new Date(start * 1000).toISOString(), requested_to_utc: new Date(end * 1000).toISOString(), errors: [] };
}
