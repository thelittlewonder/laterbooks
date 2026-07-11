# laterbooks

A personal Progressive Web App that reads book cover photos **on your phone**, extracts titles with browser OCR, and syncs missing books to your Goodreads **Want to Read** shelf.

## Architecture

```
iPhone (PWA)                    Render (free tier)
─────────────                   ──────────────────
Select photos                   FastAPI + Playwright
Tesseract.js OCR  ──titles──►   Goodreads automation
(photos stay local)             (~300–400 MB RAM)
```

- **Frontend:** SvelteKit, TypeScript, Tailwind CSS v4, Tesseract.js, installable PWA
- **Backend:** FastAPI, Playwright only (no server-side OCR)
- No database, authentication, or cloud storage — **cover photos never leave your device**

## Prerequisites

- Python 3.11+ (backend / session export script)
- Node.js 20+ (frontend)
- Goodreads account credentials

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # add Goodreads credentials or storage state
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
2. Tap **Read & sync** — OCR runs on your phone (first run downloads ~2 MB English model).
3. Detected titles are sent to the backend; Goodreads automation runs server-side.
4. Review the summary; correct any unknown titles manually.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Submit OCR titles, start Goodreads sync |
| `GET` | `/api/jobs/{id}` | Poll job progress |
| `POST` | `/api/jobs/{id}/manual` | Submit corrected titles |
| `GET` | `/health` | Health check |

### Create job body

```json
{
  "photos": [
    { "photo_index": 0, "titles": ["Dune"] },
    { "photo_index": 1, "titles": [] }
  ]
}
```

## Project structure

```
backend/
  app/
    api/          # FastAPI routes
    goodreads/    # Playwright shelf automation
    jobs/         # In-memory job state & processor
    models/       # Pydantic schemas
frontend/
  src/lib/
    ocr/          # Tesseract.js title extraction (client-side)
    components/   # PhotoPicker, OcrProgress, LiveProgress, etc.
```

## Goodreads session (recommended for Render)

Headless login can fail. Export a session from your Mac:

```bash
cd backend
source .venv/bin/activate
playwright install chromium
python scripts/export_goodreads_session.py
```

Copy the printed JSON into Render → `GOODREADS_STORAGE_STATE`.

## Deploy backend to Render

The backend uses Docker for Playwright/Chromium. Without PaddleOCR it fits the **free 512 MB** tier.

### 1. Push to GitHub

Render deploys from a Git repo. Push this project to GitHub if you haven't already.

### 2. Create the service

**Option A — Blueprint (recommended)**

1. Go to [render.com](https://render.com) → **New** → **Blueprint**
2. Connect your repo
3. Render reads `render.yaml` at the repo root

**Option B — Manual**

1. **New** → **Web Service** → connect your repo
2. **Runtime:** Docker
3. **Dockerfile path:** `backend/Dockerfile`
4. **Docker build context:** `backend`
5. **Plan:** Free

### 3. Environment variables

| Variable | Value |
|----------|--------|
| `GOODREADS_EMAIL` | Your Goodreads login email |
| `GOODREADS_PASSWORD` | Your Goodreads password |
| `GOODREADS_STORAGE_STATE` | JSON from session export script (preferred) |
| `GOODREADS_LOGIN_METHOD` | `goodreads` |
| `CORS_ORIGINS` | Your Netlify URL(s), comma-separated |
| `PLAYWRIGHT_HEADLESS` | `true` |

### 4. Deploy

```bash
curl https://laterbooks-api.onrender.com/health
# {"status":"ok"}
```

### 5. Point the frontend at Render

```bash
cd frontend
VITE_API_URL=https://laterbooks-api.onrender.com npm run build
```

## Deploy frontend to Netlify

### 1. Connect Netlify to GitHub

Netlify reads `netlify.toml` at the repo root.

### 2. Environment variables

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | Your Render API URL |

Redeploy after changing `VITE_*` vars.

### 3. Wire up CORS on Render

```
CORS_ORIGINS=https://your-site.netlify.app,http://localhost:5173
```

### Full deploy order

1. Push repo to GitHub
2. Deploy **backend** on Render → get API URL
3. Deploy **frontend** on Netlify with `VITE_API_URL` → get site URL
4. Add Netlify URL to `CORS_ORIGINS` on Render
5. Install PWA on iPhone via Safari → Share → Add to Home Screen

### Render notes

- **Plan:** Free tier (512 MB) — Playwright-only backend should fit; first cold start may take 30–60s.
- **Job state:** In-memory — active jobs are lost if Render restarts.

## Notes

- OCR quality depends on cover photo clarity; manual review handles misses.
- Tesseract.js downloads language data on first OCR run (needs network once).
- This is a personal utility — run it for your own Goodreads account only.
