# Приёмка v0.2 · 19.11.2026

| Возможность | Реальное состояние |
|---|---|
| Полный CSV import на Pages | Raw/normalize/QA/Worker research/IndexedDB; без Python и коммитов |
| B0/B1 M15/H1/H4 в браузере | Реализованы, нет синтетического fallback |
| Даты/параметры/запуск/отмена | Реальные операции; завершённые experiments сохраняются |
| Диапазоны/coverage/score/paired bootstrap | Реализованы; source/params/snapshot закреплены |
| TP/SL scenario | M1 replay с costs, time exit, ambiguity bounds и day-block CI |
| Личный forward-журнал | Freshness/gaps/late gates; часы браузера не являются независимой публикацией |
| Backup/restore | IndexedDB backup; прогнозы не заменяются |
| Автозагрузка Dukascopy | Прямой коннектор; серверные проверки дали HTTP429. В опубликованном приложении также получена ошибка источника; реальное онлайн-подключение не подтверждено |
| Недельные часы Dukascopy | Из официального календаря, праздники отдельно |
| Демо/Modules/Session-заглушки | Удалены из интерфейса |
| 24/7 без вкладки/VPS | Нет; постоянный серверный feed не заявлен |
| Trading expectancy / audited validation | Не доказаны; статусы не присваиваются |

Тесты нового ядра: JSONP parsing без eval; exact symbols/no aliases; UTC/DST; partial bars; conflicting duplicates; reference aggregation; gaps; no future leakage; whole-candle coverage; paired timestamps; explicit-lead future issuance; stale/gapped rejection; append-only paper; source append без truncation; repeat-run immutability; same-M1 ambiguity; cost/time exit; short-page pagination; no fallback после HTTP429.

Build and Pages и Checks для a98286f838ef252b9cc269b24668b7bf850499b9 завершились успешно. Локально: 25 Python + 19 frontend tests, production build. Импорт личного архива GC_F/NQ_F H1 проверяется отдельно на опубликованном сайте. Source connectivity сохраняет фактический отказ поставщика.
