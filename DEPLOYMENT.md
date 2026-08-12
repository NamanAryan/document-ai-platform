# Deploying DocAIApp (Render + Vercel)

Backend (FastAPI + ChromaDB) runs on **Render**. Frontend (static HTML/CSS/JS)
runs on **Vercel**. They talk over HTTPS, so the frontend needs the backend's
URL and the backend needs to allow the frontend's origin.

---

## Read this first

**There is no Ollama in the cloud.** Locally this app uses Ollama for both the
chat model *and* the embeddings. A Render instance has no Ollama server, so the
deployed app uses **Google Gemini** for both. This is not optional — without it
the app cannot index a single document.

The code now picks its backend at runtime:

| Variable | Local | Render |
| --- | --- | --- |
| `LLM_PROVIDER` | `auto` (finds Ollama) | `gemini` |
| `EMBEDDING_PROVIDER` | `auto` (finds Ollama) | `gemini` |

**Embeddings from different models are not interchangeable.** Ollama's
`nomic-embed-text` produces 768-dimension vectors; Gemini's model produces a
different width and a different vector space. If you ever switch providers on
an existing index, delete `chroma_db/` and re-upload the documents, or search
will fail or return nonsense.

**Free-tier storage is ephemeral.** On Render's free plan, uploaded files and
the vector index are wiped on every deploy, restart, and spin-down after
inactivity. The app still works — you just re-upload your documents. See
[Persistent storage](#optional-persistent-storage) to make it durable.

**Free instances sleep.** After ~15 minutes idle, the next request takes 50s+
to wake the service. The first page load after a nap may look broken; reload it.

---

## Prerequisites

- The project pushed to a GitHub repository
- A [Render](https://render.com) account
- A [Vercel](https://vercel.com) account
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
  (free tier is enough to try this)

---

## Step 1 — Get a Gemini API key

1. Open <https://aistudio.google.com/apikey> and create a key.
2. Copy it somewhere safe. **Do not commit it.** `.env` is gitignored; the key
   belongs in the Render dashboard.
3. While you are there, note which models your key can call. This project
   defaults to `gemini-3.5-flash` (chat) and `gemini-embedding-2-preview`
   (embeddings). Both are plain environment variables — if Google has retired
   or renamed either, change the value in Render, not the code.

## Step 2 — Push to GitHub

```bash
git add .
git commit -m "Make app deploy-friendly"
git push origin main
```

Confirm `.env` is *not* in the commit (`git status` should never list it) and
that `.env.example`, `render.yaml`, and `frontend/vercel.json` *are*.

## Step 3 — Deploy the backend to Render

The repo contains `render.yaml`, so Render can configure the service itself.

1. Render Dashboard → **New** → **Blueprint**.
2. Select your repository. Render reads `render.yaml` and proposes a web
   service named `docai-platform-api`.
3. It will prompt for the values marked `sync: false`:
   - `GEMINI_API_KEY` — your key from Step 1.
   - `CORS_ALLOW_ORIGINS` — set to `*` for now. You will lock this down in
     Step 6, once you know the Vercel URL.
4. **Apply** and wait for the build (first build is slow — chromadb and its
   dependencies are large).

Prefer clicking through instead of using the blueprint? Create a **Web
Service** with:

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app:main --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

...and add every environment variable listed in `render.yaml` by hand. Note the
start command uses `app:main`, not `app:app` — this project's FastAPI instance
is named `main`.

**Verify before continuing.** Replace the host with your own:

```bash
curl https://your-service.onrender.com/health
```

You want `{"status":"ok", ...}`. If it fails, check the Render logs — see
[Troubleshooting](#troubleshooting).

Then confirm Gemini is actually wired up, not just that the process booted:

```bash
curl https://your-service.onrender.com/analytics
```

The `pipeline` block should report `"llm_backend": "ChatGoogleGenerativeAI"`.
If it says `ChatOllama`, your provider variables did not apply.

## Step 4 — Point the frontend at the backend

Edit `frontend/config.js` and paste in your Render URL (no trailing slash):

```js
window.API_BASE = "https://your-service.onrender.com";
```

Commit and push:

```bash
git add frontend/config.js
git commit -m "Point frontend at Render backend"
git push
```

Leaving this empty makes the frontend call itself on Vercel, where no API
exists — every request 404s.

## Step 5 — Deploy the frontend to Vercel

1. Vercel Dashboard → **Add New** → **Project**, import the same repository.
2. **Set Root Directory to `frontend`.** This matters: the repo root is a
   Python project and Vercel will misread it otherwise.
3. Framework preset: **Other**. No build command, no output directory — these
   are plain static files.
4. **Deploy**, then copy the resulting URL
   (e.g. `https://document-ai-platform.vercel.app`).

`frontend/vercel.json` rewrites `/static/*` to `/*`. The HTML asks for
`/static/style.css` because that is where FastAPI serves it locally; on Vercel
the files sit at the root. The rewrite makes one set of paths work in both
places.

## Step 6 — Lock CORS to your Vercel origin

Back in Render → your service → **Environment**:

```
CORS_ALLOW_ORIGINS = https://document-ai-platform.vercel.app
```

Use the exact scheme and host, no trailing slash. Comma-separate multiple
origins if you also want preview deployments to work. Save; Render redeploys.

Leaving this as `*` works but lets any website call your API and spend your
Gemini quota.

## Step 7 — Verify end to end

Open your Vercel URL and check:

- [ ] Sidebar loads with **0** documents (not a blank/failed state)
- [ ] Uploading a small PDF or TXT succeeds
- [ ] The document appears under Knowledge Base
- [ ] Asking a question streams an answer with a source citation
- [ ] **Index diagnostics** shows `Gemini` as the embedding model
- [ ] Deleting the document clears the chat and empties the list

Browser devtools → Network is the fastest way to diagnose a failure here. A
CORS error means Step 6 is wrong; a 404 on `/documents` means Step 4 is wrong.

---

## Optional: persistent storage

To stop losing uploads on every restart:

1. In `render.yaml`, change `plan: free` to `plan: starter` (paid — free
   instances cannot mount disks).
2. Uncomment the `disk:` block at the bottom.
3. Change the two storage variables:
   ```
   CHROMA_PERSIST_DIR = /var/data/chroma_db
   DOCS_DIR           = /var/data/documents
   ```
4. Redeploy.

## Optional: skip Vercel entirely

Render already serves the frontend — FastAPI mounts `frontend/` at `/static`
and returns `index.html` at `/`. Visit your Render URL directly and the whole
app works, with `window.API_BASE` left empty and CORS irrelevant because
everything is same-origin. Vercel buys you a faster, always-warm CDN for the
static half; it is not required.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Build fails on `pip install` | Python version mismatch | Confirm `PYTHON_VERSION=3.12.7` is set |
| `RuntimeError: No LLM backend available` | Key missing or provider unset | Set `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`, `EMBEDDING_PROVIDER=gemini` |
| `404 models/gemini-… is not found` | Model name retired or not on your key | Change `GEMINI_MODEL` / `GEMINI_EMBEDDING_MODEL` |
| CORS error in console | Origin not allowed | Set `CORS_ALLOW_ORIGINS` to the exact Vercel origin |
| All API calls 404 from Vercel | `API_BASE` still empty | Step 4 |
| Unstyled page on Vercel | `vercel.json` not deployed | Confirm Root Directory is `frontend` |
| Documents vanish | Ephemeral free-tier disk | Expected — see persistent storage |
| First load hangs ~50s | Free instance was asleep | Expected; reload |
| Dimension mismatch on search | Index built with a different embedding model | Delete `chroma_db/`, re-upload |
| Out of memory on Render | 512 MB free-tier limit | Upload fewer/smaller documents, or upgrade |

---

## Local development is unchanged

`LLM_PROVIDER` / `EMBEDDING_PROVIDER` default to `auto`, which finds your local
Ollama and uses it. Nothing about your local workflow changes:

```powershell
ollama serve
.\.venv\Scripts\python.exe -m uvicorn app:main --reload
```

Set both to `gemini` in your local `.env` if you want to test the exact cloud
configuration before pushing.
