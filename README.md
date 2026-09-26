# music-bot

Telegram bot for song requests and a driver web panel.

## Notify the driver about new songs

1. Open the bot in a **private** Telegram chat and send `/start`, then `/myid`.
2. Copy the numeric ID returned by the bot. Set `OWNER_TELEGRAM_ID` to this number in the server's environment (or local `.env`). Keep `BOT_TOKEN` in the environment too. Do not commit `.env` or bot tokens to GitHub.
3. Restart the server. Each song successfully added to the queue will trigger a private message to this ID with a YouTube link and an **Відкрити в YouTube** button.

Example `.env` entries (replace placeholders with your own values):

```dotenv
BOT_TOKEN=your_bot_token
OWNER_TELEGRAM_ID=your_numeric_telegram_id
```

Notifications are sent after saving the song. If Telegram delivery fails, the song stays in the queue and the server logs the error. Only the configured ID receives the notification; the bot must already have been started from that account.
