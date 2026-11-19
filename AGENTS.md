# Квант лаб

Проект: Quant Research Lab. Прочитай README.md, docs/ACCEPTANCE.md и docs/RESEARCH_PROTOCOL.md перед изменениями; полное исходное ТЗ — docs/SPEC_v1.md. GitHub-first адаптация и реально завершённые этапы описаны в README, не подразумевай выполнение всех будущих модулей.

Публичная v0.3 — browser workspace (frontend/src/engine): CSV + Worker + IndexedDB, протокол docs/BROWSER_PROTOCOL_V3.md. Python v1 — дополнительный локальный инструмент. Открытый reference-архив EV Trading Labs 2024–2025 включён в Pages с видимой атрибуцией: см. docs/DATA_ARCHIVE.md. Это исключение не распространяется на личные CSV и другие источники. Не добавляй чужие данные без права публикации. При отказе провайдера показывай реальную ошибку, без DEMO. До заявления успешного подключения проверь ответ источника и фактические даты/цены.

- Сохраняй разделение DEMO, historical simulation и настоящих заранее выпущенных прогнозов. Не меняй issued_at/available_at задним числом.
- Не допускай будущих данных в features/training/calibration. Не называй симуляции live/forward, диапазон — торговой вероятностью, а небольшой OOS — доказанным преимуществом.
- Raw, dataset snapshots, forecast/outcome/experiment journals неизменяемы. Повторный импорт идемпотентен; конфликтующие свечи не исправляются молча.
- Не подставляй provider symbol, календарь, фьючерсный proxy или право публикации вместо пользователя. Закрытые данные и секреты не попадают в public repo/Pages/lab-state.
- Нет auto-order execution. Новые внешние признаки/ML проходят отдельный заранее заданный OOS-протокол.
- Проверки: ruff check backend scripts; pytest -q; npm --prefix frontend test; npm --prefix frontend run build. При изменении формата данных/исследования обновляй schema/model/protocol version и документацию.
- Pages — статическое приложение с browser research; непрерывный feed и webhook требуют отдельного сервиса. В режиме NO FORECAST не показывай якобы реальные будущие bands.
