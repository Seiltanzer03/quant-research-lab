# Квант лаб · Quant Research Lab

Первая работающая версия исследовательской лаборатории на **GitHub + Actions + Pages + DuckDB/Parquet**. Интерфейс на русском, начальные инструменты — XAUUSD и NAS100.

**v0.1 — исследовательский прототип.** По умолчанию используются только синтетические данные с заметной меткой DEMO. Ни одного проверенного рыночного прогноза или доказанного торгового преимущества проект пока не заявляет.

## Что уже работает

- Python 3.12 / FastAPI: локальный API, импорт TradingView CSV, неизменяемый raw-архив, дедупликация, отклонение конфликтующих свечей, UTC и явные профили источников.
- Parquet: версионированные наборы свечей; DuckDB: чтение и выборки; SQLite WAL: метаданные, append-only журналы прогнозов, исходов и экспериментов.
- Полные M15/H1/H4 из закрытых исходных свечей. Пропуски не заполняются вымышленными ценами.
- Два заранее заданных baseline: сезонные эмпирические квантили и масштабирование по прошлой EWMA-волатильности.
- Хронологическая симуляция 60/20/20, совместное покрытие High/Low 50/80/90/95%, ширина, whole-candle score, pinball loss, разрезы по режиму/месяцу/часу и парный bootstrap по дням.
- React + TypeScript + Lightweight Charts: рынок/архив, исследования, журнал, качество данных, локальный импорт CSV и калькулятор геометрии TP/SL.
- CI, публикация в Pages, ручной запуск и расписание каждые 6 часов; отдельная ветка `lab-state` для сохранения небольшого исследовательского архива.

Вкладка «Сейчас» честно показывает **NO FORECAST**. Вкладка «История» показывает симуляции с фактическим временем их расчёта. Историческая дата `as_of` никогда не выдаётся за реальную дату выпуска.

## Открыть в браузере через GitHub

1. В новом публичном репозитории открой **Settings → Pages → Build and deployment → Source → GitHub Actions**.
2. Открой **Actions → Research and Pages → Run workflow**. Первый push в `main` также запускает сборку.
3. После зелёного результата ссылка на сайт появится в Summary запуска и Settings → Pages.

Actions запускается в **00:17, 06:17, 12:17, 18:17 UTC** — **03:17, 09:17, 15:17, 21:17 по Москве**. Запуск бывает с задержкой; SLA для M15/H1 нет. После 60 дней без активности GitHub может отключить schedule в публичном репозитории.

Непрерывного подключения к рынку в этой версии нет. Без новых CSV расписание повторяет исследование того же snapshot; это не новые наблюдения и не новые live-прогнозы. Эксперименты и прогнозы дедуплицируются.

Источники ограничений: [расписания Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).

## Локальный запуск на Windows

Установи [Python 3.12](https://www.python.org/downloads/) и [Node.js 24 LTS](https://nodejs.org/). При установке Python включи Python Launcher и добавление в PATH. Открой PowerShell в папке проекта:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

Открой **http://127.0.0.1:5173**. API/OpenAPI: **http://127.0.0.1:8000/docs**. Первый запуск устанавливает зависимости и рассчитывает DEMO; повторный использует сохранённый архив. Ctrl+C останавливает frontend; скрипт завершает свой API-процесс.

`-ExecutionPolicy Bypass` применяется только к этому запуску PowerShell, не меняет постоянную политику компьютера. Скрипт можно предварительно открыть и проверить.

Linux/macOS:

```bash
bash scripts/start_linux.sh
```

На macOS нужен установленный `python3.12`. Windows-скрипт подготовлен, но нативный запуск на Windows в среде разработки не проверялся.

## Подключить свои данные

1. В TradingView выбери **обычные M1-свечи**, точный символ `PROVIDER:SYMBOL` и экспортируй данные через **Export chart data**. TradingView не предоставляет универсальный публичный API многолетней M1-истории.
2. В «Данные и контроль» открой CSV для предварительной проверки. Укажи настоящий символ и скачай профиль. Файл на Pages никуда не отправляется.
3. Проверь профиль: секунды/миллисекунды, timezone для меток без UTC-offset, tick/precision, тип актива/объёма, лицензию, торговый календарь, праздники. Пример в `configs/xauusd.profile.example.json` — шаблон с **непроверенным** календарём, не готовая настройка провайдера.
4. Импортируй локально (Windows):

```powershell
.\.venv\Scripts\python.exe -m backend.app.cli import --csv C:\quotes\gold.csv --profile C:\quotes\gold.profile.json
.\.venv\Scripts\python.exe -m backend.app.cli build
```

На Linux используй `.venv/bin/python` вместо `.\.venv\Scripts\python.exe`. Перезагрузи дашборд после расчёта. Через локальный UI также доступна кнопка импорта; пересчёт исследования выполняется отдельно командой `build`.

Для публичной сборки добавь разрешённые CSV и соседний `*.profile.json` в `inputs/`, укажи лицензию и **явно** `publish_allowed=true`. Файлы и состояние `lab-state` будут публичны. Закрытые или запрещённые к распространению данные используй локально в gitignored `data/`.

## Что пока отсутствует

Постоянный datafeed, webhook receiver, D1/Session, HAR/LightGBM/GARCH, production model promotion, полноценные вероятности касаний/направления и expected R, брокерское исполнение, внешние данные Polymarket/новости/опционы. Pine exporter подготовлен отдельно, но пока не скомпилирован и не проверен в TradingView.

Ни данные DEMO, ни backtest не разрешают автоматически включить торговлю. Пользовательский символ, реальная история и проверенный календарь должны быть заданы отдельно. Разная котировка NAS100/NQ/NDX или XAUUSD/GC не считается одним инструментом.

## Проверки

```bash
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
ruff check backend scripts
pytest -q
cd frontend
npm ci
npm test
npm run build
```

Python-зависимости закреплены в `requirements.lock`, Node — в `frontend/package-lock.json`. `pyproject.toml` задаёт поддерживаемые диапазоны для осознанного обновления.

Подробности: [архитектура](docs/ARCHITECTURE.md), [данные](docs/DATA_CONTRACT.md), [протокол](docs/RESEARCH_PROTOCOL.md), [эксплуатация](docs/RUNBOOK.md), [безопасность](docs/SECURITY.md), [приёмка](docs/ACCEPTANCE.md), [следующие этапы](docs/ROADMAP.md).
