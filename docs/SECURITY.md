# Безопасность и границы доступа

Ключи не нужны для DEMO и локального CSV. `.env`, `data/`, SQLite, node_modules и model/data outputs исключены из `main`. Проверяй `git status` перед публикацией входных CSV. Только явный `publish_allowed=true` разрешает экспорт набора в public build.

Pages — публичный статический сайт. На нём нет приватного backend, broker API, произвольного выполнения экспериментов или токенов в JavaScript. CSV preview не отправляет файл на сервер. Локальный API в стартовых скриптах слушает 127.0.0.1; **не выставляй его наружу без добавления аутентификации и защиты загрузок**.

Профили Pydantic ограничивают поля/значения; import size limit 25 MiB; OHLC/время проверяются. Пути snapshot конструируются из hash, а DuckDB получает путь связанным параметром. Журналы append-only на уровне SQLite-триггеров; это не защищает от администратора с полным доступом к файлу. Контроль прав GitHub и резервные копии остаются важны.

Рабочие процессы получают необходимые contents/pages/id-token permissions; PR CI только contents:read, workflow не использует pull_request_target. Не помещай секреты в CSV/profile, Pine payload или URL. Actions state и recovery artifact в публичном репозитории не считаются приватным хранилищем.

Webhook пока **не реализован**. Pine не даёт криптографически подписанного feed. Будущий ingress требует TLS, официального IP allowlist, rate/size limits, быстрой durable записи и worker. Его нельзя просто добавить как публичный незащищённый endpoint локального API. Автоисполнение отсутствует.
