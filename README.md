# Kaushal Pramaan: RPL Evidence Intelligence

**SIH 2026 · SIH26242 · AI-Assisted Skill Assessment Tool for Recognition of Prior Learning · Team AQUILA123**

> We don't collect more evidence. We link existing evidence to the exact Performance Criterion it supports.
> **AI finds the evidence. The assessor decides what it means.**

```
EVIDENCE → PERFORMANCE CRITERION → HUMAN ASSESSMENT → RECOGNITION
```

A traceable evidence-intelligence layer on top of the existing NCVET RPL workflow. The candidate captures
evidence offline (encrypted, hashed, geotagged). AI segments the recording and proposes
**Evidence → NOS → PC** links. The assessor **scores first**, sees AI support only after locking that score
(server-enforced), and decides. Every step lands in a hash-chained audit trail, and blind double-scoring
feeds a weighted-κ agreement measure that is **reported only once it has been measured**.

| Doc | What's in it |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Product architecture, ER, routes, API map, AI pipeline, offline, research matrix, 3-min demo |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layers, invariants, folder structure, scalability |
| [docs/API.md](docs/API.md) | API contract (+ live Swagger at `/api/docs`) |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema, relationships, migrations, seed |
| [docs/AI.md](docs/AI.md) | AI services, mapper, guardrail, demo vs real, limitations, evaluation plan |
| [docs/OFFLINE.md](docs/OFFLINE.md) | Capture → encrypted queue → sync, service worker, honest scope |
| [docs/RESEARCH.md](docs/RESEARCH.md) | 10 references → design decisions |
| [docs/DEMO.md](docs/DEMO.md) | Jury runbook, recovery, replacing the synthetic video |
| [docs/SECURITY.md](docs/SECURITY.md) | Auth, RBAC, uploads, audit, headers, known gaps |

---

## Quick start (Windows)

Prerequisites: **Python 3.13** (`py -3.13`), **Node.js 20+**, **ffmpeg** on PATH.

```bash
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Dev
```
This creates `.venv`, installs the backend, writes `.env` with a random `JWT_SECRET`, runs migrations and seeds the demo data.

```bash
cd frontend && npm ci && npm run build
```
This builds the static UI into `frontend/out`, which the backend serves. It's required after a fresh clone, because `out/` isn't committed.

```bash
powershell -ExecutionPolicy Bypass -File scripts/run.ps1
```
Open **http://localhost:8000**. API docs are at **http://localhost:8000/api/docs**. One process serves both the UI and the API, and demo mode needs **no internet**.

### Frontend development (hot reload)

```bash
cd frontend && set NEXT_PUBLIC_API_BASE=http://localhost:8000 && npm run dev
```
Then open http://localhost:3000. The backend must be running, and CORS allows `:3000`. The service worker is
only active in the production build.

### Database & seed

- SQLite by default (`database/kp.db`). For PostgreSQL, set `DATABASE_URL=postgresql+psycopg://…` and
  `pip install "psycopg[binary]"`.
- Migrate: `.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head`
- Seed (idempotent): `.venv/Scripts/python -m backend.app.services.seed`
- The server also migrates and seeds on startup. Jury mode → *Demo safety net* re-seeds to any stage.
- Regenerate the synthetic demo video: `python scripts/make_demo_video.py`

### Environment variables

Every setting is documented in [`.env.example`](.env.example). The important ones:

| Variable | Default | Meaning |
|---|---|---|
| `KP_MODE` | `demo` | `demo` = real ffmpeg/hashing + labelled seeded analysis for the demo video only; `real` = only installed/configured AI runs |
| `JWT_SECRET` | random (setup) | Signs JWTs and media tokens. **Required** for any shared deployment |
| `DATABASE_URL` | SQLite file | SQLAlchemy URL |
| `MAX_UPLOAD_MB` | 300 | Upload limit (413 above) |
| `KAPPA_MIN_PAIRS` / `METRIC_MIN_N` | 30 / 10 | κ and pilot metrics stay *"Pilot measurement underway"* below these |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | empty | Optional LLM + vision; empty means *unavailable*, never faked |
| `ASR_PROVIDER` | `none` | `faster_whisper` enables real speech-to-text |

---

## Demo accounts (seeded, demo data)

| Role | Email | Password |
|---|---|---|
| Candidate: Raj Kumar (CAND-0001) | raj@kp.demo | Candidate@2026 |
| Assessor A: A-07 | a07@kp.demo | Assessor@2026 |
| Assessor B: A-12 (blind second) | a12@kp.demo | Assessor@2026 |
| Admin (Jury mode) | admin@kp.demo | Admin@2026 |

These are demo-only credentials. Change or remove them before any real deployment (see SECURITY.md).

## Demo flow (3 minutes): full script in [docs/DEMO.md](docs/DEMO.md)

1. **Candidate** → Capture → *Field simulation: no signal* → *Use practical recording (10:00)* → Save
   → **Evidence #17 · saved locally (encrypted) · waiting for connection**.
2. Switch the simulation off → **synced ✓ hash verified ✓**.
3. **Assessor A-07** → Evidence #17 → **Find relevant evidence**. The pipeline runs (REAL / DEMO
   ANALYSIS labels) and finds **AI found 00:42–01:08**.
4. **Evidence Mapper**: #17 → ISC/N1002 → **PC10** (verbatim NQR text) → Rubric → Assessor. Confidence is 🔒.
5. **Assess**: rubric → **3/4 → Lock**. **AI support** is revealed: *Supports · 91% · DEMO ANALYSIS*,
   *AI score: None*. Confirm the mapping → Final 3/4.
6. **Audit trail** → *Verify chain* ✓ → Record **PDF / JSON**.
7. **Assessor A-12** scores blind → **Admin → Agreement**: n = 1/30 → **Pilot measurement underway**.

If anything misbehaves: **Admin → Jury mode → Demo safety net** jumps to any stage in ~2 s.

---

## Tests

```bash
.venv/Scripts/python -m pytest backend/tests
```
That's the backend suite: 98 tests across unit, API and integration, including the full jury flow, κ vs
scikit-learn, guardrail, audit-chain tamper detection, segmentation on the demo video, upload security,
the login throttle, CSP headers, path-traversal blocking and concurrent number reservation.

```bash
cd frontend && npm test
```
That's the frontend suite: SHA-256 vector, AES-GCM round-trip, offline capture with a reserved number,
sync, retry after a dropped connection, and the failure report.

```bash
cd frontend && npx tsc --noEmit && npx eslint src
```
Type-check and lint.

## Troubleshooting

| Problem | Fix |
|---|---|
| `py -3.13` not found | Install Python 3.13, or edit `scripts/setup.ps1` to use your interpreter |
| "ffmpeg unavailable" on /status | Install ffmpeg and make sure `ffmpeg -version` works in a new terminal |
| Port 8000 busy | `scripts/run.ps1 -Port 8010` |
| Blank page / old UI after rebuilding | Hard-reload (Ctrl+Shift+R). The service worker caches the app shell |
| Video won't seek or play after a while | Media links expire after 15 min. Reload the page |
| "Too many failed sign-in attempts" (429) | Wait 10 min or restart the server (in-memory throttle) |
| Hashing/encryption unavailable on a phone | WebCrypto needs HTTPS or localhost. See the HTTPS note in DEMO.md |
| Want a clean demo | Admin → Jury mode → Load "Fresh", and use a private window for the candidate |

## Honest status

- **Demo data is labelled.** Evidence #17, the 10:00 video (synthetic), the transcript, tags and the **91%**
  are seeded DEMO ANALYSIS for a synthetic recording. Replace them with a real recorded practical (DEMO.md).
- **Not built or not claimed:** DigiLocker integration (existing ecosystem, not integrated), any
  certification, a measured κ or impact numbers (pilot measurement underway), calibrated AI confidence.
- **Real but not exercised here:** the Claude/Gemini, faster-whisper and Tesseract adapters are implemented
  and report themselves *unavailable* without keys or installs. They haven't been run against live
  services in this build.
- Only PC10 of ISC/N1002 is seeded (verbatim). Other PCs must be added from the official Q-File, and the
  PC10 rubric descriptors are a **team draft** pending SSC validation.

## Roadmap

1. Real recorded practicals + a pilot with two certified assessors → first measured κ, minutes per candidate,
   and sync success.
2. IndicWhisper ASR on a GPU worker. Multilingual embedding mapper (pgvector) with LLM re-ranking. Calibration
   of relevance scores against assessor decisions.
3. Remaining Assistant Electrician PCs and rubric validation with IISSSC assessors. A second QP to prove the
   multi-occupation model.
4. Production hardening: PostgreSQL, object storage, job queue, HTTPS/HSTS, refresh tokens in HttpOnly
   cookies, a database-level audit lock, Docker.
5. Awarding-body export format agreed with an assessment agency (still no claim of DigiLocker integration
   until it is real).
