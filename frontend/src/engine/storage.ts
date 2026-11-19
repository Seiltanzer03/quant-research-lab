import { openDB } from 'idb';
import type { Dashboard } from '../types';
import type { PaperForecast, Settings, StoredDataset } from './contracts';
import { normalizeBars } from './data';

const database = () => openDB('quant-lab-personal-v2', 1, { upgrade(db) {
  db.createObjectStore('sources', { keyPath: 'id' });
  db.createObjectStore('reports', { keyPath: 'id' });
  db.createObjectStore('experiments', { keyPath: 'id' });
  db.createObjectStore('paper', { keyPath: 'forecast_id' });
  db.createObjectStore('outcomes', { keyPath: 'forecast_id' });
  db.createObjectStore('raw_imports', { keyPath: 'id' });
} });
export type SavedRun = { id: string; source_id: string; generated_at_utc: string; settings: Settings; report: Dashboard };
export async function loadWorkspace() {
  const db = await database();
  const sources = await db.getAll('sources') as StoredDataset[];
  const reports = await db.getAll('reports') as SavedRun[];
  const experiments = await db.getAll('experiments') as SavedRun[];
  const paper = await db.getAll('paper') as PaperForecast[];
  const outcomes = await db.getAll('outcomes');
  return { sources, reports, experiments, paper: paper.map(f => ({ ...f, ...(outcomes.find(o => o.forecast_id === f.forecast_id) ? { outcome: outcomes.find(o => o.forecast_id === f.forecast_id).outcome } : {}) })) };
}
export async function saveSource(source: StoredDataset) {
  const db = await database();
  const old = await db.get('sources', source.id) as StoredDataset | undefined;
  const merged = old ? { ...source, bars: normalizeBars([...old.bars, ...source.bars], source.profile).bars } : source;
  await db.put('sources', merged);
  return merged;
}
export async function saveRun(source: StoredDataset, report: Dashboard, settings: Settings) {
  const db = await database();
  const id = report.datasets[0].dataset_hash + '/' + report.schema_version + '/' + report.git_sha + '/' + JSON.stringify(settings);
  const existing = await db.get('experiments', id) as SavedRun | undefined;
  const run = existing ?? { id, source_id: source.id, generated_at_utc: report.generated_at_utc, settings: { ...settings }, report };
  const transaction = db.transaction(['reports', 'experiments'], 'readwrite');
  if (!existing) await transaction.objectStore('experiments').add(run);
  await transaction.objectStore('reports').put({ ...run, id: source.id });
  await transaction.done;
  return run.report;
}
export async function saveRawImport(id: string, fileName: string, text: string, profile: StoredDataset['profile']) {
  const db = await database();
  if (!await db.get('raw_imports', id)) await db.add('raw_imports', { id, fileName, text, profile, received_at_utc: new Date().toISOString() });
}
export async function appendPaper(forecast: PaperForecast) {
  const db = await database();
  const transaction = db.transaction('paper', 'readwrite');
  const old = await transaction.store.get(forecast.forecast_id) as PaperForecast | undefined;
  if (!old) {
    const availableAt = new Date(Date.now()).toISOString();
    if (Date.parse(availableAt) >= Date.parse(forecast.horizon_start_utc)) throw new Error('Сохранение завершилось после начала окна: поздний прогноз не записан');
    forecast = { ...forecast, available_at_utc: availableAt };
    await transaction.store.add(forecast);
  }
  await transaction.done;
  return old ?? forecast;
}
export async function appendOutcome(forecastId: string, outcome: PaperForecast['outcome']) {
  const db = await database();
  const transaction = db.transaction('outcomes', 'readwrite');
  if (!await transaction.store.get(forecastId)) await transaction.store.add({ forecast_id: forecastId, outcome });
  await transaction.done;
}
export async function backupWorkspace() {
  const db = await database();
  const stores = ['sources', 'reports', 'experiments', 'paper', 'outcomes', 'raw_imports'];
  const result: Record<string, unknown> = { format: 'quant-lab-personal-v2', created_at_utc: new Date().toISOString() };
  for (const name of stores) result[name] = await db.getAll(name);
  return result;
}
export async function restoreWorkspace(text: string) {
  const input = JSON.parse(text);
  if (input.format !== 'quant-lab-personal-v2' || !Array.isArray(input.sources)) throw new Error('Это не резервная копия Quant Lab v0.2');
  for (const source of input.sources as StoredDataset[]) {
    if (source.profile.is_demo !== false || !source.profile.source_symbol.includes(':')) throw new Error('Неподтверждённый профиль в резервной копии');
    source.bars = normalizeBars(source.bars, source.profile).bars;
    await saveSource(source);
  }
  const db = await database();
  for (const name of ['reports', 'experiments', 'paper', 'outcomes', 'raw_imports']) {
    if (!Array.isArray(input[name])) continue;
    const transaction = db.transaction(name, 'readwrite');
    for (const row of input[name]) {
      const key = ['paper', 'outcomes'].includes(name) ? row.forecast_id : row.id;
      if (!await transaction.store.get(key)) await transaction.store.add(row);
    }
    await transaction.done;
  }
}
