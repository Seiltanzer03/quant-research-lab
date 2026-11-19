# Приёмка v0.1 — 19.11.2026

Это GitHub-first адаптация первых этапов исходного ТЗ, не реализация всех 18 разделов. Готовый запуск не означает подтверждённую рыночную модель.

| Часть | Реальное состояние |
|---|---|
| Основа Python / React / OpenAPI | Реализована, локальный health endpoint и UI production build проверены |
| Импорт CSV / raw / UTC / дедупликация | Реализованы, покрыты автоматическими тестами |
| Календари / DST | Настраиваемые weekly sessions, holiday closures и overrides; автоматической сверки брокера нет |
| OHLC агрегация | M15/H1/H4, полные UTC-окна, проверка по независимому ручному reference |
| Два baseline / историческая оценка | Реализованы; только историческая симуляция, DEMO по умолчанию |
| Joint coverage / score / paired bootstrap | Реализованы; экономический edge не заявлен |
| UI исследования / журнал / данные | Реализованы; CSV preview локален браузеру, полное сохранение — CLI/API |
| GitHub Actions / Pages | Workflow и persistence подготовлены; удалённый запуск должен быть подтверждён зелёным workflow |
| Безопасность raw/журналов | Версии Parquet + raw hash, SQLite UPDATE/DELETE triggers; администратор файла технически может обойти |
| Настоящие заранее опубликованные прогнозы | 0, отсутствуют |
| Pine exporter | Подготовлен; компиляция/доставка в TradingView не проверены |
| Webhook / VPS / live forecast | Не реализованы |
| HAR, LightGBM, PIT, direction/touch probabilities | Не реализованы |
| D1/Session / нестандартные anchors | Не реализованы; только фиксированная UTC-сетка |
| Полный Scenario Lab / expected R | Не реализованы; только проверка геометрии RR и исторический ambiguous classifier |
| Windows native запуск | Скрипт подготовлен, нативная Windows-проверка не проведена |

Автотесты проверяют: no future leakage; append-only predictions; timezone/DST; reference resampling для 15/60/240 минут на 960 M1; незакрытые свечи; missing bars; CSV replay; whole-candle interval; same-M1 TP/SL ambiguous; отсутствие автоалиасов; совпадение timestamps B0/B1; no promotion из DEMO/backtest; late forecast rejection; воспроизводимость run id/metrics; запрет unsupported probabilities и implicit public export.

Webhook acceptance (100 доставок), настоящий forward, график live-качества и broker execution не проходят приёмку в этой версии: соответствующих модулей ещё нет.

Локальные результаты исходной проверки: **25 Python tests passed**, **3 frontend tests passed**, `ruff check` и TypeScript/Vite build прошли. Актуальные результаты смотри в CI соответствующего commit; этот текст не заменяет удалённый зелёный запуск.
