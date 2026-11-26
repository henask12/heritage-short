# Heritage Short — Web Showcase

Public landing page for **Red Through the Years**, ready to deploy on Vercel.

## Local

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000

## Deploy to Vercel

1. Push this repo to GitHub (already on `henask12/heritage-short`).
2. Go to [vercel.com/new](https://vercel.com/new) → Import the repo.
3. Set **Root Directory** to `web`.
4. Framework: Next.js (auto-detected).
5. Deploy.

No environment variables required for the public site.

## What’s on the page

- Hero with working title + logline
- Film player with **16:9 / 9:16** format toggle and **English / Amharic** tracks
- Story / audience / intent
- How it was made (pipeline summary)
- AI disclosure + link to the GitHub repo

Videos are compressed web copies under `public/videos/` (EN+AM × 16:9+9:16). Full-quality masters stay in the repo at `outputs/final/`.
