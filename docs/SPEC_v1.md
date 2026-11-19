# QUANT RESEARCH LAB — ТЕХНИЧЕСКОЕ ЗАДАНИЕ v1.0

**Дата:** 19 ноября 2026 г.  
**Назначение:** автономная личная исследовательская инфраструктура и торговый веб-дашборд для прогнозирования диапазонов будущих свечей на индексах и металлах.  
**Рабочая платформа пользователя:** TradingView (основные графики и первичный пользовательский источник котировок).  
**Способ реализации:** поэтапная разработка в Antigravity / VS Code с Python и TypeScript.  
**Начальные рынки:** XAUUSD и NAS100; архитектура универсальна для ES/SPX500, YM/US30, XAGUSD, DAX и других инструментов.  
**Основной принцип:** сначала честное прогнозирование и валидация; торговые правила, Polymarket, новости и автоисполнение добавляются только после проверки.

---

## 0. ЧТО СТРОИМ И ЗАЧЕМ

Создать локально работающую исследовательскую систему, способную в момент времени `t` из данных, известных **не позже t**, прогнозировать диапазоны цены в течение следующих 15, 60, 240 минут и следующей торговой сессии; оценивать вероятности касания заданных уровней и условные распределения исходов; записывать неизменяемые прогнозы до наступления будущих событий; проверять прогнозы и торговую пользу на отложенной истории; показывать в понятном дашборде только результаты с указанием качества и ограничений.

**Обязательное разделение продуктов:**

- `FORECAST` — вероятности и распределения; они могут быть статистически полезны без торгового преимущества.
- `TRADING DECISION` — отдельные правила входа, TP/SL, execution и expectancy, доступные только после самостоятельной проверки.
- `RESEARCH` — исследования внешних факторов, которые должны доказать incremental out-of-sample value.

### Не является целью MVP

Автономный ИИ-трейдер, генерация «точных сигналов», GPT как источник рыночных вероятностей, Polymarket как автоматический BUY/SELL, HFT, order-book L2, нейросеть ради нейросети, автоматическое открытие реальных сделок.

### Что пользователь получит в первой полезной версии

1. Фактические вероятные границы будущей свечи/временного окна: 50/80/90/95%.
2. Вероятность касания введённого TP и SL **в пределах горизонта**; вероятность порядка касаний — только если данные и модель это позволяют.
3. Данные о текущем режиме: реализованная волатильность, сессия, прогнозный диапазон vs типичный.
4. Сравнение модельного диапазона с простым историческим baseline и дневник прогнозов/ошибок.
5. Режим `NO FORECAST` при нехватке данных, сбое источника либо провале контроля качества.
6. Отдельную лабораторию для запуска новых гипотез без изменения рабочего прогноза.

---

## 1. КРИТИЧЕСКОЕ ОГРАНИЧЕНИЕ TRADINGVIEW

TradingView — пользовательская платформа графиков, **не универсальный публичный поставщик программной многолетней M1-истории**.

**Поддерживаемые официальные способы:**

- `CSV import`: экспорт OHLCV из загруженного участка TradingView Supercharts, затем импорт в базу. Длина истории зависит от лимитов/подписки и фактически загруженных баров; наличие 3–5 лет M1 не предполагается.
- `Pine Script v6 alerts → webhook`: отправлять завершённые M1-свечи как JSON на наш HTTPS-приёмник. Для мониторинга событий и постепенного наполнения архива, но это не гарантированно безразрывный datafeed: webhooks могут не доходить, а закрытие последней свечи фиксируется с задержкой появления нового обновления.
- `TradingView для ручной работы`: ссылка «открыть этот инструмент в TradingView», при желании — отдельный Pine-индикатор для отображения **собственных** forecast levels, но не пытаться получать историю обратным неофициальным способом.

**Чего НЕ делать:** парсить приватный websocket, обходить авторизацию/лимиты TV, называть Alert полноценным историческим API, получать feed из графической библиотеки (TradingView charting library itself не содержит данных).

**Обязательное правило:** при исторической недостаточности TV импортировать M1 из отдельного разрешённого поставщика/брокера. Система обязана поддерживать `CSVProvider`, `TradingViewWebhookProvider`, `BrokerAPIProvider`, `FuturesDataProvider` через единый интерфейс и отслеживать разные источники. Для реального execution использовать именно котировки торгуемого CFD/фьючерса либо специально валидированную связь прокси.

Для стартового TV-only режима честно выводить `HISTORY_INCOMPLETE`, если полнота истории/инструмента не подтверждена.

Ссылки на первичную документацию:
- https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/
- https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
- https://www.tradingview.com/support/solutions/43000480679-historical-intraday-data-bars-and-limits-explained/
- https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
- https://www.tradingview.com/pine-script-docs/concepts/repainting/

---

## 2. ИНСТРУМЕНТЫ, ТАЙМФРЕЙМЫ И СЕССИИ

### Начальные instrument profiles

| Канонический ID | Пользовательский символ TV | Экономический актив | Примечание |
|---|---|---|---|
| `XAUUSD` | определяется при первичной настройке (`EXCHANGE:SYMBOL`) | спот/CFD золото | Не отождествлять автоматически с GC |
| `NAS100` | определяется при первичной настройке | CFD Nasdaq100 | Не отождествлять с NQ или NDX |
| `SPX500` | позднее | CFD/индекс SP500 | Не путать с ES и cash SPX |
| `XAGUSD` | позднее | spot/CFD серебро | Не путать с SI |

Запрещено жёстко прошивать `OANDA:...` или какой-либо тикер без подтверждения в TradingView и без сохранения provider metadata. Профиль включает: `canonical_id`, `source`, `source_symbol`, `asset_class`, `quote_currency`, `tick_size`, `price_precision`, `session_calendar`, `timezone`, `DST rules`, `lot_size` (если торгуется), `data_license`, `available_volume_type`, `roll_policy` (для фьючерсов), `execution_instrument_id`.

### Горизонты

- **M15 (15 минут)** — прогноз следующей закрытой M15-свечи при известных данных на закрытии текущей M15.
- **H1 (60 минут)** — следующей H1-свечи.
- **H4 (240 минут)** — следующей H4-свечи.
- **D1 / Session** — отдельный горизонт до конца **определённой торговой сессии**, не «любые 24 часа».
- В исследовании отдельно поддерживаются rolling horizons `next 15m/60m/240m`, которые нельзя смешивать с фиксированными M15/H1/H4 свечами, если начало окна не совпадает.

В MVP работать на **закрытых** стандартных time-based свечах. Нестандартные Heikin Ashi, Renko и другие синтетические типы исключить из primary ingestion.

### Хранение времени

Все внутренние timestamp в UTC. Сохранять `bar_open_utc`, `bar_close_utc`, `event_time_utc`, `received_at_utc`, `decision_available_at_utc`; отдельно отображать user timezone. DST и праздничные/сокращённые сессии определять через календарь инструмента. Разделять session missing bars и реальные потери пакетов.

---

## 3. АРХИТЕКТУРА

```text
[TradingView CSV] --+ 
[TradingView webhook] ----> [INGEST API / ADAPTERS] -->(RAW immutable)
[Broker/API/vendor] -+              |                  |
                                     v                  v
                             [DATA QA + NORMALIZE] --> [Parquet OHLCV]
                                     |                  |
                                     +--> [SQLite metadata / lineage]
                                                        |
                                               [DuckDB / Polars]
                                                        |
                                           [FEATURE ENGINE / LABELS]
                                                        |
                                          [MODEL TRAIN + VALIDATION]
                                                        |
                                          [MODEL REGISTRY / GATES]
                                                        |
                                         [FORECAST ENGINE + JOURNAL]
                                                        |
                                                   [FastAPI]
                                                        |
                        +-------------------------------+------------------+
                        v                               v                  v
               [Trade Dashboard]               [Research Lab]       [Scenario Tester]
                        |
                   [TradingView link]

[FUTURE ADAPTERS]: macro calendar, news timestamps, options/IV, Polymarket,
order flow, positioning, cross-asset context. Each is separately tested.
```

### Предписанный стек

- **Backend:** Python 3.12+ (поддерживаемая версия), FastAPI + Pydantic v2.
- **Научные расчёты:** Polars, DuckDB, NumPy, pandas (для библиотек), SciPy, scikit-learn; `arch` для GARCH (опционально).
- **Машинное обучение:** LightGBM quantile objectives; модели только после baseline.
- **Данные:** локальные Parquet (raw/clean/features), DuckDB для чтения и аналитики, SQLite с WAL для метаданных/задач/истории экспериментов.
- **UI:** React + TypeScript + Vite, TradingView Lightweight Charts (open-source) для собственного графика с полосами прогноза. Главные трейдерские графики остаются в TradingView.
- **Исследования:** Jupyter notebooks как вспомогательный инструмент, НО вся production-логика в проверяемых Python-модулях, а не в notebooks.
- **Сборка и тесты:** Git, pytest, ruff, mypy, ESLint, Vitest/Playwright, CI для тестов.
- **Планировщик:** отдельный service/worker с persistent job status, retry и healthcheck (не запускать долгие задачи в HTTP-обработчике).
- **Развёртывание:** первоначально `localhost` на Windows/Linux (CPU, 16 GB RAM достаточно для M1 bars двух инструментов при разумной обработке); позже Linux VPS для 24/7 webhook/scheduler. Наружу не выставлять незащищённый dashboard.
- **Docker:** опционально, не делать его условием успешного MVP.

### Разделение процессов

1. `ingest-service`: принимает, валидирует, немедленно сохраняет событие и отвечает HTTP.
2. `data-worker`: дедупликация, качества, ресэмплинг и исправление доказанных gaps.
3. `research-worker`: feature/labels/training/validation.
4. `forecast-worker`: оперативные прогнозы утверждённой модели, запись до будущего периода.
5. `api/ui`: отдаёт информацию трейдеру, не изменяя исторический прогноз.

TradingView требует HTTPS Webhook на порту 80/443 (обычно 443), работающий receiver должен ответить примерно за 3 секунды, а у пользователя должна быть включена 2FA. Сразу после сохранения сообщения ответить `202 Accepted`, расчёт отправить worker; настроить проверку источников IP по официальным данным TV, TLS, ограничение размера, частоты, idempotency и журнал доставки. Не помещать пароли брокера или API-ключи в тело/URL вебхука. Вебхуки TV не являются криптографически подписанной надёжной биржевой лентой: проверять и по возможности сверять с независимым провайдером.

---

## 4. ХРАНИЛИЩЕ И СХЕМЫ ДАННЫХ

### Основные таблицы (логически)

| Таблица | Основные поля | Назначение |
|---|---|---|
| `instruments` | id, source_symbol, provider, timezone, tick, session_id | профили инструментов |
| `raw_events` | event_id, payload_hash, source, received_at, raw_payload, status | неизменяемое первичное событие |
| `bars_m1` | instrument_id, source, bar_open_utc, bar_close_utc, OHLCV, is_final, quality_flags | нормализованные M1 |
| `bars_aggregated` | instrument_id, timeframe, anchor, OHLCV, quality_flags | M15/H1/H4/D1 |
| `feature_snapshots` | instrument, as_of, feature_set_version, vector_hash | признаки на известное время |
| `models` | model_id, artifact_hash, training_end, feature_set_id, run_id, status | реестр моделей |
| `forecasts` | forecast_id, issue_time, available_at, expiry, horizon, model_version, quantiles, status | **неизменяемый** прогноз |
| `forecast_outcomes` | forecast_id, outcome_available_at, realized_HLC, scores, evaluation_quality | оценка по факту |
| `experiments` | run_id, hypothesis, dataset_hash, split_scheme, params, metrics, git_sha | воспроизводимость |
| `scenario_evaluations` | scenario_id, user_levels, forecast_id, probability_estimates, caveats | ручные сценарии |
| `external_features` | source, event_time, available_at, revision_time, value, quality | будущие модули |

### Обязательные правила качества

- `high >= max(open, close)`, `low <= min(open, close)`; положительные цены, объём nullable.
- На `(source, instrument_id, bar_open_utc, timeframe)` — уникальный ключ.
- Идемпотентный повторный импорт не создаёт вторых свечей и вторых прогнозов.
- Неполные/изменившиеся свечи не перезаписывают raw. Исправления в clean фиксируются как **новая версия** с provenance.
- `missing M1`, duplicate, DST anomalies, stale feed, dislocated quote, abnormal spread, zero-volume session — маркируются отдельно. Missing bars **не заполнять фиктивными нулями цен**.
- Ресэмплинг OHLC: `open=first`, `high=max`, `low=min`, `close=last`, `volume=sum where present`; выдавать итог только если окно полно и закрыто по календарю.
- Разделять real exchange volume и tick volume у CFD; `volume` может отсутствовать.
- Сохранять оригинальный файл, hash, настройки импорта, условия лицензии и дату доступности данных.
- Все сплиты исследования привязаны к `available_at`, а не к дате публикации задним числом.

**Минимальные operational gates:** источники показывают фактическую долю закрытых M1 среди ожидаемых в торговую сессию; gaps критического горизонта = `NO FORECAST`; `stale feed` и delayed alerts видимы в UI. Порог допустимой задержки — конфигурируемый, не скрытый.

---

## 5. СТРОГАЯ ПОСТАНОВКА ВЕРОЯТНОСТНОГО ПРОГНОЗА

### 5.1 Разделить три разные цели

**A. Диапазон будущего бара / окна:** совместное условие, что будущие High и Low останутся внутри прогнозных границ.

**B. Цена закрытия:** вероятность, что `C_future > C_at_decision` и квантильный диапазон будущего `close`. Не выводить P(close up) напрямую из диапазона High/Low.

**C. Касания уровней:** вероятность, что за время прогноза хотя бы один раз `High >= TP` или `Low <= SL`. Вероятность `TP before SL` — **отдельная path-dependent модель**, не следует из маргинальных вероятностей и OHLC.

### 5.2 Базовые label-определения

Для момента принятия решения `t`, известной последней подтверждённой цены `P_t`, и следующего окна `[t, t+Δ]`:

```text
UP_EXCURSION   = max(0, MAX_HIGH[t:t+Δ] - P_t)
DOWN_EXCURSION = max(0, P_t - MIN_LOW[t:t+Δ])
FUTURE_RETURN  = CLOSE[t+Δ] / P_t - 1
```

Для сопоставимости рынков и нестационарности использовать нормализацию по **volatility estimate, известной на t**. Исходные excursions в пунктах также сохранять. Для горизонта «следующая закрытая свеча» окно строго совпадает с торговым календарём свечи, для `rolling next Δ` — с временем решения.

### 5.3 Интервалы

Обязательные уровни confidence: 50%, 80%, 90%, 95%. Строить квантильные верхнюю и нижнюю границы так, чтобы контролировать **совместное** условие для High и Low. Например, для номинальных 90% использовать односторонние 95%-квантили excursions (по union bound номинальная совместная ошибка ≤10% при корректной условной калибровке маргиналей), затем **проверить и при необходимости адаптивно откалибровать joint empirical coverage** на предыдущих данных.

Важно: доля попаданий за всю историю НЕ гарантирует попадания в каждом режиме волатильности; показывать отдельные режимы, часы, новости. Асимметрия верхней/нижней границы не равна прогнозу направления и сама по себе не доказывает BUY/SELL.

### 5.4 Формат ответа на прогноз

```json
{
  "forecast_id": "uuid",
  "instrument_id": "XAUUSD",
  "source_id": "tradingview:USER_SELECTED_SYMBOL",
  "mode": "next_closed_bar",
  "timeframe": "H1",
  "as_of_utc": "2026-11-19T09:00:00Z",
  "issued_at_utc": "2026-11-19T09:00:02Z",
  "available_at_utc": "2026-11-19T09:00:02Z",
  "horizon_start_utc": "2026-11-19T09:00:00Z",
  "horizon_end_utc": "2026-11-19T10:00:00Z",
  "anchor_price": null,
  "price_unit": "USD/oz",
  "forecast_quantiles": {
    "0.80": { "lower": null, "upper": null },
    "0.90": { "lower": null, "upper": null }
  },
  "probabilities": {
    "close_above_anchor": null
  },
  "model_version": "baseline_v1",
  "data_snapshot_hash": "sha256-placeholder",
  "validation_n": 0,
  "quality_status": "INSUFFICIENT_DATA",
  "is_trading_qualified": false
}
```

`null` здесь означает отсутствие реального расчёта, **не нулевой прогноз**. Время появления прогноза должно быть строго раньше label period, иначе он непригоден для live-оценки; если расчёт запоздал, предсказывать от **нового фактического решения и оставшегося горизонта**, а не делать вид, будто прогноз был доступен при открытии бара.

---

## 6. МОДЕЛИ — В КАКОМ ПОРЯДКЕ РЕАЛИЗОВЫВАТЬ

### Уровень B0 — Seasonal Historical Quantile Baseline (обязателен)

Простой эмпирический прогноз excursions на основании предыдущих наблюдений с похожим горизонтом, сессией и time-of-day. Окно обучения rolling, минимум наблюдений — конфигурируемый. При слишком маленькой выборке откатиться к более широкой группе или `NO FORECAST`, но не подменять недостающие наблюдения вымышленными.

### Уровень B1 — Volatility-scaled empirical / EWMA Student-t

Эмпирические квантильные excursions в единицах volatility, умноженные на текущий прогноз масштаба. EWMA и Student-t используются как понятные эконометрические ориентиры. Не путать conditional distribution `close return` с `high-low excursion`.

### Уровень M1 — HAR-like realized volatility + quantile regression

Признаки волатильности с разными лагами (например 4, 24, 120 M15 bars), время суток, day-of-week, диапазоны/returns. Основной интерпретируемый кандидат; нельзя использовать данные с незакрытого бара.

### Уровень M2 — LightGBM quantile + rolling/adaptive calibration

Отдельные квантильные модели для UP/DOWN excursions; прогноз закрытия — отдельная head. Калибровка **только по данным, уже ставшим известными к моменту прогноза**. Если данные малообъёмные, модель не включать в production.

### Уровень M3 — GARCH/EGARCH/tails (optional)

Кандидат для прогнозирования volatility/close return distribution; при прогнозе High/Low обязательно дополнительно проверить соответствующее преобразование. EVT для крайних событий — только после достаточной истории хвостов.

**Недопустимо:** автоматически считать нейросеть лучше baseline, оптимизировать сотни наборов параметров и выдать «лучшую» конфигурацию по единственному test-периоду, менять production модель без OOS-протокола.

### Общий feature registry

Разрешённые группы: прошлые returns (1/4/24 bars), previous candle range, realized volatility (несколько горизонтов), normalized realized range, объём и relative volume там, где качество достаточное, сессия/time-of-day/day-of-week, расстояние до session open и известных до `t` session levels, holiday indicator, known scheduled macro-event proximity. Все фичи имеют: `name`, `window`, `available_at`, `source`, `version`, `missing_value_policy`. В MVP нет SMC/ICT, новостей, Polymarket и текстовых моделей.

---

## 7. ПРОТОКОЛ НАУЧНОЙ ПРОВЕРКИ

### Зафиксировать до подбора параметров

- Первичную гипотезу, целевые переменные и инструменты.
- Baseline, метрики, минимальное улучшение и критерий провала.
- Разделение **development → validation → untouched test**, последовательные walk-forward окна.
- Список кандидатов и полные правила исполнения.
- Количество протестированных гипотез: вести registry, не выбирать победителя задним числом.

### Пример временных окон (НЕ жесткая привязка к годам)

1. `train` — только прошлые 12–36 месяцев при наличии.
2. `validation` — следующие 2–3 месяца или rolling folds для выбора гиперпараметров.
3. `locked OOS` — нетронутый будущий период, например последние 6 месяцев, который НЕ использовали для выбора настроек.
4. `forward paper` — прогнозы, созданные в реальном времени до наступления следующего бара.

При малом датасете не утверждать, что проведён надёжный independent OOS. Для пересекающихся горизонтов использовать purging/embargo; разброс метрик/доверительные интервалы оценивать block bootstrap по времени/дням, а не iid ресэмплингом соседних баров.

### Обязательные метрики

- `Joint Coverage` по номинальным 50/80/90/95%, общий и по разрезам: волатильность, сессия, час, день, новости.
- `Mean / Median Interval Width` **при сопоставимом coverage**.
- `Interval Score / Winkler` для интервалов; `Pinball Loss` для маргинальных квантилей.
- `PIT / calibration diagnostics` для близких к полным распределениям.
- `Brier Score`, `Log Loss` + reliability diagram для направления/касания и иных вероятностей, если они реально обучены.
- `Drift`: изменение calibration при смене режима, stale source и дата последней переоценки.
- Положительное trading expectancy **отдельно** от score. Если модель не улучшает базовый benchmark на OOS — не считать исследовательским достижением.

### Минимальные acceptance gates для названия «проверенная модель»

Это инженерные стартовые пороги, а не найденные академически «магические числа»:

- Не меньше 500 завершённых, заранее выпущенных прогнозов **для конкретного инструмента × горизонта × режима теста**, прежде чем разрешать уверенные надписи о качестве (для некоторых анализов может потребоваться значительно больше).
- Для номинальных 90% за эти прогнозы coverage в ориентировочном интервале 87–93% и без серьёзного систематического провала в крупнейших режимах. Не применять этот порог как гарантию точности из-за автокорреляции.
- Утверждение «лучше baseline» — только при корректном сопоставимом coverage, меньшем interval score и положительном **paired block-bootstrap** интервале улучшения, плюс проверка устойчивости по месяцам.
- Для торговой пользы — отдельно OOS после спреда/slippage и сравнение с идентичными timestamps без модели; результат может быть `NOT PROVEN`.
- Никакой «точности 90%» на 20 примерах; вместо этого `Пока недостаточно наблюдений`.

**Важно:** инженерная корректность системы не зависит от того, найдётся ли рыночное преимущество. Успешный честный вывод «baseline не побеждён» — тоже успешная работа исследовательского ПО.

---

## 8. РУЧНОЙ ТОРГОВЫЙ ДАШБОРД

### Страница №1 — `Рынок / Сейчас`

```text
 QUANT RESEARCH LAB                 Data: OK | Last M1 12:34 | Model: APPROVED
 [XAUUSD ▾] [M15 | H1 | H4 | Session] [TV ↗] [UTC/User time]

 [Current price]   [Volatility regime]   [Data freshness]   [Sample / Model]

 ┌───────────────────────────── ЦЕНОВОЙ ГРАФИК ──────────────────────────────┐
 │ Реальные свечи из нашей базы; вправо прогнозный fan: 50/80/90/95%          │
 │ Вертикальная линия момента прогноза; уровень anchor; нижняя/верхняя границы│
 │ Отмечены прошлые прогнозы и реальные исходы, без перерисовки истории      │
 └───────────────────────────────────────────────────────────────────────────┘

 [90% range: Lower--Upper] [80% range] [Expected up/down excursions]
 [P(close > anchor): only if validated] [P(touch chosen price): only if validated]

 ГОРИЗОНТ И ВАЛИДНОСТЬ
 Прогноз выпущен: timestamp | окно: от--до | источник данных | задержка
 Backtest calibration vs Forward calibration | 90% coverage | N | width baseline

 МОЙ СЦЕНАРИЙ
 [Long/Short] [Entry] [TP] [SL] [time horizon] [Evaluate]
 P(TP touched), P(SL touched), P(TP first): if validated & path observable
 Expected R net of cost (if supported); conditional warnings

 [Открыть TradingView] [Сохранить сценарий] [Посмотреть историю прогнозов]
```

**Приоритет интерфейса:** первыми видны только данные, которые могут изменить решение о входе, выходе или отказе от сделки. Никаких «AI confidence 97%» без проверенного определения и статистики.

### Страница №2 — `Исследования`

Пользователь может без программирования:

1. Выбрать инструмент и качество/поставщика данных.
2. Выбрать постановку задачи: range, close, touch, TP-before-SL.
3. Выбрать горизонт, feature group, baseline, модель, доступный датасет, train/validation/test.
4. Нажать `Запустить эксперимент`, получить state/progress, метрики и графики по времени.
5. Сравнить с заранее назначенным baseline **на одних и тех же timestamps**.
6. Открыть журнал feature versions, data quality, ошибки, параметры, seed и версии кода.
7. Нажать `Кандидат в production`: система запускает acceptance gates; ручное утверждение допускается только с отображаемым статусом подтверждения и без стирания результатов провала.

### Страница №3 — `История прогнозов`

Таблица прогноза до факта, самого факта, ошибки и interval widths с фильтрами instrument/horizon/model/date/regime. Визуализация `calibration over time`, `coverage by regime`, `interval score vs baseline` и версия data. Клик по прогнозу открывает график именно на исходный момент; система не должна «перерисовывать прошлые прогнозы» новым model version.

### Страница №4 — `Данные / Контроль`

Показывать percent coverage M1, timestamp последней свечи, gaps, CSV source mapping, invalid rows, webhook failure count, источник времени, все instrument calendars, лицензионные условия/возможность экспорта; кнопки `Импорт CSV`, `Пересчитать aggregated bars`, `Сверить источники`, `Скачать журнал ошибок`.

### Страница №5 — `Модули` (пока заглушка со статусом planned)

Отдельные адаптеры для Polymarket, календаря CPI/FOMC/NFP, опционы IV/skew, news NLP. Любой внешний источник должен иметь `available_at`, source/revision quality, свою hypothesis и backtest incremental value. Отображать влияние на P-range/P-event только после честного `base vs base+external` OOS. Никакой внешней вероятности вроде «Polymarket 80% вверх → long» без учёта определения event, strike и expiry.

### Статусы достоверности

`DEMO`, `INSUFFICIENT_DATA`, `COLLECTING`, `BACKTEST_ONLY`, `PAPER_VALIDATING`, `VALIDATED`, `DRIFT_WARNING`, `DATA_STALE`, `MODEL_REJECTED`, `NO_FORECAST`. Для `NO_FORECAST` на графике не показывать якобы реальные будущие bands.

---

## 9. СЦЕНАРНЫЙ КАЛЬКУЛЯТОР И РИСК

Входы: `direction`, `entry`, `tp`, `sl`, `max_holding_minutes`, `execution_source`, `spread`, `commission`, `slippage`, `position_size` (в необязательном позднем режиме), `decision_timestamp`.

Выходы:

- `P(touch TP before horizon)` и `P(touch SL before horizon)` — если обучена/проверена модель касаний.
- `P(TP first | TP or SL is hit)` / `P(neither)` / `P(both within same M1)` — **только** для моделей или симуляций с достаточной внутрибараной историей. M15 OHLC не определяет последовательность достижения уровней. Если одновременное касание в M1 — ambiguous, не записывать его как win автоматически; исключение только при разрешённой tick reconstruction.
- `expected R` только из полного распределения исходов с учётом time exit, spreads и costs; не выводить его из «90% range».
- `out-of-sample comparisons` с/без range model на идентичных событиях; matched-random abstention filter для контроля пропуска сделок.

**Никакого auto-order execution в MVP.** Алгоритм не вправе делать сделки вместо человека. В будущем интеграция с брокером отдельным модулем, безопасно и с явным разрешением.

---

## 10. СТАБИЛЬНЫЙ API (версии /v1)

### Ingest

- `POST /v1/imports/tradingview-csv` — загрузка CSV, source/profile/calendar mapping; возвращает job id и отчёт.
- `POST /v1/webhooks/tradingview` — приём финализированной свечи, быстрая запись, `202`, дедупликация.
- `GET /v1/ingestion/health` — freshness, gaps, duplicates, source quality.

### Market/Forecast

- `GET /v1/instruments`
- `GET /v1/bars?instrument_id=...&timeframe=...&from=...&to=...`
- `GET /v1/forecasts/latest?instrument_id=...&horizon=...&mode=...`
- `GET /v1/forecasts/history?...`
- `GET /v1/forecasts/{forecast_id}/outcome`
- `POST /v1/scenarios/evaluate` — принять explicit `as_of` и уровни; не переписывать предсказание.

### Research

- `POST /v1/experiments` — создать проверяемый run.
- `GET /v1/experiments/{run_id}` — параметры, artifact links, scores.
- `GET /v1/model-registry` — модели и основания статуса.
- `POST /v1/models/{model_id}/request-deployment` — запуск валидации/gates, без автоматического скрытого внедрения.
- `GET /v1/quality/report` — data+forecast quality.
- `GET /healthz` / `GET /readyz` — инфраструктурный health.

Структуры всех ответов зафиксировать в OpenAPI; идентификаторы и timestamps не должны изменяться между перезапусками. API должен поддерживать пагинацию и ограничение максимального объёма ответа.

---

## 11. PINE SCRIPT v6 — АГЕНТ ДОЛЖЕН ПОДГОТОВИТЬ ОТДЕЛЬНЫЙ ГОТОВЫЙ СКРИПТ

Требования к `tv_bar_exporter.pine`:

1. Запуск на обычных свечах `1m`.
2. Сообщение JSON `schema_version`, `event_type=bar_closed`, `source`, `symbol=syminfo.tickerid`, `interval=timeframe.period`, `bar_open_ms=time`, `bar_close_ms=time_close`, open/high/low/close/volume (JSON `null` для отсутствующего объёма).
3. Отправлять `alert(..., alert.freq_once_per_bar_close)` только на подтверждённом реальном завершении свечи, без повторной посылки исторических свечей. Обязательные guards `barstate.isrealtime` + `barstate.isconfirmed`.
4. Строго протестировать JSON на разных инструментах; внутри JSON не должно быть `NaN` и пользовательских секретов.
5. Документировать ручное создание Alert из Pine (алерты TV — отдельные snapshots настроек и могут требовать пересоздания при изменении скрипта).
6. Документировать возможный delay/lost event. Часть real-time data не восполняется автоматически TV; для постоянного потока понадобится дополнительный профессиональный источник.
7. Подготовить тест webhook delivery и replay/idempotency.

**Security:** endpoint с TLS, проверка IP отправителей по официальным документам TV и rate limit, не хранить ключи к брокеру в TV. Нельзя рассчитывать на секрет в теле payload как криптографическую аутентификацию, которой TradingView не предоставляет.

---

## 12. СТРУКТУРА РЕПОЗИТОРИЯ

```text
quant-research-lab/
  README.md
  docs/
    ARCHITECTURE.md
    DATA_CONTRACT.md
    MODEL_CARD_TEMPLATE.md
    RESEARCH_PROTOCOL.md
    SECURITY.md
    RUNBOOK.md
    CHANGELOG.md
    ACCEPTANCE.md
  backend/
    app/
      api/
      config/
      db/
      connectors/
        tradingview_csv.py
        tradingview_webhook.py
        generic_csv.py
        broker_data_adapter.py
      data_quality/
      resampling/
      features/
      labels/
      models/
        historical_baseline.py
        ewma_baseline.py
        har_quantile.py
        lightgbm_quantile.py
        calibration.py
      forecast/
      evaluation/
      experiment_registry/
      scenario/
      services/
    tests/
  frontend/
    src/
      pages/Market.tsx
      pages/Research.tsx
      pages/ForecastHistory.tsx
      pages/DataQuality.tsx
      pages/Modules.tsx
      components/
      api/
  tv/
    tv_bar_exporter.pine
    SETUP.md
  notebooks/
  configs/
    instruments.yaml
    calendars.yaml
    model_policy.yaml
  scripts/
    start_windows.ps1
    start_linux.sh
    import_csv.py
    run_quality_check.py
    train_baseline.py
    verify_acceptance.py
    backup.py
  tests/fixtures/
  data/             # gitignored: raw / clean / feature / forecast artifacts
  models/           # gitignored: model snapshots + hashes
  reports/          # tracked metadata / generated artifacts
  .env.example
  .gitignore
```

Обязательно предоставить понятную инструкцию по настройке Python/Node, виртуального окружения, CSV импорта, выбору TV символа, первому запуску, повторному запуску, резервным копиям и устранению проблем. Исходный код без запускаемого прототипа — не выполненное ТЗ.

---

## 13. ЭТАПЫ РАЗРАБОТКИ И ПРИЁМКИ

### ЭТАП 0 — Основа проекта (1–3 рабочих дня)

Создать репозиторий, backend/frontend, конфигурацию, `README`, health endpoint, тесты и скрипт запуска. Создать sample synthetic fixtures **явно помеченные DEMO**.

**Готово, если:** один скрипт запуска поднимает backend и UI; тесты проходят; в UI демонстрационные значения не выглядят как живые прогнозы.

### ЭТАП 1 — TradingView CSV + Raw Data + Quality (3–6 дней)

Подключить CSV import, preview колонок, mapping на UTC/canonical ID, регистрацию источника, сырой архив, нормализацию, quality tests и M1→M15/H1/H4. В UI включить Data Quality и реальные исторические свечи.

**Готово, если:** произвольный валидный тестовый CSV импортируется; повторный импорт не дублирует; gaps/аномалии видны; агрегация сравнима с вручную вычисленной; 100% исходных raw данных сохраняется.

### ЭТАП 2 — Исторические распределения и baseline (4–7 дней)

Реализовать labels excursions, baseline по сессиям/time-of-day, исторический walk-forward без leakage и forecast journal. Сделать генерацию архивных simulated forecasts и отделить их от настоящих live-issued.

**Готово, если:** baseline выдаёт реальные lower/upper bands на XAUUSD/NAS100 там, где достаточно данных; ни одна фича не использует будущего; coverage/width честно вычислены; 90%-интервал не объявляется реальной вероятностью без оценки калибровки.

### ЭТАП 3 — Дашборд для ручной торговли (4–7 дней)

Реализовать Market и Forecast History, Lightweight Charts, actual past bars, прогнозный fan, as-of timestamp, PDF/CSV export reports если нужен позже, кнопка TradingView, индикаторы качества, объяснение статистики на русском.

**Готово, если:** менее чем за 15 секунд на локальной машине пользователь способен увидеть прогноз и его качество по выбранному рынку; ясно различимы HISTORICAL/DEMO/LIVE; нет выдуманных вероятностей и отсутствующих данных.

### ЭТАП 4 — Webhook + непрерывная запись (3–7 дней)

Pine exporter + webhook, проверка JSON, HTTPS ingress, retries/queue, дедупликация, health, stale alerts, reconciliation, demo setup.

**Готово, если:** в тесте из 100 валидных отправленных webhooks backend сохраняет каждый фактически доставленный event ровно один раз; пропущенные события не скрываются; при перезапуске нет потери уже подтверждённого raw; если источник нестабилен — показывается `DATA_STALE`.

### ЭТАП 5 — Модели-кандидаты и исследования (7–14 дней)

HAR-like quantile, LightGBM quantile, rolling calibration, registry, notebook cross-check, walk-forward, сравнение score с baseline, model acceptance policy.

**Готово, если:** каждый experiment можно повторить из run_id на исходном snapshot; training/test не пересекаются незаконно; победа модели не заявлена без OOS; нет silent production deployment.

### ЭТАП 6 — TP/SL Scenario Lab (5–9 дней)

Вероятности отдельных касаний, path-dependent probability в пределах доступного разрешения, ambiguous events, costs, scenario log, сравнение trade/no-trade с базой.

**Готово, если:** при одновременном касании TP и SL внутри одной M1 свечи исход `AMBIGUOUS`; expected R не выводится при нехватке реальных данных; scenario export не содержит поддельного backtest результата.

### ЭТАП 7 — Forward validation (минимум несколько недель реального времени)

Начать собирать реальные immutable predictions и outcomes; следить за calibration, drift, monthly reports. Никаких утверждений о profitability до накопления достаточной независимой выборки.

**Готово, если:** временные метки доказывают, что прогноз существовал до будущих данных; исправление прошлой цены/модели не переписывает прогнозы; эксперт может воспроизвести любой оценённый прогноз по `forecast_id`.

### Будущие этапы: необязательные и независимые

8. `Polymarket` — Gamma/CLOB, точные правила контракта, quote timestamps, residual against price/volatility/option probability; инкрементальный paired OOS тест.
9. `Macro/News` — время планового/фактического релиза, первая доступность, ревизии данных и surprise; event study.
10. `Options` — IV/skew/term structure; отдельные корректировки risk-neutral vs physical probabilities.
11. `Execution` — broker integration, paper trading, только с явным переключателем и независимой risk guard.

### Предварительная трудоёмкость

MVP (этапы 0–3) ориентировочно 2–4 недели при последовательной разработке; полноценная версия с live, Research Lab и Scenario Lab — ~6–12 недель плюс период настоящего forward-наблюдения. Это оценка, не обещание срока; исторические данные — главный внешний blocker.

---

## 14. ГОТОВЫЕ ПРИЁМОЧНЫЕ ТЕСТЫ (АВТОМАТИЗИРОВАТЬ)

1. `test_no_future_leakage`: изменение OHLC после `t` не меняет уже созданную feature snapshot / forecast на `t`.
2. `test_prediction_immutability`: существующий forecast не меняется при новой версии модели и импортированной будущей свечи.
3. `test_timezones_dst`: переход на летнее/зимнее время не создаёт двойных candles, календарные окна ожидаемы.
4. `test_resample_vs_reference`: M1→M15/H1/H4 точно совпадает с проверенными ручными расчётами на наборе из минимум 500 известных M1.
5. `test_partial_bar_not_available`: незакрытая свеча не используется в обучении или прогнозе `next_closed_bar`.
6. `test_missing_data_gate`: пропущенные ожидаемые M1 и stale источники блокируют критически зависящие прогнозы.
7. `test_ingest_idempotence`: два одинаковых CSV и дубликат webhook не создают повторных records.
8. `test_joint_interval`: проверяются оба High и Low, а не только будущий Close.
9. `test_ambiguous_stop_take`: случай, когда одна M1 содержит и TP, и SL, не становится автоматически выигрышем.
10. `test_market_alias_basis`: никакая связь CFD/spot/futures не предполагается автоматически.
11. `test_baseline_paired`: baseline и challenger оцениваются ровно на одних forecast timestamps.
12. `test_validation_registry`: ML не публикуется как `VALIDATED`, если fails quality/calibration/OOS gates.
13. `test_late_forecast`: alert или расчёт, пришедший после начала периода, не получает ложную метку «прогноз от открытия свечи».
14. `test_model_version_reproducible`: run_id позволяет получить идентичные labels/metrics из закреплённой версии данных (с допусками машинной арифметики).
15. `test_demo_no_trade`: демо-режим не отдаёт данные в production или broker endpoint.

---

## 15. ДОКУМЕНТАЦИЯ, БЕЗОПАСНОСТЬ И ОПЕРАЦИИ

- `.env.example`, ключи никогда не коммитить; внешний backend недоступен без аутентификации.
- Webhook ingress изолирован от брокерского API, без прав на реальные ордера; rate limiting, size limit, логирование без секретов.
- Резервная копия SQLite + Parquet + config + model artifacts; команда restore с проверкой.
- История моделей, экспериментов и прогнозов — append-only с audit trail.
- Метрические healthchecks: source freshness, backlog, last training, percent missing, running forecast age.
- Не использовать неофициальное извлечение потока TradingView; соблюдать условия лицензии котировок и ограничение распространения/перепродажи.
- Для круглосуточной работы Windows10 с устаревшими обновлениями и открытыми внешними портами не использовать: production ingress лучше вынести на поддерживаемый Linux/VPS.
- В документации отдельная глава `Почему вероятность диапазона не является вероятностью прибыльного входа`.
- Для новых модулей обязательны адаптер + timestamp policy + experimental protocol + holdout + dashboard badge.

---

## 16. ЧТО НЕОБХОДИМО ОТ ПОЛЬЗОВАТЕЛЯ ДЛЯ ПЕРВОГО ЗАПУСКА

1. **Точный TV symbol с префиксом провайдера** для XAUUSD и NAS100 (например формат `PROVIDER:TICKER`, а не произвольный похожий тикер).
2. Один-два **CSV экспортированных файла из TradingView** с доступной историей M1 (либо M15/H1 для прототипа, с честным снижением точности intrabar оценки).
3. Выбранные часы trading sessions, timezone (для отображения), при необходимости broker/prop symbol и тип комиссий.
4. Желательно — источник M1 за 1–3+ года вне TV (при невозможности получить нужную историю экспортом). До этого проект запускается в режиме `DATA_COLLECTION/RESEARCH`, но не утверждает статистическое преимущество.

**Порядок выполнения агентом:** не пытаться разработать всё сразу. На каждом этапе — код + тесты + инструкция запуска + скриншот рабочего приложения + список реальных ограничений. Следующий этап начинать только после завершения предыдущего acceptance test.

---

## 17. ЗАДАНИЕ ДЛЯ АГЕНТА ANTIGRAVITY (КОПИРОВАТЬ В ЧАТ РАЗРАБОТКИ)

> Ты — lead quant developer и full-stack engineer. Реализуй проект Quant Research Lab **строго по ТЗ v1.0**, итеративно. В первую очередь реализуй ЭТАПЫ 0 и 1, не симулируй полноценный результат заранее. Используй Python FastAPI, DuckDB/Parquet, SQLite и React/TypeScript + Lightweight Charts. TradingView — первичная платформа для экспорта CSV и live Alerts; у TradingView нет универсального открытого исторического OHLC API. Никакого неофициального scraping. Разделяй DEMO, BACKTEST и REAL-LIVE. Не допускай look-ahead, data leakage и перезаписи прошлых прогнозов. Покажи реальные логи тестов, запусти локально, объясни мне по-русски, как открыть дашборд и импортировать TradingView CSV. На каждом этапе сначала проверь acceptance criteria и отчитывайся о том, что реально реализовано и что пока отсутствует. Не реализуй автоматическую торговлю без отдельной задачи.

---

## 18. ОРИЕНТИРЫ ДЛЯ ИССЛЕДОВАТЕЛЬСКОГО ЯДРА

- Engle (1982), *Autoregressive Conditional Heteroscedasticity* — условная дисперсия финансовых временных рядов.
- Bollerslev (1986), *Generalized Autoregressive Conditional Heteroskedasticity* — GARCH.
- Corsi (2009), *A Simple Approximate Long-Memory Model of Realized Volatility* — HAR-RV, DOI: `10.1093/jjfinec/nbp001`.
- Koenker & Bassett (1978), *Regression Quantiles* — quantile regression.
- Conformal prediction for time series, включая EnbPI: theory has additional assumptions, **не обещать гарантии IID-coverage финансовому рынку**.
- TradingView официальные документы: ссылки в разделе 1.
- TradingView Lightweight Charts: https://www.tradingview.com/lightweight-charts/
- Polymarket разработчикам (будущий модуль): https://docs.polymarket.com/

---

### ФИНАЛЬНОЕ ПРАВИЛО ПРОЕКТА

**Если Quant Research Lab не может доказать, что прогноз был сделан до начала предсказываемого события и честно оценён после его завершения, этот прогноз не допускается в торговый дашборд как проверенный.**
