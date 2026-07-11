# laterbooks

Snap book cover photos → auto OCR → sync to Goodreads **Want to Read**. Seamless, no manual steps.

## Architecture (100% free tier)

```
iPhone (PWA)              Render FREE (512MB)           Google Cloud Vision
─────────────             ───────────────────           ───────────────────
Select photos ─upload──►  FastAPI + Playwright          DOCUMENT_TEXT_DETECTION
Watch progress            Goodreads automation          1000 images/month FREE
                          Photos deleted immediately
```

| Piece | Cost | Why |
|-------|------|-----|
| Netlify (frontend) | Free | Static PWA |
| Render (backend) | Free | Playwright only — no OCR models in RAM |
| Google Vision OCR | Free | 1,000 cover photos/month forever |

Browser Tesseract cannot read stylized bookstore shelf photos. Vision API can.

## Setup Vision API (5 min, free)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → enable **Cloud Vision API**
3. Create an **API key** (Credentials → Create credentials → API key)
4. Restrict key to Cloud Vision API only (recommended)
5. Add billing account (required to activate free tier — **you won't be charged** under 1,000 images/month)

Set on Render: `GOOGLE_VISION_API_KEY=your_key`

## Prerequisites

- Python 3.11+, Node.js 20+
- Goodreads account

## Local dev

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
cp .env.example .env   # add GOOGLE_VISION_API_KEY + Goodreads creds
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## Usage

1. Snap book photos in the bookstore.
2. Tap **Sync** — uploads, OCR via Vision API, Goodreads syncs automatically.
3. Done. Manual review only if something couldn't be matched.

## Deploy

### Render (backend) — FREE plan

1. Push to GitHub → Render Blueprint (`render.yaml`)
2. Env vars:
   - `GOOGLE_VISION_API_KEY`
   - `GOODREADS_STORAGE_STATE` (from `python scripts/export_goodreads_session.py`)
   - `CORS_ORIGINS` = your Netlify URL

### Netlify (frontend)

1. Set `VITE_API_URL` = your Render URL
2. Deploy

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Upload photos, auto OCR + Goodreads sync |
| `GET` | `/api/jobs/{id}` | Poll progress |
| `POST` | `/api/jobs/{id}/manual` | Retry corrected titles |
| `GET` | `/health` | Health check |

## Other free options (if you outgrow 1k/month)

| Option | Free allowance | Notes |
|--------|----------------|-------|
| **Google Vision** (current) | 1,000/mo | Best accuracy, zero server RAM |
| **Oracle Cloud ARM** | 2 OCPU / 12GB | Self-host RapidOCR + Playwright, more setup |
| **Hetzner** | — | ~€4/mo if you need unlimited |

## Security note

The API has no auth — anyone with your Render URL can trigger syncs. Don't share the URL publicly. (API key auth coming.)

## Notes

- Photos upload to Render briefly, then delete immediately after OCR.
- Goodreads match validation prevents adding wrong books on fuzzy OCR.
- Personal tool — your Goodreads account only.
