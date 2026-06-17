// Cloudflare Worker — daily cron trigger for Project Wraeclast.
//
// Python collectors can't run on Workers, so the reliable raw-collection schedule is a
// Worker cron that calls the FastAPI backend's protected /internal/run endpoint. The heavy
// lifting (ninja, scraper, curate, export) happens in the backend; this is just the clock.
//
// Secrets (set with `wrangler secret put`):
//   BACKEND_URL        e.g. https://your-backend.example.com
//   INTERNAL_RUN_TOKEN must match the backend's INTERNAL_RUN_TOKEN

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerRun(env));
  },

  // Manual trigger for testing: GET the worker URL.
  async fetch(request, env) {
    const result = await triggerRun(env);
    return new Response(JSON.stringify(result), {
      headers: { "content-type": "application/json" },
    });
  },
};

async function triggerRun(env) {
  if (!env.BACKEND_URL || !env.INTERNAL_RUN_TOKEN) {
    return { ok: false, error: "BACKEND_URL / INTERNAL_RUN_TOKEN not configured" };
  }
  try {
    const resp = await fetch(`${env.BACKEND_URL}/internal/run`, {
      method: "POST",
      headers: {
        "x-run-token": env.INTERNAL_RUN_TOKEN,
        "user-agent": "Project-Wraeclast-Cron/0.1",
      },
    });
    const body = await resp.text();
    return { ok: resp.ok, status: resp.status, body: body.slice(0, 2000) };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}
