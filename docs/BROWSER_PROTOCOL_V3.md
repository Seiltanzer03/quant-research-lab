# Browser research protocol v3

Версия моделей `browser_ranges_v3`, схема отчёта 2.1. Профиль + normalized OHLC → SHA-256 snapshot; параметры сохраняются с отчётом. Движок frontend/src/engine работает в Web Worker.

M1/M5/M15/H1 CSV: UTC-сетка обязана совпадать с timeframe. Naive non-UTC timestamps отклоняются, DST не угадывается. Будущие/неполные свечи исключаются. Идентичные дубли идемпотентны, конфликт цены/объёма отклоняется. Пропуски не интерполируются. Агрегация требует полного количества баров, правильных начала/конца и принадлежности подтверждённому недельному календарю. Для CSV неподтверждённый UTC-календарь не отсекает наблюдаемые бары; пустые слоты не классифицируются как ошибки источника, coverage по торговым сессиям не заявляется.

Sample next native bar: anchor — предыдущий закрытый исходный бар, target — полный UTC-бар. EWMA прошлых close returns alpha=.06; через gaps returns не рассчитываются, дисперсия переносится. Масштаб = sigma исходного timeframe × sqrt(horizon/source timeframe). Изменение будущих OHLC не меняет предыдущий прогноз.

B0: долевые UP/DOWN excursions; B1: excursions/sigma_known_at_anchor. Последние lookback samples (1000 по умолчанию). Группа UTC-hour при min_train (100), иначе pooled. Для joint confidence c маргинальные quantiles = `1 - (1-c)/2`, higher quantile. Попадание проверяется по обоим Low/High. Нижняя граница ограничена нулём.

Chronological 60/20/20. Fit не использует label end после simulated as_of. Пользовательский rerun параметров создаёт отдельный experiment; просмотренный период не становится новым «нетронутым» test. Окна одного горизонта не пересекаются.

Score: width + 2/alpha × (max(lower−actualLow,0) + max(actualHigh−upper,0)), к anchor в bps. Это whole-candle envelope score, не scalar-close interval score. Pinball — сумма UP/DOWN для q=.95. Парный B0−B1 на одинаковых timestamps; UTC-day block bootstrap, seed42, 400 повторов, минимум 5 блоков для CI. Разрезы режимов/часов/месяцев отдельно. Метрики не дают trading approval.

Forward paper: available_at/issued_at = реальный Date.now, start — следующий UTC boundary строго после окончания расчёта. Anchor — последняя закрытая M1. Lead = start−anchor_close; обучающие окна используют такой же lead, labels известны до issue. M1, проверенная недельная сессия, age≤3m и непрерывные последние 240m обязательны. Outcome требует все M1 окна. Forecast/outcome — разные IndexedDB stores, add-only; существующее значение не заменяется. Внешнего timestamp authority нет: владелец может изменить часы/базу браузера. Это личный журнал, не audited external publication.

Scenario replay (исходное разрешение сохраняется): Entry/TP/SL применяется к последним lookback непересекающимся окнам. Масштабирование current_sigma/sample_sigma одинаково для всех цен окна. Entry — цена уже открытой позиции; pending entry не моделируется. Первое совместное касание TP/SL внутри исходной свечи = AMBIGUOUS. Границы среднего R: все ambiguous SL…все TP. Neither = time exit по close горизонта. Cost_points/risk вычитается однократно; реальная bid/ask/margin/gap-fill модель не заявлена. CI относится к пессимистичной границе. Частоты исторические, не validated future probabilities.

Сырые CSV сохраняются до разбора в raw_imports. Sources добавляют бары, не удаляя прежние; reports — latest pointers, experiments — неизменяемые результаты. Backup/restore не перезаписывает journal ids. Исключение: открытый лицензированный архив EV Trading Labs 2024–2025 с атрибуцией поставляется вместе с приложением. Личные CSV и журналы в public main/Pages не попадают. Experiment id включает schema и Git SHA, не только данные/параметры.
