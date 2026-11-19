# Открытый архив · 19.11.2026

Источник и лицензия: https://evtradelabs.com/data — страница открыто предлагает закрытые годы M5/M15/H1/H4/D1 без регистрации и указывает «License: free use with attribution to EV Trading Labs». Видимая атрибуция есть в рабочем кабинете. Текущий год и M1 требуют аккаунта; они не скачаны и ограничения не обходятся.

Скачаны штатными кнопками Download: XAUUSD/M5/2024.json.gz, XAUUSD/M5/2025.json.gz, NQ/M5/2024.json.gz, NQ/M5/2025.json.gz. Файлы сохранены байт-в-байт как frontend/public/quotes/*.bin, чтобы HTTP не декодировал gzip дважды. SHA-256, число записей и точные границы — frontend/src/engine/archive-manifest.json. Сборка и браузер проверяют checksum. Исходные файлы не корректируются.

Формат источника: массив объектов ts/o/h/l/c/ao/ah/al/ac/v. ts — open time Unix UTC seconds; o/h/l/c — Bid; ao/ah/al/ac — Ask. Исследовательское ядро использует Bid и v, а не смешивает стороны. Поставщик описывает эти файлы как resample Dukascopy M1; собственный инструмент пользователя и исполнение его брокера не отождествляются с архивом.

| Canonical group | Точный dataset symbol | Класс |
|---|---|---|
| XAUUSD | EVTL:XAUUSD | Spot gold reference |
| NAS100 | EVTL:NQ | Nasdaq 100 reference, Dukascopy-derived CFD |

NQ — имя набора EV Trading Labs; CME NQ futures не подставлены. Отдельные CSV GC_F/NQ_F остаются отдельными инструментами. Календарь архива не подтверждён, gaps не заполняются. Данные исторические 2024–2025, не текущие. Возможные ошибки upstream не устраняются молча.

Исключение для открытой reference-истории не даёт права публиковать личные CSV или данные других источников. У них publish_allowed=false.
