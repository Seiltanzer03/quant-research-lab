# Эксплуатация

## Обычные операции

- Start: `scripts/start_windows.ps1` либо `bash scripts/start_linux.sh`.
- Import: `python -m backend.app.cli import --csv file.csv --profile file.profile.json`.
- QA: `python -m backend.app.cli quality`.
- Rebuild: `python -m backend.app.cli build`. `--auto-demo` создаёт демо только при пустой базе; реальные данные не подменяются молча.
- Public build: `python -m backend.app.cli build --inputs inputs --auto-demo --public`.

Обёртки используют Python из `.venv`. Для команд вручную активируй окружение или укажи полный путь к его интерпретатору. API: `/healthz`, `/readyz`, `/docs`; `/v1/forecasts/latest` возвращает NO_FORECAST.

## Pages и расписание

Settings → Pages → GitHub Actions. Первый push запускает `Research and Pages`. Ручной запуск в Actions. Расписание каждые 6 часов, minute 17 UTC. Исследования на одном snapshot дедуплицируются. Batch не скачивает новые котировки автоматически.

Состояние хранится в `lab-state`, не в Actions cache. Git checkout использует штатный ограниченный GITHUB_TOKEN. При сбое восстановление не начинает новую пустую базу. При конфликте push нет force; запускай workflow заново после разбора причины. Ветка `lab-state` не запускает research рекурсивно: trigger только `main`.

Архив рассчитан на пилот. При файле >80 MiB persistence останавливается до git push; перенеси хранение на VPS/object storage, не удаляя историю. 14-дневные artifacts не являются единственной резервной копией. Не используй репозиторий как неограниченное озеро данных.

## Резервная копия и восстановление

Останови локальный API и расчёты. Скопируй целиком `data/` вместе с SQLite WAL/SHM, если они остались, и свои profiles/configs. Либо используй SQLite backup API и копируй все snapshots/raw при отсутствии параллельных писателей. Сохраняй commit SHA и lock-файлы.

Для restore скопируй архив в пустую `data/`, запусти SQLite `PRAGMA integrity_check`, затем `python -m backend.app.cli quality` и `build`. Не восстанавливай поверх работающего писателя. На GitHub клонируй `lab-state`: папка `state/` является аналогом локальной `data/`.

## Диагностика

| Проблема | Проверка и действие |
|---|---|
| Нет dashboard.json | Выполни `build --auto-demo`, проверь вывод Python, затем frontend |
| На Pages ошибка 404 | Source=GitHub Actions; research/deploy job зелёный; ссылка в Summary |
| На Pages остались старые цифры | Сравни время snapshot; проверь новые inputs, raw hash и workflow; обнови страницу |
| После CSV нет новой модели | Проверь полные окна, минимум 180 labels, timeframe, календарь и gaps |
| HISTORY_INCOMPLETE | Подтверди источник/лицензию/календарь; не меняй verified ради зелёного badge |
| DATA_CONFLICT | Цены уже импортированной свечи изменились; создай явную версию источника, raw сохранён |
| Timezone/DST error | Используй epoch либо ISO с UTC-offset; уточни единицы s/ms |
| Schedule не запускается | Проверь ветку main, Actions settings и отключение после 60 дней без активности |
| API недоступен | Локальный порт 8000, процесс uvicorn, LAB_DATA_DIR; Pages API не содержит |
| 80 MiB limit | Перенеси архив на постоянное хранилище; код и Pages могут остаться в GitHub |

Начальный UI не запускает произвольный код из браузера и не хранит GitHub token. Ссылка «Запустить расчёт» открывает штатный Run workflow в GitHub.
