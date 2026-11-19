import { useEffect, useState } from 'react';
import type { Lab } from './engine/useLab';
import type { ScenarioResult } from './engine/contracts';
import { Panel, Badge, Empty } from './components/ui';
import { Icon } from './components/Icon';
import { download, number, pct, riskReward, stamp } from './utils';

export function ScenarioWorkspace({ lab, minutes, zone }: { lab: Lab; minutes: number; zone: string }) {
  const anchor = lab.source?.bars.at(-1)?.close;
  const [direction, setDirection] = useState<'long' | 'short'>('long');
  const [entry, setEntry] = useState(''), [tp, setTp] = useState(''), [sl, setSl] = useState(''), [cost, setCost] = useState('0');
  const [scaled, setScaled] = useState(true);
  const [result, setResult] = useState<ScenarioResult>();
  useEffect(() => { if (anchor) { setEntry(String(anchor)); setTp(String(Math.round(anchor * 1.005 * 1000) / 1000)); setSl(String(Math.round(anchor * .9975 * 1000) / 1000)); setResult(undefined); } }, [anchor, lab.source?.id]);
  useEffect(() => { setResult(undefined); }, [minutes, lab.settings]);
  const rr = riskReward(direction, Number(entry), Number(tp), Number(sl));
  async function run() { const value = await lab.scenario({ direction, entry: Number(entry), tp: Number(tp), sl: Number(sl), cost_points: Number(cost), minutes, volatility_scaled: scaled }); if (value) setResult(value); }
  if (!lab.source) return <Empty>Для сценария сначала открой готовую историю или импортируй свои свечи в разделе «Данные».</Empty>;
  return <><Panel title="Проверить мой TP/SL на реальных движениях" subtitle="Одинаковая геометрия применяется к прошлым непересекающимся окнам. Учитываются time exit, издержки и неопределённый порядок внутри исходной свечи." action={<Badge>HISTORICAL REPLAY</Badge>}>
    <div className="scenario-form"><label>Направление<select aria-label="Направление сценария" value={direction} onChange={e => setDirection(e.target.value as typeof direction)}><option value="long">Long</option><option value="short">Short</option></select></label>{[['Entry', entry, setEntry], ['Take Profit', tp, setTp], ['Stop Loss', sl, setSl], ['Издержки, ед. цены', cost, setCost]].map(([label, value, setter]) => <label key={String(label)}>{String(label)}<input type="number" step="any" value={String(value)} onChange={e => (setter as (v: string) => void)(e.target.value)} /></label>)}<div className="rr-result"><small>Reward / Risk до издержек</small><strong>{rr == null ? 'Проверь уровни' : `${number(rr)} R`}</strong></div></div>
    <div className="subtle-note">Разрешение истории: M{lab.source.profile.timeframe_minutes}. Порядок касаний внутри одной такой свечи не угадывается.</div><div className="scenario-controls"><label className="checkbox"><input type="checkbox" checked={scaled} onChange={e => setScaled(e.target.checked)} />Привести прошлые движения к последней известной волатильности</label><button className="button primary" disabled={lab.busy || rr == null || lab.source.profile.timeframe_minutes > minutes} onClick={run}><Icon name="lab" />Проверить {minutes} минут</button></div>
    {lab.source.profile.timeframe_minutes > minutes && <div className="subtle-note">Исходное разрешение крупнее выбранного горизонта. Выбери более длинный горизонт или более подробную историю.</div>}
  </Panel>{result && <>
    <div className="metrics-grid"><div className="metric"><div className="metric-label">TP коснулся за горизонт</div><strong>{pct(result.tp_touch)}</strong><small>SL коснулся: {pct(result.sl_touch)}</small></div><div className="metric"><div className="metric-label">TP раньше SL — точно</div><strong>{pct(result.tp_first)}</strong><small>Неопределённый порядок: {pct(result.ambiguous)}</small></div><div className="metric"><div className="metric-label">Средний R после издержек</div><strong>{number(result.mean_r_lower)} … {number(result.mean_r_upper)}</strong><small>Пессимистичный … оптимистичный порядок</small></div><div className="metric"><div className="metric-label">Исторических сценариев</div><strong>{number(result.sample_n, 0)}</strong><small>{result.days} блоков-дней</small></div></div>
    <Panel title="Исходы сценария" subtitle={`${result.source_symbol} · ${stamp(result.sample_from_utc, zone)} — ${stamp(result.sample_to_utc, zone)}`} action={<button className="button secondary" onClick={() => download('quant-scenario.json', JSON.stringify(result, null, 2))}><Icon name="download" />Отчёт JSON</button>}><div className="scenario-outcomes">{[['TP первым', result.tp_first], ['SL первым', result.sl_first], ['Time exit', result.neither], ['Оба внутри одной исходной свечи', result.ambiguous]].map(([label, value]) => <div key={String(label)}><span>{String(label)}</span><strong>{pct(Number(value))}</strong></div>)}</div><dl className="details"><dt>95% bootstrap CI среднего R</dt><dd>{result.mean_r_ci95 ? `${number(result.mean_r_ci95[0])} … ${number(result.mean_r_ci95[1])}` : 'Меньше 5 блоков-дней'}</dd><dt>Вариант для CI</dt><dd>Неопределённые исходы считаются SL</dd></dl><div className="subtle-note"><Icon name="info" />{result.warning}</div></Panel>
  </>}</>;
}
