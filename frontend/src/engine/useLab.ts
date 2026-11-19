import { useEffect, useRef, useState } from 'react';
import type { Dashboard } from '../types';
import { DEFAULT_SETTINGS } from './contracts';
import type { PaperForecast, Progress, ScenarioInput, ScenarioResult, Settings, SourceProfile, StoredDataset } from './contracts';
import { hash, normalizeBars, parseCSV } from './data';
import { downloadSource } from './provider';
import { loadReference, loadPreparedReport } from './archive';
import { evaluatePaper } from './research';
import { appendOutcome, appendPaper, backupWorkspace, loadWorkspace, restoreWorkspace, saveRawImport, saveRun, saveSource } from './storage';
import type { SavedRun } from './storage';

export function useLab() {
  const [sources, setSources] = useState<StoredDataset[]>([]);
  const [reports, setReports] = useState<Record<string, Dashboard>>({});
  const [experiments, setExperiments] = useState<SavedRun[]>([]);
  const [paper, setPaper] = useState<PaperForecast[]>([]);
  const [settings, setSettings] = useState<Settings>({ ...DEFAULT_SETTINGS });
  const [activeId, setActiveId] = useState('');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<Progress>();
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const rejectRef = useRef<((e: Error) => void) | null>(null);
  const busyRef = useRef(false);
  const source = sources.find(s => s.id === activeId) ?? sources[0];
  const report = source ? reports[source.id] : undefined;

  async function reload() {
    const data = await loadWorkspace();
    setSources(data.sources); setReports(Object.fromEntries(data.reports.map(r => [r.source_id, r.report])));
    setExperiments(data.experiments.sort((a, b) => b.generated_at_utc.localeCompare(a.generated_at_utc)));
    setPaper(data.paper.sort((a, b) => b.issued_at_utc.localeCompare(a.issued_at_utc)));
    return data;
  }
  useEffect(() => {
    let cancelled = false;
    loadWorkspace().then(data => {
      if (cancelled) return;
      setSources(data.sources); setReports(Object.fromEntries(data.reports.map(r => [r.source_id, r.report])));
      setExperiments(data.experiments.sort((a, b) => b.generated_at_utc.localeCompare(a.generated_at_utc)));
      setPaper(data.paper.sort((a, b) => b.issued_at_utc.localeCompare(a.issued_at_utc)));
      setActiveId(localStorage.getItem('quant-lab-active-source') ?? data.sources[0]?.id ?? '');
      setReady(true);
    }).catch(e => { setError(`Не удалось открыть локальную базу браузера: ${String(e)}`); setReady(true); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => { if (activeId) localStorage.setItem('quant-lab-active-source', activeId); }, [activeId]);

  function worker<T>(task: 'research' | 'scenario' | 'paper', selected: StoredDataset, input?: ScenarioInput, minutes?: number): Promise<T> {
    return new Promise((resolve, reject) => {
      const instance = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
      workerRef.current = instance; rejectRef.current = reject;
      const finish = () => { instance.terminate(); if (workerRef.current === instance) { workerRef.current = null; rejectRef.current = null; } };
      instance.onmessage = event => {
        if (event.data.type === 'progress') setProgress(event.data.progress);
        else if (event.data.type === 'error') { finish(); reject(new Error(event.data.error)); }
        else { finish(); resolve(event.data.result as T); }
      };
      instance.onerror = event => { finish(); reject(new Error(event.message || 'Ошибка исследовательского процесса')); };
      instance.postMessage({ id: crypto.randomUUID(), task, source: selected, settings, input, minutes });
    });
  }
  async function guarded<T>(action: () => Promise<T>) {
    if (busyRef.current) return undefined;
    busyRef.current = true; setBusy(true); setError(''); setNotice('');
    try { return await action(); }
    catch (error) { setError(error instanceof Error ? error.message : String(error)); return undefined; }
    finally { busyRef.current = false; setBusy(false); setProgress(undefined); abortRef.current = null; }
  }
  function cancel() {
    abortRef.current?.abort(); workerRef.current?.terminate(); rejectRef.current?.(new Error('Расчёт отменён. Предыдущие результаты сохранены.'));
    workerRef.current = null; rejectRef.current = null;
  }
  function inRange(selected: StoredDataset, from?: string, to?: string): StoredDataset {
    if (!from || !to) return selected;
    const start = Date.parse(`${from}T00:00:00Z`) / 1000, end = Date.parse(`${to}T00:00:00Z`) / 1000 + 86400;
    return { ...selected, bars: selected.bars.filter(b => b.time >= start && b.time < end), requested_from_utc: new Date(start * 1000).toISOString(), requested_to_utc: new Date(end * 1000).toISOString() };
  }
  async function calculate(selected: StoredDataset, from?: string, to?: string) {
    const scoped = inRange(selected, from, to);
    const result = await worker<Dashboard>('research', scoped);
    const saved = await saveRun(scoped, result, settings);
    for (const forecast of paper.filter(f => f.dataset_id === selected.id && !f.outcome)) {
      const outcome = evaluatePaper(forecast, selected);
      if (outcome) await appendOutcome(forecast.forecast_id, outcome);
    }
    await reload();
    setActiveId(selected.id); setReports(old => ({ ...old, [selected.id]: saved }));
    setNotice(`Исследование завершено: ${scoped.bars.length.toLocaleString('ru-RU')} закрытых свечей. Результат сохранён в этом браузере.`);
    return saved;
  }
  function connect(instrument: 'XAUUSD' | 'NAS100', from: string, to: string) {
    return guarded(async () => {
      const controller = new AbortController(); abortRef.current = controller;
      const cached = sources.find(s => s.profile.instrument_id === instrument && s.profile.source === 'dukascopy_public');
      const downloaded = await downloadSource(instrument, from, to, cached, controller.signal, setProgress);
      if (controller.signal.aborted) throw new Error('Загрузка отменена');
      const merged = await saveSource(downloaded);
      setSources(old => [...old.filter(s => s.id !== merged.id), merged]); setActiveId(merged.id);
      return calculate(merged, from, to);
    });
  }
  function reference(instrument: 'XAUUSD' | 'NAS100') {
    return guarded(async () => {
      const controller = new AbortController(); abortRef.current = controller;
      const downloaded = await loadReference(instrument, controller.signal, setProgress);
      if (controller.signal.aborted) throw new Error('Загрузка отменена');
      const source = await saveSource(downloaded);
      setSources(old => [...old.filter(s => s.id !== source.id), source]); setActiveId(source.id);
      const prepared = JSON.stringify(settings) === JSON.stringify(DEFAULT_SETTINGS) ? await loadPreparedReport(instrument, source, controller.signal) : null;
      if (!prepared) return calculate(source);
      await saveRun(source, prepared, settings); await reload();
      setNotice(`Готово: ${source.bars.length.toLocaleString('ru-RU')} реальных M5-свечей за 2024–2025. Можно менять параметры и запускать свои расчёты.`);
      return prepared;
    });
  }
  function run(from: string, to: string) {
    if (!source) { setError('Сначала загрузи реальную историю из источника или CSV'); return Promise.resolve(undefined); }
    return guarded(() => calculate(source, from, to));
  }
  function importCSV(file: File, profile: SourceProfile) {
    return guarded(async () => {
      if (file.size > 50 * 1024 * 1024) throw new Error('CSV больше 50 MiB. Раздели экспорт на части.');
      const text = await file.text();
      const rawHash = await hash(text);
      await saveRawImport(rawHash, file.name, text, profile);
      const normalized = parseCSV(text, profile);
      if (!normalized.bars.length) throw new Error('В файле нет закрытых свечей');
      const id = (await hash(profile)).slice(0, 24);
      const item: StoredDataset = { id, profile, bars: normalized.bars, fetched_at_utc: new Date().toISOString(), requested_from_utc: new Date(normalized.bars[0].time * 1000).toISOString(), requested_to_utc: new Date((normalized.bars.at(-1)!.time + profile.timeframe_minutes * 60) * 1000).toISOString(), errors: [] };
      const existing = sources.find(s => s.id === id);
      const merged = await saveSource({ ...item, bars: normalizeBars([...(existing?.bars ?? []), ...item.bars], profile).bars });
      setActiveId(id); setSources(old => [...old.filter(s => s.id !== id), merged]);
      await calculate(merged);
      return { from: new Date(merged.bars[0].time * 1000).toISOString().slice(0, 10), to: merged.bars.at(-1) ? new Date(merged.bars.at(-1)!.time * 1000).toISOString().slice(0, 10) : '', duplicates: normalized.duplicates, partial: normalized.partial };
    });
  }
  async function scenario(input: ScenarioInput): Promise<ScenarioResult | undefined> {
    if (!source) { setError('Сначала открой готовую историю или импортируй свечи'); return undefined; }
    return guarded(() => worker<ScenarioResult>('scenario', source, input));
  }
  async function issue(minutes: number) {
    if (!source) return undefined;
    return guarded(async () => {
      const result = await worker<PaperForecast>('paper', source, undefined, minutes);
      const saved = await appendPaper(result); await reload();
      setNotice(`Прогноз зафиксирован до ${saved.horizon_start_utc}. Границы этой записи больше не меняются.`);
      return saved;
    });
  }
  async function restore(file: File) {
    return guarded(async () => { await restoreWorkspace(await file.text()); await reload(); setNotice('Резервная копия восстановлена. Существующие прогнозы не перезаписаны.'); });
  }
  return { sources, source, reports, report, experiments, paper, settings, setSettings, activeId, setActiveId, ready, busy, progress, error, setError, notice, connect, reference, run, importCSV, scenario, issue, restore, cancel, backup: backupWorkspace };
}
export type Lab = ReturnType<typeof useLab>;
