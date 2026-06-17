# Wraeclast web (Next.js)

Clean, functional dashboard reading the FastAPI backend: state of the league today,
farm ranking by profit/hour, build snapshot, and a RAG chat.

## Dev
```bash
cd web
npm install
cp .env.example .env.local   # point NEXT_PUBLIC_API_URL at your backend
npm run dev                  # http://localhost:3000
```

## Deploy (Vercel)
Import the repo, set the project root to `web/`, and add the env var `NEXT_PUBLIC_API_URL`
pointing at the deployed backend. The free `*.vercel.app` HTTPS domain also satisfies the
GGG confidential-OAuth redirect requirement if you pursue Phase 2.
