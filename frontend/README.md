# Poker Bot Mini App Frontend

This folder is a static Telegram Mini App frontend. Host these files on any HTTPS static host, then set the bot backend's `MINI_APP_URL` to the hosted `index.html` URL or the folder URL.

Before deploying, edit `config.js`:

```js
window.CHIPS_BOT_API_BASE_URL = "https://your-backend-api.example";
```

That URL must point at the Python backend serving `/api/new-game`.