import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { Dashboard, Dataset, Forecast, Horizon } from './types';
import { Icon } from './components/Icon';
import { PriceChart } from './components/PriceChart';
import { download, inspectCSV, number, pct, riskReward, stamp } from './utils';
import './styles.css';

const REPO = 'https://github.com/Seiltanzer03/quant-research-lab';
const WORKFLOW = `${REPO}/actions/workflows/research.yml`;
type Page = 'market' | 'research' | 'history' | 'data' | 'modules';
const nav: { id: Page; label: string; icon: string }[] = [
  { id: 'market', label: 'Рынок и диапазоны', icon: 'market' },
  { id: 'research', label: 'Исследования', icon: 'lab' },
  { id: 'history', label: 'История прогнозов', icon: 'history' },
  { id: 'data', label: 'Данные и контроль', icon: 'data' },
  { id: 'modules', label: 'Модули', icon: 'modules' },
];

function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Panel({ title, subtitle, action, children, className = '' }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}
function Empty({ children }: { children: ReactNode }) { return <div className="empty"><Icon name="info" size={26} /><p>{children}</p></div>; }

export default function App() {
  const [data, setData] = useState<Dashboard>();
  const [error, setError] = useState('');
  const [page, setPage] = useState<Page>('market');
  const [datasetId, setDatasetId] = useState('');
  const [minutes, setMinutes] = useState('15');
  const [zone, setZone] = useState('Europe/Moscow');
  const [selected, setSelected] = useState<Forecast>();
  const [historical, setHistorical] = useState(true);
  const [showOutcome, setShowOutcome] = useState(false);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/dashboard.json`, { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error(`Снимок исследования недоступен (${r.status}). Выполни локальную сборку или запусти Actions.`); return r.json(); })
      .then((value: Dashboard) => { if (value.schema_version !== '1.0') throw new Error('Версия снимка не поддерживается'); setData(value); })
      .catch(e => setError(String(e.message)));
  }, []);
  const dataset = data?.datasets.find(d => d.dataset_id === datasetId) ?? data?.datasets[0];
  const horizon = dataset?.horizons[minutes];
  const forecast = selected ?? horizon?.history.at(-1);
  const metrics = horizon?.models[0]?.test;
  const digits = dataset?.profile.price_precision ?? 2;
  const switchPage = (value: Page) => { setPage(value); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  function resetSelection() { setSelected(undefined); setShowOutcome(false); }
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={() => switchPage('market')} aria-label="Квант лаб — главная"><div className="brand-icon"><Icon name="market" size={24} /></div><span>Квант лаб<small>RESEARCH WORKSPACE</small></span></a>
      <div className="workspace-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav>{nav.map(item => <button key={item.id} className={page === item.id ? 'nav-item active' : 'nav-item'} onClick={() => switchPage(item.id)}><Icon name={item.icon} /><span>{item.label}</span>{item.id === 'modules' && <small>4</small>}</button>)}</nav>
      <div className="sidebar-note"><span className="status-dot" /> GitHub hosted<small>Исследования по расписанию<br />Без постоянно работающего сервера</small></div>
      <a className="sidebar-bottom" href={`${REPO}/blob/main/README.md`} target="_blank" rel="noreferrer"><Icon name="info" />Как это работает<Icon name="arrow" size={14} /></a>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div><span className="muted">Workspace</span><span className="slash">/</span><span>{nav.find(n => n.id === page)?.label}</span></div><div className="topbar-right"><span className="desktop-only"><Icon name="clock" size={14} />Снимок: {stamp(data?.generated_at_utc, zone)}</span><a href={REPO} target="_blank" rel="noreferrer"><Icon name="github" size={17} />GitHub<Icon name="arrow" size={13} /></a></div></header>
      <main>
        <div className="page-heading"><div className="eyebrow">ЛИЧНАЯ ИССЛЕДОВАТЕЛЬСКАЯ ЛАБОРАТОРИЯ</div><div className="heading-line"><div><h1>{nav.find(n => n.id === page)?.label}</h1><p>{page === 'market' ? 'Диапазоны цены. Измеримое качество. Прозрачные ограничения.' : page === 'research' ? 'Два заранее заданных baseline. Одинаковые даты. Проверка на отложенной истории.' : page === 'history' ? 'Неизменяемые записи исторических симуляций и их исходов.' : page === 'data' ? 'От исходного CSV до полной свечи — с проверкой каждого шага.' : 'Новые источники подключаются после отдельной проверки пользы.'}</p></div><a className="button secondary" href={WORKFLOW} target="_blank" rel="noreferrer"><Icon name="lab" />Запустить расчёт<Icon name="arrow" size={14} /></a></div></div>
        {error ? <div className="notice amber"><Icon name="info" /><div>{error}<p><a href={WORKFLOW}>Открыть GitHub Actions</a></p></div></div> : !data ? <div className="loading"><div className="spinner" />Загружаю исследование…</div> : <>
          <div className="notice amber" role="status"><Badge tone="amber">{dataset?.profile.is_demo ? 'DEMO' : 'BACKTEST ONLY'}</Badge><div><strong>{dataset?.profile.is_demo ? 'Синтетические данные · проверка работы системы' : 'Исторические данные · исследовательский режим'}</strong><span>{dataset?.profile.is_demo ? 'Цены и метрики ниже — демонстрационные. Реальные котировки пока не подключены.' : 'Оперативного прогноза нет. Историческая симуляция не является forward-проверкой.'}</span></div><button onClick={() => switchPage('data')}>Подключить CSV <Icon name="chevron" size={14} /></button></div>
          {!dataset || !horizon ? <Empty>Нет опубликованных данных. Импортируй CSV локально или запусти демонстрационную сборку.</Empty> : <>
            <div className="toolbar"><div className="instrument-select"><span className="instrument-logo">{dataset.profile.instrument_id.startsWith('XAU') ? 'Au' : 'N'}</span><select aria-label="Инструмент и источник" value={dataset.dataset_id} onChange={e => { setDatasetId(e.target.value); resetSelection(); }}>{data.datasets.map(d => <option key={d.dataset_id} value={d.dataset_id}>{d.profile.instrument_id} · {d.profile.is_demo ? 'DEMO' : d.profile.source_symbol}</option>)}</select></div><div className="timeframes">{[['15', 'M15'], ['60', 'H1'], ['240', 'H4']].map(([value, label]) => <button key={value} className={minutes === value ? 'selected' : ''} onClick={() => { setMinutes(value); resetSelection(); }}>{label}</button>)}<button disabled title="Session/D1 будет добавлен после проверки календарей">Session</button></div><div className="toolbar-spacer" /><select className="zone" aria-label="Часовой пояс" value={zone} onChange={e => setZone(e.target.value)}><option value="Europe/Moscow">Москва · UTC+3</option><option value="UTC">UTC</option><option value="America/New_York">Нью-Йорк</option></select><Badge>NO LIVE FORECAST</Badge></div>
            {page === 'market' && <>
              <div className="metrics-grid"><Metric label="Цена в архиве" value={number(dataset.latest_close, digits)} detail={`${stamp(dataset.quality.last_bar_close_utc, zone)} · ${dataset.profile.source_symbol}`} icon="market" /><Metric label="Покрытие диапазона 90%" value={pct(metrics?.coverage['0.9'])} detail={`На отложенной истории · ${number(metrics?.n, 0)} окон`} icon="target" /><Metric label="Средняя ширина 90%" value={number(metrics?.mean_width_90, digits)} detail="В пунктах инструмента · baseline B0" icon="lab" /><Metric label="Forward-наблюдения" value="0" detail="Допуск к торговле: не подтверждён" icon="history" /></div>
              <div className="market-grid"><Panel title={`${dataset.profile.instrument_id} · ${minutes === '15' ? 'M15' : `H${Number(minutes) / 60}`}`} subtitle={historical ? 'Последнее окно исторической симуляции · baseline B0' : 'Последние закрытые свечи из архива'} action={<div className="segmented"><button className={historical ? 'selected' : ''} onClick={() => setHistorical(true)}>История</button><button className={!historical ? 'selected' : ''} onClick={() => setHistorical(false)}>Сейчас</button></div>} className="chart-panel">
                <div className="chart-toolbar"><div className="chart-legend">{['50', '80', '90', '95'].map(c => <span key={c} className={`legend-${c}`}><i />{c}%</span>)}</div>{historical && <label className="checkbox"><input type="checkbox" checked={showOutcome} onChange={e => setShowOutcome(e.target.checked)} />Показать факт</label>}</div>
                <PriceChart bars={horizon.bars} forecast={historical ? forecast : undefined} showOutcome={showOutcome} digits={digits} />
                {!historical && <div className="chart-notice"><Icon name="info" />NO FORECAST — постоянный источник данных и рабочая модель не подключены.</div>}
                <div className="chart-foot"><span><span className="status-dot" />Только закрытые свечи</span><a href={dataset.profile.is_demo ? 'https://www.tradingview.com/chart/' : `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(dataset.profile.source_symbol)}`} target="_blank" rel="noreferrer">TradingView <Icon name="arrow" size={12} /></a><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">График на TradingView Lightweight Charts™</a></div>
              </Panel><Panel title="Паспорт исследования" subtitle="Что именно посчитано" className="passport"><Badge tone="teal">FORECAST RESEARCH</Badge><dl><dt>Источник</dt><dd>{dataset.profile.source_symbol}</dd><dt>Прогнозный горизонт</dt><dd>{minutes} минут · следующий бар</dd><dt>Метод</dt><dd>Сезонные исторические квантили</dd><dt>Статус модели</dt><dd><Badge tone="amber">{horizon.status}</Badge></dd><dt>Реальных forward-прогнозов</dt><dd>0</dd><dt>Торговое преимущество</dt><dd className="amber-text">Не доказано</dd></dl><div className="subtle-note"><Icon name="info" /><p>Попадание High и Low в диапазон проверяется совместно. Оно не означает вероятность прибыльной сделки.</p></div><button className="text-button" onClick={() => switchPage('research')}>Метрики и проверка <Icon name="chevron" size={14} /></button></Panel></div>
              {historical && forecast ? <><div className="section-label">ИСТОРИЧЕСКОЕ ОКНО <span>{stamp(forecast.horizon_start_utc, zone)} — {stamp(forecast.horizon_end_utc, zone)}</span><Badge>Рассчитано после события</Badge></div><div className="ranges-grid">{['0.5', '0.8', '0.9', '0.95'].map(c => <div key={c} className={`range-card ${c === '0.9' ? 'emphasis' : ''}`}><div><span>Диапазон {Number(c) * 100}%</span><span className={`range-dot legend-${Number(c) * 100}`} /></div><strong>{number(forecast.forecast_quantiles[c].lower, digits)} <span>—</span> {number(forecast.forecast_quantiles[c].upper, digits)}</strong><small>Номинальный уровень · не гарантия</small></div>)}</div></> : null}
              <div className="bottom-grid"><Panel title="Калибровка baseline" subtitle="Совместное покрытие High и Low на тестовом участке" action={<button className="text-button" onClick={() => switchPage('research')}>Подробнее <Icon name="arrow" size={13} /></button>}><Calibration horizon={horizon} /></Panel><Panel title="Контроль данных" subtitle="Полнота внутри загруженного участка" action={<button className="text-button" onClick={() => switchPage('data')}>Открыть <Icon name="arrow" size={13} /></button>}><QualitySummary dataset={dataset} /><div className="subtle-note">100% внутри файла не подтверждает достаточную глубину истории.</div></Panel></div>
            </>}
            {page === 'research' && <Research horizon={horizon} dataset={dataset} zone={zone} />}
            {page === 'history' && <History horizon={horizon} zone={zone} digits={digits} onSelect={f => { setSelected(f); setHistorical(true); setShowOutcome(false); switchPage('market'); }} />}
            {page === 'data' && <DataPage dataset={dataset} zone={zone} />}
            {page === 'modules' && <><div className="module-grid">{data.modules.map(m => <Panel key={m.id} title={m.name} action={<Badge>{m.status}</Badge>}><p className="module-description">{m.id === 'polymarket' ? 'Проверка дополнительной ценности вероятностей контрактов на одинаковых OOS-датах.' : m.id === 'macro' ? 'События CPI, FOMC и NFP с реальным временем доступности информации.' : m.id === 'webhook' ? 'Приём завершённых M1-свечей через HTTPS. Для работы нужен ПК или VPS.' : 'Модели-кандидаты после baseline, с отдельной проверкой калибровки.'}</p></Panel>)}</div><Scenario dataset={dataset} /></>}
          </>}
          <footer><span>КВАНТ ЛАБ <span className="footer-dot">·</span> v0.1.0</span><span>Прогноз ≠ торговое решение <span className="footer-dot">·</span> Автоторговля отсутствует</span><a href={`${REPO}/blob/main/docs/ACCEPTANCE.md`} target="_blank" rel="noreferrer">Статус реализации <Icon name="arrow" size={12} /></a></footer>
        </>}
      </main>
    </div>
  </div>;
}

function Metric({ label, value, detail, icon }: { label: string; value: string; detail: string; icon: string }) {
  return <div className="metric"><div className="metric-label">{label}<Icon name={icon} size={16} /></div><strong>{value}</strong><small>{detail}</small></div>;
}

function Calibration({ horizon }: { horizon: Horizon }) {
  const metrics = horizon.models[0]?.test;
  if (!metrics) return <Empty>Недостаточно окон для проверки baseline.</Empty>;
  return <div className="calibration"><div className="calibration-key"><span><i className="actual-dot" />Фактическое</span><span><i className="nominal-dot" />Номинальное</span><small>N = {metrics.n}</small></div>{['0.5', '0.8', '0.9', '0.95'].map(c => <div className="cal-row" key={c}><span>{Number(c) * 100}%</span><div className="cal-track"><div style={{ width: pct(metrics.coverage[c]) }} /><i style={{ left: pct(Number(c)) }} /></div><strong>{pct(metrics.coverage[c])}</strong></div>)}<p className="caption">Хронологический test · последние 20% доступных окон. Параметры зафиксированы до сравнения.</p></div>;
}

function QualitySummary({ dataset }: { dataset: Dataset }) {
  return <div className="quality-summary"><div><span>Загружено свечей</span><strong>{number(dataset.quality.rows, 0)}</strong></div><div><span>Полнота участка</span><strong className="teal-text">{pct(dataset.quality.coverage, 2)}</strong></div><div className="progress-track"><span style={{ width: pct(dataset.quality.coverage) }} /></div><div><span>Пропуски по календарю</span><strong>{dataset.quality.missing_bars}</strong></div><div><span>Вне настроенной сессии</span><strong>{dataset.quality.off_session_bars}</strong></div><div><span>Актуальность потока</span><Badge tone="amber">{dataset.profile.is_demo ? 'DEMO ARCHIVE' : 'ARCHIVE / NOT LIVE'}</Badge></div></div>;
}

function Research({ horizon, dataset, zone }: { horizon: Horizon; dataset: Dataset; zone: string }) {
  const paired = horizon.paired;
  return <><div className="notice"><Icon name="lab" /><div><strong>Протокол зафиксирован: 60% / 20% / 20%</strong><span>Development → validation → test. B0 — фиксированный benchmark; B1 — кандидат. Автоматического внедрения нет.</span></div></div><Panel title="Сравнение на одинаковых timestamps" subtitle="Whole-candle envelope score учитывает и High, и Low; меньше — лучше." action={<Badge tone="amber">{dataset.profile.is_demo ? 'DEMO' : 'BACKTEST ONLY'}</Badge>}>
    {horizon.models.length ? <div className="table-scroll"><table><thead><tr><th>Модель</th><th>N test</th><th>Coverage 90%</th><th>Ширина 90%</th><th>Score, bps</th><th>Статус</th></tr></thead><tbody>{horizon.models.map(m => <tr key={m.id}><td><strong>{m.role === 'baseline' ? 'B0' : 'B1'} · {m.name}</strong><small>{m.id}</small></td><td>{m.test.n}</td><td>{pct(m.test.coverage['0.9'])}</td><td>{number(m.test.mean_width_90)}</td><td>{number(m.test.score_90_bps)}</td><td><Badge tone="amber">{m.gate.status}</Badge></td></tr>)}</tbody></table></div> : <Empty>Недостаточно полных окон. Требуется минимум 180 наблюдений для начальной симуляции.</Empty>}
  </Panel><div className="bottom-grid"><Panel title="Проверка дополнительной пользы" subtitle="Парный bootstrap по календарным UTC-дням"><dl className="details"><dt>Сравниваемых прогнозов</dt><dd>{paired?.n ?? '—'}</dd><dt>Блоков-дней</dt><dd>{paired?.day_blocks ?? '—'}</dd><dt>Δ score B0 − B1, bps</dt><dd>{number(paired?.mean_score_improvement_bps)}</dd><dt>95% bootstrap-интервал</dt><dd>{paired?.ci95 ? `${number(paired.ci95[0])} … ${number(paired.ci95[1])}` : 'Мало независимых блоков'}</dd><dt>Coverage сопоставим (±2 п.п.)</dt><dd>{paired ? paired.coverage_comparable ? 'Да' : 'Нет' : '—'}</dd><dt>Преимущество в торговле</dt><dd className="amber-text">Не проверялось</dd></dl><p className="caption">На демо экономические выводы не делаются. 500 повторов bootstrap, seed 42. Узкий диапазон сам по себе не означает лучший прогноз.</p></Panel><Panel title="Калибровка baseline" subtitle="Тестовый участок"><Calibration horizon={horizon} /></Panel></div>
    <Panel title="Реестр и ограничения" subtitle={`Run: ${horizon.run_id?.slice(0, 24) ?? 'пока нет'}`}><div className="registry-grid"><div><span>Начало validation</span><strong>{stamp(horizon.split?.validation_start_utc, zone)}</strong></div><div><span>Начало test</span><strong>{stamp(horizon.split?.test_start_utc, zone)}</strong></div><div><span>Настоящий forward</span><strong>0 прогнозов</strong></div></div>{horizon.models.map(m => <div className="gate-row" key={m.id}><strong>{m.role === 'baseline' ? 'B0' : 'B1'}</strong><div>{m.gate.reasons.map(reason => <Badge key={reason}>{reason}</Badge>)}</div></div>)}<div className="subtle-note">Все результаты — историческая симуляция. News, PIT, direction/touch probabilities, HAR и LightGBM ещё не реализованы. Для честного повторения сохраняются snapshot hash, параметры, версия кода и результаты.</div></Panel>
    {horizon.models[0] && <Panel title="Покрытие 90% по режимам" subtitle="Режим определён по волатильности, известной до начала окна."><div className="regimes">{horizon.models[0].test.by_regime.map(r => <div key={r.regime}><span>{({ low: 'Низкая', normal: 'Обычная', high: 'Высокая' })[r.regime]} волатильность</span><strong>{pct(r.coverage_90)}</strong><small>N = {r.n}</small></div>)}</div></Panel>}
  </>;
}

function History({ horizon, zone, digits, onSelect }: { horizon: Horizon; zone: string; digits: number; onSelect: (f: Forecast) => void }) {
  const [filter, setFilter] = useState('all');
  const rows = [...horizon.history].reverse().filter(f => filter === 'all' || (filter === 'miss' ? !f.outcome.joint_covered_90 : f.outcome.joint_covered_90));
  return <Panel title="Журнал симуляций" subtitle="Последние 120 окон B0. Запись создана после события; это не live-issued прогнозы." action={<button className="button secondary" onClick={() => download('quant-forecast-history.json', JSON.stringify(horizon.history, null, 2))}><Icon name="download" />JSON</button>}><div className="history-filters"><select aria-label="Фильтр результатов" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Все результаты</option><option value="covered">Попадания 90%</option><option value="miss">Выходы из диапазона</option></select><Badge>HISTORICAL SIMULATION</Badge></div>{rows.length ? <div className="table-scroll"><table><thead><tr><th>Окно</th><th>Диапазон 90%</th><th>Факт Low / High</th><th>Совместное попадание</th><th>Открыть</th></tr></thead><tbody>{rows.map(f => <tr key={f.forecast_id}><td><strong>{stamp(f.as_of_utc, zone)}</strong><small>{f.forecast_id.slice(0, 12)}</small></td><td>{number(f.forecast_quantiles['0.9'].lower, digits)} — {number(f.forecast_quantiles['0.9'].upper, digits)}</td><td>{number(f.outcome.realized_low, digits)} / {number(f.outcome.realized_high, digits)}</td><td><Badge tone={f.outcome.joint_covered_90 ? 'teal' : 'amber'}>{f.outcome.joint_covered_90 ? 'В диапазоне' : 'Выход'}</Badge></td><td><button className="icon-button" aria-label={`Открыть прогноз ${f.forecast_id.slice(0, 12)}`} onClick={() => onSelect(f)}><Icon name="arrow" /></button></td></tr>)}</tbody></table></div> : <Empty>Для выбранного фильтра пока нет записей.</Empty>}</Panel>;
}

function DataPage({ dataset, zone }: { dataset: Dataset; zone: string }) {
  return <><div className="bottom-grid"><Panel title="Качество загруженного участка" subtitle={dataset.profile.source_symbol}><QualitySummary dataset={dataset} /><dl className="details"><dt>Первая свеча</dt><dd>{stamp(dataset.quality.first_bar_utc, zone)}</dd><dt>Последняя свеча закрыта</dt><dd>{stamp(dataset.quality.last_bar_close_utc, zone)}</dd><dt>Вне календаря</dt><dd>{dataset.quality.off_session_bars}</dd><dt>Общая глубина истории</dt><dd>Полнота не установлена</dd></dl><div className="gate-row">{dataset.quality.flags.map(f => <Badge key={f} tone="amber">{f}</Badge>)}</div></Panel><Panel title="Профиль источника" subtitle="CFD, spot и futures не подменяются друг другом"><dl className="details"><dt>Класс актива</dt><dd>{dataset.profile.asset_class}</dd><dt>Базовый таймфрейм</dt><dd>{dataset.profile.timeframe_minutes} мин</dd><dt>Календарь</dt><dd>{dataset.profile.calendar.timezone}</dd><dt>Календарь проверен</dt><dd>{dataset.profile.calendar.verified ? 'Да, для этого источника' : 'Нет'}</dd><dt>Тип объёма</dt><dd>{dataset.profile.available_volume_type}</dd><dt>Лицензия</dt><dd>{dataset.profile.data_license}</dd><dt>Snapshot SHA-256</dt><dd className="hash">{dataset.dataset_hash}</dd></dl></Panel></div><ImportPanel /></>;
}

function ImportPanel() {
  const [preview, setPreview] = useState<ReturnType<typeof inspectCSV>>();
  const [fileName, setFileName] = useState('');
  const [payload, setPayload] = useState<File>();
  const [symbol, setSymbol] = useState('');
  const [instrument, setInstrument] = useState('XAUUSD');
  const [frame, setFrame] = useState('1');
  const [zone, setZone] = useState('UTC');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const valid = preview && !preview.missing.length && !preview.invalid && !preview.errors.length && symbol.includes(':');
  const manifest = { instrument_id: instrument, source: 'tradingview_csv', source_symbol: symbol, asset_class: 'cfd', timeframe_minutes: Number(frame), timestamp_timezone: zone, timestamp_unit: 's', standard_ohlc: true, available_volume_type: 'none', data_license: 'UNCONFIRMED', publish_allowed: false, calendar: { timezone: zone, verified: false, sessions: [{ weekdays: [0, 1, 2, 3, 4], open_minute: 0, close_minute: 1440 }], closed_dates: [], overrides: {} } };
  async function choose(file?: File) {
    if (!file) return;
    setMessage('');
    if (file.size > 25 * 1024 * 1024) { setMessage('Файл больше 25 MiB. Раздели экспорт на части.'); return; }
    try { setPreview(inspectCSV(await file.text())); setPayload(file); setFileName(file.name); } catch (e) { setMessage(String(e)); }
  }
  async function sendLocal() {
    if (!valid || !payload) return;
    setBusy(true); setMessage('');
    const form = new FormData(); form.append('file', payload); form.append('profile_json', JSON.stringify(manifest));
    try {
      const response = await fetch('/v1/imports/tradingview-csv', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? 'Ошибка импорта');
      setMessage(`Сохранено: ${result.rows_added} новых свечей. Для обновления исследования выполни python -m backend.app.cli build и обнови страницу.`);
    } catch (e) { setMessage(`Локальный API: ${String(e)}`); } finally { setBusy(false); }
  }
  return <Panel title="Импорт TradingView CSV" subtitle="На GitHub Pages файл проверяется в браузере. Он никуда не отправляется."><div className="import-grid"><div><input ref={input} className="sr-only" type="file" accept=".csv,text/csv" onChange={e => choose(e.target.files?.[0])} /><button className="dropzone" onClick={() => input.current?.click()}><span className="upload-icon"><Icon name="upload" size={26} /></span><strong>{fileName || 'Выбрать CSV с котировками'}</strong><small>Time, Open, High, Low, Close · до 25 MiB</small><span className="button secondary">Открыть файл</span></button></div><div className="import-form"><label>Инструмент<select value={instrument} onChange={e => setInstrument(e.target.value)}><option>XAUUSD</option><option>NAS100</option><option>SPX500</option><option>XAGUSD</option></select></label><label>Точный символ TradingView<input placeholder="PROVIDER:SYMBOL" value={symbol} onChange={e => setSymbol(e.target.value)} /></label><div className="form-row"><label>Таймфрейм CSV<select value={frame} onChange={e => setFrame(e.target.value)}><option value="1">M1</option><option value="15">M15</option><option value="60">H1</option></select></label><label>Часовой пояс меток<input value={zone} onChange={e => setZone(e.target.value)} placeholder="UTC" /></label></div><div className="button-row"><button disabled={!valid} className="button primary" onClick={() => download(`${fileName.replace(/\.csv$/i, '') || instrument}.profile.json`, JSON.stringify(manifest, null, 2))}><Icon name="download" />Скачать профиль</button>{import.meta.env.DEV && <button disabled={!valid || busy} className="button secondary" onClick={sendLocal}>{busy ? 'Импорт…' : 'Импортировать локально'}</button>}</div></div></div>
    {preview && <><div className="import-stats"><Badge tone={preview.invalid || preview.missing.length || preview.errors.length ? 'amber' : 'teal'}>{number(preview.rows, 0)} строк</Badge><span>Ошибки OHLC: {preview.invalid}</span><span>Повторы времени: {preview.duplicates}</span>{preview.missing.length > 0 && <span className="amber-text">Нет колонок: {preview.missing.join(', ')}</span>}</div>{preview.errors.length > 0 && <p className="amber-text">{preview.errors.join('; ')}</p>}<div className="table-scroll"><table><thead><tr>{preview.fields.slice(0, 7).map(f => <th key={f}>{f}</th>)}</tr></thead><tbody>{preview.preview.map((row, i) => <tr key={i}>{preview.fields.slice(0, 7).map(f => <td key={f}>{row[f]}</td>)}</tr>)}</tbody></table></div></>}
    {message && <div className="notice" role="status">{message}</div>}<div className="subtle-note"><Icon name="info" /><div>Проверка в браузере — предварительная. Полная проверка времени, календаря и конфликтов выполняется Python-модулем. Для Pages: после проверки лицензии добавь CSV и профиль в <a href={`${REPO}/tree/main/inputs`} target="_blank" rel="noreferrer">inputs</a> и явно установи publish_allowed=true. Для локальной работы публикация не нужна.</div></div>
  </Panel>;
}

function Scenario({ dataset }: { dataset: Dataset }) {
  const anchor = dataset.latest_close ?? 100;
  const [direction, setDirection] = useState('long');
  const [entry, setEntry] = useState(String(anchor));
  const [tp, setTp] = useState(String(Math.round(anchor * 1.01 * 100) / 100));
  const [sl, setSl] = useState(String(Math.round(anchor * .995 * 100) / 100));
  const rr = riskReward(direction, Number(entry), Number(tp), Number(sl));
  return <Panel title="Мой сценарий" subtitle="Пока доступна только геометрия сделки. Вероятности и expected R не обучены." action={<Badge>RESEARCH</Badge>}><div className="scenario-form"><label>Направление<select value={direction} onChange={e => setDirection(e.target.value)}><option value="long">Long</option><option value="short">Short</option></select></label>{[['Entry', entry, setEntry], ['Take Profit', tp, setTp], ['Stop Loss', sl, setSl]].map(([label, value, setter]) => <label key={String(label)}>{String(label)}<input type="number" min="0" step="any" value={String(value)} onChange={e => (setter as (v: string) => void)(e.target.value)} /></label>)}<div className="rr-result"><small>Reward / Risk до издержек</small><strong>{rr == null ? 'Проверь уровни' : `${number(rr)} R`}</strong></div></div><div className="subtle-note">P(TP), P(SL), P(TP first) и математическое ожидание не рассчитываются из границ диапазона. Автоматического исполнения сделок нет.</div></Panel>;
}
