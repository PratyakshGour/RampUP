# OnboardOS

OnboardOS turns meeting transcripts into evidence-backed company memory. It stores people, projects, systems, decisions, tasks, facts, source excerpts, and their relationships in FalkorDB. The React app provides a dashboard, transcript ingestion, company-memory chat, a live graph explorer, and personalized onboarding.

Synthetic demo records are clearly labeled. The optional deterministic demo extractor does not call Gemini and does not claim to understand decisions or infer relationships from arbitrary uploads; it stores transcript sections as notes.

## Requirements

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+
- Docker Desktop with Docker Compose
- A Gemini Developer API key from [Google AI Studio](https://aistudio.google.com/apikey) for AI extraction and answer generation (optional in demo mode)

## Run locally (PowerShell)

From the `RampUP` project folder:

```powershell
Copy-Item Backend\.env.example Backend\.env
docker compose up -d falkordb

py -3 -m venv Backend\.venv
Backend\.venv\Scripts\Activate.ps1
python -m pip install -r Backend\requirements.txt
Set-Location Backend
python -m app.graph.loader
python -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
Set-Location Frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The FastAPI Swagger UI is at <http://localhost:8000/docs>. Set `GEMINI_API_KEY` in `Backend\.env` to enable Gemini processing. The server keeps the key; the frontend never receives it.

### Free-tier Gemini configuration

1. Create an API key at [Google AI Studio](https://aistudio.google.com/apikey).
2. Set `GEMINI_API_KEY=...` in `Backend\.env`.
3. Keep `GEMINI_MODEL=gemini-3.8-flash` to use the documented free-tier Flash model, or set another model available to your account.
4. Leave `LLM_PROVIDER=gemini` and `DEMO_MODE=false`.

The app uses Google's official `google-genai` SDK and structured JSON output. It does not change models or upgrade billing when quota is exhausted. Rate-limit and quota failures are shown to the user; uploaded transcript files remain available for retry.

### Deterministic demo mode

For a no-key walkthrough, set `DEMO_MODE=true` in `Backend\.env`, restart the API, and run `python -m app.graph.loader` from `Backend`. The loader inserts three reproducible synthetic transcripts. New uploads are retained as section-level notes; the UI labels the mode as deterministic demo processing.

### FalkorDB

`docker compose up -d falkordb` starts FalkorDB on `localhost:6379`; its browser UI is available at <http://localhost:3000>. To stop it, run `docker compose down`. The graph name defaults to `onboardos`.

## API

- `GET /health`
- `GET /api/dashboard/stats`
- `POST /api/meetings/upload`
- `GET /api/meetings`
- `GET /api/meetings/{meeting_id}`
- `GET /api/meetings/{meeting_id}/evidence`
- `POST /api/meetings/{meeting_id}/process` (retry a failed extraction)
- `GET /api/graph`
- `GET /api/graph/node/{node_id}`
- `POST /api/chat`
- `GET /api/chat/history?session_id=...`
- `POST /api/chat/new`
- `GET /api/onboarding/{employee_id}` (`sample` selects a seeded new hire)

## Tests and checks

From the project root:

```powershell
Set-Location Backend
python -m pytest
Set-Location ..\Frontend
npm run typecheck
npm run build
npm run lint
```

Unit tests mock Gemini and FalkorDB, so they require neither API credits nor a running database. The seeded walkthrough does require FalkorDB. No auth or multi-tenant access controls are implemented; do not use this MVP for private production meeting data.
