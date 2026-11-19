# Квант лаб

Проект: Quant Research Lab. Прочитай README.md, docs/ACCEPTANCE.md и docs/RESEARCH_PROTOCOL.md перед изменениями; полное исходное ТЗ — docs/SPEC_v1.md. GitHub-first адаптация и реально завершённые этапы описаны в README, не подразумевай выполнение всех будущих модулей.

- Сохраняй разделение DEMO, historical simulation и настоящих заранее выпущенных прогнозов. Не меняй issued_at/available_at задним числом.
- Не допускай будущих данных в features/training/calibration. Не называй симуляции live/forward, диапазон — торговой вероятностью, а небольшой OOS — доказанным преимуществом.
- Raw, dataset snapshots, forecast/outcome/experiment journals неизменяемы. Повторный импорт идемпотентен; конфликтующие свечи не исправляются молча.
- Не подставляй provider symbol, календарь, фьючерсный proxy или право публикации вместо пользователя. Закрытые данные и секреты не попадают в public repo/Pages/lab-state.
- Нет auto-order execution. Новые внешние признаки/ML проходят отдельный заранее заданный OOS-протокол.
- Проверки: ruff check backend scripts; pytest -q; npm --prefix frontend test; npm --prefix frontend run build. При изменении формата данных/исследования обновляй schema/model/protocol version и документацию.
- Pages — статический snapshot; непрерывный feed и webhook требуют отдельного сервиса. В режиме NO FORECAST не показывай якобы реальные будущие bands.
