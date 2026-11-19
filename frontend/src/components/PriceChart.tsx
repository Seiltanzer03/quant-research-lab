import { useEffect, useRef } from 'react';
import { CandlestickSeries, ColorType, createChart, LineSeries, LineStyle } from 'lightweight-charts';
import type { UTCTimestamp } from 'lightweight-charts';
import type { Bar, Bounds } from '../types';

type ChartForecast = { horizon_start_utc: string; horizon_end_utc: string; anchor_price: number; forecast_quantiles: Record<string, Bounds>; mode?: string };
export function PriceChart({ bars, forecast, showOutcome, digits }: { bars: Bar[]; forecast?: ChartForecast; showOutcome: boolean; digits: number }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !bars.length) return;
    const chart = createChart(container.current, {
      autoSize: true, height: 360,
      layout: { background: { type: ColorType.Solid, color: '#0e141d' }, textColor: '#7e8c9d', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11, attributionLogo: true },
      grid: { vertLines: { color: '#19212c' }, horzLines: { color: '#19212c' } },
      rightPriceScale: { borderColor: '#26303d', minimumWidth: 75 },
      timeScale: { borderColor: '#26303d', timeVisible: true, secondsVisible: false, rightOffset: 3, barSpacing: 8 },
      crosshair: { vertLine: { color: '#64748b', labelBackgroundColor: '#263746' }, horzLine: { color: '#64748b', labelBackgroundColor: '#263746' } },
    });
    const candles = chart.addSeries(CandlestickSeries, { upColor: '#58c6af', downColor: '#e2838c', wickUpColor: '#58c6af', wickDownColor: '#e2838c', borderVisible: false, priceFormat: { type: 'price', precision: digits, minMove: 10 ** -digits } });
    const start = forecast ? new Date(forecast.horizon_start_utc).getTime() / 1000 : undefined;
    const visible = start && !showOutcome ? bars.filter(b => b.time < start) : (start ? bars.filter(b => b.time <= start) : bars);
    candles.setData(visible.slice(-90).map(b => ({ ...b, time: b.time as UTCTimestamp })));
    if (forecast && start) {
      const end = new Date(forecast.horizon_end_utc).getTime() / 1000;
      const colors: Record<string, string> = { '0.95': '#374e63', '0.9': '#4b8693', '0.8': '#5bb5b0', '0.5': '#88dfcf' };
      for (const confidence of ['0.95', '0.9', '0.8', '0.5']) {
        const bounds = forecast.forecast_quantiles[confidence];
        for (const side of ['lower', 'upper'] as const) {
          const line = chart.addSeries(LineSeries, { color: colors[confidence], lineWidth: confidence === '0.9' ? 2 : 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: confidence === '0.9', crosshairMarkerVisible: false, title: confidence === '0.9' ? '90%' : '', priceFormat: { type: 'price', precision: digits, minMove: 10 ** -digits } });
          line.setData([{ time: start as UTCTimestamp, value: bounds[side] }, { time: end as UTCTimestamp, value: bounds[side] }]);
        }
      }
      const anchor = chart.addSeries(LineSeries, { color: '#d8b779', lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      anchor.setData([{ time: start as UTCTimestamp, value: forecast.anchor_price }, { time: end as UTCTimestamp, value: forecast.anchor_price }]);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, forecast, showOutcome, digits]);
  return <div className="chart-wrap"><div ref={container} className="price-chart" /><div className="chart-label">{forecast ? forecast.mode === 'forward_paper' ? 'FORWARD PAPER · ЛИЧНЫЙ ЖУРНАЛ' : 'HISTORICAL SIMULATION' : 'РЕАЛЬНЫЕ КОТИРОВКИ'} · UTC</div>{!bars.length && <div className="chart-empty">Недостаточно полных свечей</div>}</div>;
}
