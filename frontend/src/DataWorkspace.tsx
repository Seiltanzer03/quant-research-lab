import { useRef, useState } from 'react';
import type { Lab } from './engine/useLab';
import type { Instrument, SourceProfile } from './engine/contracts';
import { PROVIDER_PROFILES } from './engine/data';
import { QualitySummary } from './ReportPanels';
import { Panel, Badge, Empty } from './components/ui';
import { Icon } from './components/Icon';
import { download, number, stamp } from './utils';

export function DataWorkspace({ lab, zone, onImported }: { lab: Lab; zone: string; onImported: (from: string, to: string) => void }) {
  const [symbol, setSymbol] = useState('');
  const [instrument, setInstrument] = useState<Instrument>('XAUUSD');
  const [asset, setAsset] = useState<'spot' | 'cfd' | 'index' | 'futures'>('cfd');
  const [timeframe, setTimeframe] = useState<1 | 15 | 60>(1);
  const [timestampUnit, setTimestampUnit] = useState<'s' | 'ms'>('s');
  const [timezone, setTimezone] = useState('UTC');
  const [file, setFile] = useState<File>();
  const [fileMessage, setFileMessage] = useState('');
  const fileInput = useRef<HTMLInputElement>(null), restoreInput = useRef<HTMLInputElement>(null);
  const dataset = lab.report?.datasets[0];
  async function runImport() {
    if (!file || !symbol.includes(':')) { setFileMessage('Выбери CSV и укажи точный PROVIDER:SYMBOL'); return; }
    const preset = PROVIDER_PROFILES[instrument] ?? PROVIDER_PROFILES.XAUUSD;
    const profile: SourceProfile = { ...structuredClone(preset), instrument_id: instrument, source: 'user_csv', source_symbol: symbol.trim(), asset_class: asset, timeframe_minutes: timeframe, timestamp_unit: timestampUnit, timestamp_timezone: timezone, available_volume_type: 'csv_unspecified', data_license: 'User CSV for personal local analysis; no public distribution', calendar: { timezone: 'UTC', verified: false, sessions: [{ weekdays: [0, 1, 2, 3, 4, 5, 6], open_minute: 0, close_minute: 1440 }], closed_dates: [] } };
    const result = await lab.importCSV(file, profile);
    if (result) { onImported(result.from, result.to); setFileMessage(`Импорт завершён. Повторы: ${result.duplicates}; незакрытые строки исключены: ${result.partial}. Расчёт уже выполнен.`); }
  }
  async function backup() { download(`quant-lab-backup-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(await lab.backup())); }
  return <>
    <Panel title="Мои реальные источники" subtitle="Котировки, отчёты и журнал сохраняются в IndexedDB этого браузера." action={<button className="button secondary" onClick={backup}><Icon name="download" />Резервная копия</button>}>
      {lab.sources.length ? <div className="table-scroll"><table><thead><tr><th>Инструмент / источник</th><th>Свечей</th><th>Разрешение</th><th>Последнее закрытие</th><th>Открыть</th></tr></thead><tbody>{lab.sources.map(s => <tr key={s.id}><td><strong>{s.profile.instrument_id}</strong><small>{s.profile.source_symbol}</small></td><td>{number(s.bars.length, 0)}</td><td>M{s.profile.timeframe_minutes}</td><td>{stamp(new Date((s.bars.at(-1)!.time + s.profile.timeframe_minutes * 60) * 1000).toISOString(), zone)}</td><td><button className="icon-button" aria-label={`Выбрать ${s.profile.source_symbol}`} onClick={() => lab.setActiveId(s.id)}><Icon name="arrow" /></button></td></tr>)}</tbody></table></div> : <Empty>История ещё не получена. Подключи Dukascopy в панели сверху либо импортируй CSV ниже. Демо не используется.</Empty>}
      <div className="button-row panel-actions"><input type="file" accept=".json" className="sr-only" ref={restoreInput} onChange={e => { const f = e.target.files?.[0]; if (f) void lab.restore(f); }} /><button className="button secondary" disabled={lab.busy} onClick={() => restoreInput.current?.click()}><Icon name="upload" />Восстановить копию</button><span className="caption">Скопируй резервную копию для переноса на другой компьютер или браузер.</span></div>
    </Panel>
    <Panel title="Импортировать CSV и выполнить исследование" subtitle="Работает на опубликованном сайте. Python и коммиты в GitHub для импорта не требуются.">
      <div className="import-grid"><div><input ref={fileInput} className="sr-only" type="file" accept=".csv,text/csv" onChange={e => { setFile(e.target.files?.[0]); setFileMessage(''); }} /><button className="dropzone" disabled={lab.busy} onClick={() => fileInput.current?.click()}><span className="upload-icon"><Icon name="upload" size={26} /></span><strong>{file?.name ?? 'Выбрать CSV из TradingView / брокера'}</strong><small>Time, Open, High, Low, Close · до 50 MiB</small><span className="button secondary">Открыть файл</span></button></div>
      <div className="import-form"><div className="form-row"><label>Инструмент<select aria-label="Инструмент CSV" value={instrument} onChange={e => { const value = e.target.value as Instrument; setInstrument(value); if (value.endsWith('_F')) setAsset('futures'); }}>{['XAUUSD', 'NAS100', 'SPX500', 'XAGUSD', 'GC_F', 'NQ_F'].map(i => <option key={i}>{i}</option>)}</select></label><label>Тип инструмента<select aria-label="Тип инструмента CSV" value={asset} onChange={e => setAsset(e.target.value as typeof asset)}><option value="cfd">CFD</option><option value="spot">Spot</option><option value="index">Индекс</option><option value="futures">Фьючерс / непрерывная серия</option></select></label></div>
        <label>Точный символ источника<input aria-label="Символ CSV" placeholder="PROVIDER:SYMBOL" value={symbol} onChange={e => setSymbol(e.target.value)} /></label>
        <div className="form-row"><label>Таймфрейм CSV<select aria-label="Таймфрейм CSV" value={timeframe} onChange={e => setTimeframe(Number(e.target.value) as typeof timeframe)}><option value={1}>M1</option><option value={15}>M15</option><option value={60}>H1</option></select></label><label>Единицы Unix-времени<select value={timestampUnit} onChange={e => setTimestampUnit(e.target.value as 's' | 'ms')}><option value="s">Секунды</option><option value="ms">Миллисекунды</option></select></label></div>
        <label>Часовой пояс CSV<input value={timezone} onChange={e => setTimezone(e.target.value)} placeholder="UTC" /></label>
        <button className="button primary" disabled={lab.busy || !file || !symbol.includes(':')} onClick={runImport}><Icon name="lab" />Импортировать и посчитать</button>
      </div></div>
      {fileMessage && <div className="notice" role="status">{fileMessage}</div>}
      <div className="subtle-note">Файл остаётся в твоём браузере. Для времени без UTC-offset используй UTC или Unix timestamps. Календарь CSV не подтверждён: используются только полные наблюдаемые UTC-окна. Пустые слоты включают выходные/перерывы и не объявляются ошибками поставщика. CSV не получает допуск к оперативным прогнозам.</div>
    </Panel>
    {dataset && <div className="bottom-grid"><Panel title="Качество исследуемого участка" subtitle={dataset.profile.source_symbol}><QualitySummary dataset={dataset} /><dl className="details"><dt>Начало</dt><dd>{stamp(dataset.quality.first_bar_utc, zone)}</dd><dt>Последняя закрытая свеча</dt><dd>{stamp(dataset.quality.last_bar_close_utc, zone)}</dd><dt>Пропуски</dt><dd>{dataset.quality.missing_bars}</dd><dt>Вне календаря</dt><dd>{dataset.quality.off_session_bars}</dd></dl><div className="gate-row">{dataset.quality.flags.map(f => <Badge key={f} tone="amber">{f}</Badge>)}</div></Panel><Panel title="Происхождение и версия данных"><dl className="details"><dt>Источник</dt><dd>{dataset.profile.source}</dd><dt>Символ</dt><dd>{dataset.profile.source_symbol}</dd><dt>Календарь</dt><dd>{dataset.profile.calendar.timezone}</dd><dt>Календарь проверен</dt><dd>{dataset.profile.calendar.verified ? 'Недельные сессии; праздники отдельно' : 'Нет'}</dd><dt>Использование</dt><dd>Личное, без публикации котировок</dd><dt>SHA-256</dt><dd className="hash">{dataset.dataset_hash}</dd></dl></Panel></div>}
  </>;
}
