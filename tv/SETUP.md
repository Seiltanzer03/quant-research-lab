# Pine M1 exporter — подготовка будущего live-этапа

**В v0.1 webhook receiver отсутствует. GitHub Pages не может принять alert.** Скрипт подготовлен по контракту ТЗ; компиляция и доставка в настоящем TradingView пока не проверены. Не указывай URL Pages как webhook.

Когда будет реализован и испытан HTTPS receiver:

1. Выбери точный source symbol и обычные свечи 1m. Открой Pine Editor, вставь `tv_bar_exporter.pine`, скомпилируй и добавь на график.
2. Создай Alert: условие **Any alert() function call**. Webhook URL — проверенный HTTPS receiver на 443. Для webhooks у аккаунта TradingView требуется 2FA.
3. После изменения скрипта/настроек пересоздай Alert: TradingView сохраняет snapshot на момент создания.
4. Проверь настоящий JSON на инструменте с/без volume. Сообщения должны содержать null вместо NaN, только окончательные realtime M1, без исторического replay и секретов.
5. На receiver проверь 100 доставленных сообщений и повторов: каждый event один раз, raw durable до ответа 202; задержки/потери явно видны. При одновременной/повторной доставке сохраняется idempotency.

TradingView alerts могут задерживаться/теряться, исторический replay автоматически не даётся. Закрытие свечи иногда определяется только новым обновлением. Это не полноценный гарантированный datafeed.

Официальные документы: [alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/), [bar states](https://www.tradingview.com/pine-script-docs/concepts/bar-states/), [webhooks](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/).
