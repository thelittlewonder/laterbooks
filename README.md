# shelfie

A personal Progressive Web App that reads book cover photos, extracts titles with OCR, and syncs missing books to your Goodreads **Want to Read** shelf.

## Stack

- **Frontend:** SvelteKit, TypeScript, Tailwind CSS v4, installable PWA
- **Backend:** FastAPI, PaddleOCR, Playwright
- No database, authentication, or cloud storage — images are deleted immediately after processing

## Prerequisites

- Python 3.11+
- Node.js 20+
- Goodreads account credentials

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # add your Goodreads email and password
```

### Frontend

```bash
cd frontend
npm install
```

## Run locally

Start the API (from `backend/`):

```bash
uvicorn app.main:app --reload --port 8000
```

Start the PWA (from `frontend/`):

```bash
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend.

## Usage

1. Select up to 10 book cover photos from your gallery.
2. Tap **Sync** — photos are processed one at a time.
3. Watch live progress while OCR and Goodreads automation run.
4. Review the summary; correct any unknown titles manually.
5. Photos are deleted from the server as soon as each one is processed.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Upload photos, start processing |
| `GET` | `/api/jobs/{id}` | Poll job progress |
| `POST` | `/api/jobs/{id}/manual` | Submit corrected titles |
| `GET` | `/health` | Health check |

## Project structure

```
backend/
  app/
    api/          # FastAPI routes
    ocr/          # PaddleOCR title extraction
    goodreads/    # Playwright shelf automation
    jobs/         # In-memory job state & processor
    models/       # Pydantic schemas
frontend/
  src/lib/
    components/   # PhotoPicker, LiveProgress, etc.
```

## Deploy backend to Render

The backend uses Docker because Playwright and PaddleOCR need Chromium and system libraries.

### 1. Push to GitHub

Render deploys from a Git repo. Push this project to GitHub if you haven't already.

### 2. Create the service

**Option A — Blueprint (recommended)**

1. Go to [render.com](https://render.com) → **New** → **Blueprint**
2. Connect your repo
3. Render reads `render.yaml` at the repo root and creates the web service

**Option B — Manual**

1. **New** → **Web Service** → connect your repo
2. Set **Runtime** to **Docker**
3. **Dockerfile path:** `backend/Dockerfile`
4. **Docker build context:** `backend`
5. **Plan:** Standard (2 GB RAM minimum — Starter is too small for OCR + Chromium)

### 3. Set environment variables

In the Render dashboard → your service → **Environment**:

| Variable | Value |
|----------|--------|
| `GOODREADS_EMAIL` | Your Goodreads login email |
| `GOODREADS_PASSWORD` | Your Goodreads password |
| `CORS_ORIGINS` | Your frontend URL(s), comma-separated, e.g. `https://shelfie.pages.dev,http://localhost:5173` |
| `PLAYWRIGHT_HEADLESS` | `true` |
| `UPLOAD_DIR` | `/tmp/uploads` (already set in `render.yaml`) |

### 4. Deploy

Render builds the Docker image and starts the service. First deploy takes several minutes (PaddleOCR + Chromium install).

Your API URL will be something like `https://shelfie-api.onrender.com`. Verify:

```bash
curl https://shelfie-api.onrender.com/health
# {"status":"ok"}
```

### 5. Point the frontend at Render

Build the frontend with your Render API URL:

```bash
cd frontend
VITE_API_URL=https://shelfie-api.onrender.com npm run build
```

Deploy the built static files wherever you host the PWA (Cloudflare Pages, Netlify, etc.).

## Deploy frontend to Netlify

Netlify serves the PWA as a static site with HTTPS (required for iPhone install).

### 1. Deploy backend first

Follow the Render steps above and note your API URL, e.g. `https://shelfie-api.onrender.com`.

### 2. Connect Netlify to GitHub

1. Go to [netlify.com](https://netlify.com) → **Add new site** → **Import an existing project**
2. Connect the same GitHub repo
3. Netlify reads `netlify.toml` at the repo root — no manual build settings needed

### 3. Set environment variables

In Netlify → **Site configuration** → **Environment variables**:

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | Your Render API URL, e.g. `https://shelfie-api.onrender.com` |

`VITE_*` vars are baked in at build time — redeploy after changing this.

### 4. Deploy

Netlify runs `npm run build` in `frontend/` and publishes the `build/` folder.

Your site will be at `https://something.netlify.app`. Verify the PWA loads.

### 5. Wire up CORS on Render

Back in Render → **Environment**, set:

```
CORS_ORIGINS=https://something.netlify.app,http://localhost:5173
```

Render restarts automatically. Now the frontend can call the API.

### Full deploy order

1. Push repo to GitHub
2. Deploy **backend** on Render → get API URL
3. Deploy **frontend** on Netlify with `VITE_API_URL` → get site URL
4. Add Netlify URL to `CORS_ORIGINS` on Render
5. Install PWA on iPhone via Safari → Share → Add to Home Screen

### Render notes

- **Plan:** Use **Standard** (2 GB RAM). Starter (512 MB) will likely OOM during OCR or Playwright.
- **Cold starts:** Free/idle services spin down; first request after idle can take 30–60s.
- **Job state:** In-memory — active jobs are lost if Render restarts or redeploys.
- **Goodreads login:** If Amazon blocks headless login, you may need to debug locally with `PLAYWRIGHT_HEADLESS=false`; Render cannot run a visible browser.
- **Disk:** Ephemeral — fine, since photos are deleted immediately after processing.

## Notes

- Goodreads login uses Playwright against the live site; Amazon sign-in flows may require headed mode (`PLAYWRIGHT_HEADLESS=false`).
- PaddleOCR downloads model weights on first run (~100 MB).
- This is a personal utility — run it on your own machine, not as a public service.
