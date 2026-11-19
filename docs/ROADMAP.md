# Следующие этапы

1. Подключить реальный разрешённый M1 CSV для точных пользовательских TV symbols; проверить timezone, лицензию, реальный торговый календарь и качество истории. До этого DEMO не превращается в рынок.
2. Внешний аудит baseline на реальных данных, отчёт по часам/режимам/месяцам, заранее запечатанный новый holdout. Не подбирать правила до получения красивой прибыли на уже просмотренном test.
3. HAR-like и LightGBM кандидаты, отдельные model artifacts/registry/calibration; production approval только после собственного протокола.
4. Постоянный Linux worker/VPS, authenticated dashboard API, durable webhook queue/reconciliation, Pine delivery/replay tests. Только после этого реальные заранее выпущенные прогнозы.
5. Несколько недель/месяцев paper forward, минимум 500 завершённых наблюдений для каждой instrument × horizon × test mode; реально проверить joint coverage и drift.
6. Scenario Lab с наблюдаемой M1-последовательностью TP/SL, costs и time exit. Одновременные касания остаются ambiguous; expected R не выводится из bands.
7. Polymarket, macro/news, options — каждый источник отдельно, со временем доступности и парной проверкой incremental value. Auto-order execution требует отдельной задачи.

GitHub остаётся кодом/CI/research и после появления VPS; Pages может показывать периодические отчёты, а непрерывные задачи выполняются постоянным процессом.
