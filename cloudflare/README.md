# Cloudflare Cron deployment

The reliable, free, never-sleeping clock that triggers daily collection.

## Why a Worker that calls the backend
Cloudflare Workers run JavaScript, not Python. Our collectors are Python (FastAPI backend).
So the Worker's only job is: on its cron schedule, `POST /internal/run` on the backend with
the shared secret. The backend runs `collector.run_daily.run_all()` (ninja → build → scraper
→ curate → export).

## Deploy
```bash
cd cloudflare
npm install -g wrangler        # or use npx
wrangler login
wrangler secret put BACKEND_URL          # https://<your-backend-host>
wrangler secret put INTERNAL_RUN_TOKEN   # same value as backend env INTERNAL_RUN_TOKEN
wrangler deploy
```

Test it without waiting for the cron: open the deployed Worker URL in a browser (the `fetch`
handler triggers a run and returns the JSON result).

## Alternative
`.github/workflows/daily.yml` does the same thing via GitHub Actions cron if you'd rather not
run a Worker. Either one is sufficient; don't run both.
