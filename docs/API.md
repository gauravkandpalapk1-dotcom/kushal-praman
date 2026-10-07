# API Contract — `/api/v1`

FastAPI also serves live, interactive docs at **`/api/docs`** (Swagger) and `/api/redoc`.
This file is the contract the frontend is built against. If code and this file disagree, the code is wrong.

## Conventions

- JSON everywhere except uploads (multipart) and record/PDF downloads.
- Auth: `Authorization: Bearer <JWT>`. Roles: `candidate`, `assessor`, `admin`.
- Errors: `{"detail": "<human readable>", "code": "<machine_code>"}` with the right status:
  `400` bad input · `401` unauthenticated · `403` wrong role/ownership · `404` · `409` workflow-state
  violation (e.g. AI support before initial score) · `413` file too large · `415` bad file type ·
  `422` validation.
- Timestamps: ISO-8601 UTC (`2026-10-07T09:02:11Z`). Durations in seconds (float).
- Every state-changing call writes a hash-chained audit entry.
- `mode` fields are `"real"` or `"demo"`. Anything with `mode:"demo"` must be shown in the UI with a
  **DEMO ANALYSIS** / **DEMO DATA** badge.

---

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{email, password(min 8), full_name, role:"candidate"\|"assessor", preferred_language?, qualification_id?}` | `201 TokenOut` |
| POST | `/auth/login` | `{email, password}` | `200 TokenOut` · `401` |
| GET | `/auth/me` | — | `UserOut` |

```jsonc
// TokenOut
{"access_token":"…","token_type":"bearer","expires_in":28800,"user":UserOut}
// UserOut
{"id":1,"email":"raj@kp.demo","full_name":"Raj Kumar","role":"candidate","is_active":true,
 "candidate":{"id":1,"candidate_code":"CAND-0001","qualification_id":1,"preferred_language":"hi","district":"Dehradun"} | null,
 "assessor":{"id":1,"assessor_code":"A-07","agency":{"id":1,"name":"…","code":"…"}} | null}
```
Admin accounts can't be self-registered (`403`).

## Qualifications (QP → NOS → PC → Rubric)

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/qualifications` | any | list with `nos_count`, `pc_count` |
| GET | `/qualifications/{id}/tree` | any | full hierarchy |
| POST | `/qualifications` | admin | `{title,nqr_code,nsqf_level,sector_skill_council,version,assessment_mode}` |
| POST | `/qualifications/{id}/nos` | admin | `{code,title,version,is_mandatory}` |
| POST | `/nos/{id}/pcs` | admin | `{code,text,max_marks(default 4),is_verbatim,source_note}` |
| PUT | `/pcs/{id}/rubric` | admin | `{levels:[{score,descriptor,exemplar?}],status:"draft"\|"validated"}`, creates a new rubric version |

```jsonc
// tree
{"qualification":{"id":1,"title":"Assistant Electrician","nqr_code":"QG-03-IS-03883-2025-V2-IISSSC","nsqf_level":3,
  "sector_skill_council":"IISSSC","version":"2.0","assessment_mode":"Offline","source_ref":4},
 "nos":[{"id":3,"code":"ISC/N1002","title":"Assemble the electrical components","version":"5.0","is_mandatory":true,
   "pcs":[{"id":1,"code":"PC10","text":"use wires strippers, crippling tool and …","is_verbatim":true,
     "source_note":"Verbatim from NQR Q-File (original spelling)","max_marks":4,
     "rubric":{"id":1,"version":1,"status":"draft","levels":[{"score":0,"descriptor":"…","exemplar":null}, …]}}]}]}
```

## Evidence

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/evidence` | candidate | multipart: `file` + `meta` (JSON string). **Idempotent on `meta.local_id`**: a repeat upload returns `200` with the existing record |
| GET | `/evidence` | any | candidate: own only; `?status=ready&candidate_id=` |
| GET | `/evidence/{id}` | owner/assessor/admin | `EvidenceOut` |
| GET | `/evidence/{id}/media?t=<media_token>` | token | HTTP Range supported (video seeking). Token comes from `EvidenceOut.media_url` (HMAC, 15 min) |
| POST | `/evidence/{id}/process` | assessor/admin | `202 ProcessingOut`, starts the pipeline (re-run is idempotent: returns current job if running/done unless `?force=true`) |
| GET | `/evidence/{id}/processing` | owner/assessor/admin | `ProcessingOut` (poll every ~700 ms) |
| GET | `/evidence/{id}/workspace` | assessor/admin | tier-1 view (see below) |
| GET | `/evidence/{id}/mappings` | any authorised | `MappingOut[]` (tier-gated fields) |

```jsonc
// meta (upload)
{"local_id":"uuid","kind":"video|photo|audio|document","qualification_id":1,"pc_hint_id":null,
 "client_sha256":"hex","captured_at":"…","latitude":30.3165,"longitude":78.0322,"accuracy_m":12,
 "device":"ua string","language":"hi","reserved_number":17,"encrypted_at_rest":true,
 "offline_captured":true,"queued_at":"…","sync_attempts":1,"notes":null}
// EvidenceOut
{"id":5,"display_number":17,"label":"Evidence #17","kind":"video","original_filename":"practical.mp4",
 "mime_type":"video/mp4","size_bytes":5242880,"sha256":"…","client_sha256":"…","integrity_ok":true,
 "status":"received|processing|ready|failed","is_demo":true,"offline_captured":true,"encrypted_at_rest":true,
 "captured_at":"…","synced_at":"…","qualification_id":1,
 "candidate":{"id":1,"full_name":"Raj Kumar","candidate_code":"CAND-0001"},
 "metadata":{"latitude":…,"longitude":…,"accuracy_m":…,"device":"…","duration_s":600.0,"width":640,"height":360,"language":"hi"},
 "media_url":"/api/v1/evidence/5/media?t=…"}
// ProcessingOut
{"evidence_id":5,"status":"queued|running|done|failed","mode":"demo","started_at":"…","finished_at":"…",
 "steps":[{"key":"integrity|probe|segmentation|speech|vision|ocr|llm|mapping","label":"Integrity check (SHA-256)",
           "status":"pending|running|done|skipped|failed","mode":"real|demo|unavailable","detail":"…",
           "started_at":"…","finished_at":"…"}]}
// workspace (tier 1: WHERE the evidence is, no interpretation)
{"evidence":EvidenceOut,
 "segments":[{"id":1,"start_s":0,"end_s":42,"label":"Scene 1","source":"scene"}],
 "transcript":[{"start_s":44.0,"end_s":49.5,"text":"…","language":"hi","translation_en":"…","mode":"demo"}],
 "surfaced":[{"mapping_id":1,"segment_id":2,"start_s":42,"end_s":68,"pc_id":1,"pc_code":"PC10","nos_code":"ISC/N1002",
              "statement":"Potential evidence supporting PC10 found at 00:42–01:08.","mode":"demo"}]}
// MappingOut
{"id":1,"evidence_id":5,"segment":{"id":2,"start_s":42,"end_s":68},
 "pc":{"id":1,"code":"PC10","text":"…","nos":{"id":3,"code":"ISC/N1002","title":"…"}},
 "qualification":{"id":1,"title":"Assistant Electrician","nqr_code":"…"},
 "statement":"Potential evidence supporting PC10 found at 00:42–01:08.",
 "status":"pending|confirmed|edited|rejected","mode":"demo","decided_by":"A-07"|null,"decided_at":…,
 "locked":true,            // true => confidence/rationale/tags are null for this viewer
 "lock_reason":"Revealed after your initial score is locked"|null,
 "confidence":0.91|null, "rationale":"…"|null, "tags":["wire stripper","crimping tool"]|null}
```
**Tier rule:** `admin` always sees interpretive fields. `assessor` sees them only if they hold an
assessment on that (evidence, PC) whose initial score is locked. `candidate` never sees them.

## Mapping decisions (assessor; only after their initial score is locked for that PC → else 409)

| Method | Path | Body |
|---|---|---|
| POST | `/mappings/{id}/confirm` | `{}` |
| POST | `/mappings/{id}/reject` | `{reason}` (required) |
| POST | `/mappings/{id}/edit` | `{pc_id?, start_s?, end_s?, reason}`: status `edited`, original preserved in audit |

## Assessments (assessor-first state machine, server-enforced)

`opened → initial_locked → ai_revealed → finalized`

| Method | Path | Role | Rule |
|---|---|---|---|
| POST | `/assessments` | assessor | `{evidence_id, pc_id}`; returns the existing one if this assessor already opened it (`200`) else `201` |
| GET | `/assessments` | assessor (own) / admin (all) | `?status=` |
| GET | `/assessments/{id}` | owner/admin | `AssessmentOut`, **never includes other assessors' scores** |
| POST | `/assessments/{id}/initial` | owner | `{score:0..max, note?}`. **409 if already locked** (immutable) |
| GET | `/assessments/{id}/ai-support` | owner/admin | **409 `initial_score_required`** until locked. First call sets `ai_revealed_at` |
| POST | `/assessments/{id}/final` | owner | `{score, rationale?}`. 409 if not locked or already finalized; **422 if score ≠ initial and no rationale** |
| GET | `/assessments/{id}/audit` | owner/admin | `AuditOut[]` for this assessment + its evidence + mapping |
| GET | `/assessments/{id}/record.json` | owner/admin | assessment record |
| GET | `/assessments/{id}/record.pdf` | owner/admin | same, as PDF |

```jsonc
// AssessmentOut
{"id":1,"status":"opened","max_score":4,"blind":false,"is_second_assessor":false,
 "evidence":EvidenceOut,"candidate":{…},"qualification":{…},"nos":{…},"pc":{… incl rubric},
 "assessor":{"id":1,"assessor_code":"A-07","full_name":"…"},
 "opened_at":"…","initial_score":null,"initial_note":null,"initial_locked_at":null,
 "ai_revealed_at":null,"final_score":null,"final_rationale":null,"finalized_at":null,
 "score_changed":null, "mapping":{"id":1,"status":"pending"}|null}
// ai-support
{"assessment_id":1,"mode":"demo","pc":{…},"nos":{…},
 "findings":[{"mapping_id":1,"start_s":42,"end_s":68,"statement":"Potential evidence supporting PC10 found at 00:42–01:08.",
   "signal":"supports","confidence":0.91,"rationale":"…","tags":["…"],
   "transcript":[{"start_s":…,"end_s":…,"text":"…","translation_en":"…"}]}],
 "summary":"…neutral description…",
 "services":[{"service":"speech","provider":"demo","model":"seeded fixture","mode":"demo"}],
 "disclaimer":"AI output identifies and describes evidence. It does not assess competency. The assessor decides."}
```
`signal` ∈ `supports | partial | not_found`. It describes the **evidence**, never the candidate.

## Audit

| GET `/audit` | admin | `?entity_type=&entity_id=&limit=200` → `AuditOut[]` newest first |
|---|---|---|
| GET `/audit/verify` | admin/assessor | `{"ok":true,"entries":42,"head_hash":"…","broken_at":null}` |

```jsonc
// AuditOut
{"id":7,"ts":"…","actor":{"id":2,"name":"…","role":"assessor","code":"A-07"},"action":"assessment.initial_locked",
 "entity_type":"assessment","entity_id":1,"summary":"Initial score 3/4 locked for PC10","details":{…},
 "prev_hash":"…","hash":"…"}
```
Actions: `auth.login, auth.register, evidence.received, evidence.integrity_verified, evidence.integrity_failed,
processing.started, processing.completed, mapping.proposed, assessment.opened, assessment.initial_locked,
ai.revealed, mapping.confirmed, mapping.edited, mapping.rejected, assessment.finalized, record.exported,
admin.*, demo.reset`.

## Agreement (admin)

`GET /agreement` → pairs are the first two **finalized** assessments by distinct assessors on the same
(evidence, PC), using final scores.
```jsonc
{"threshold":30,"n_pairs":1,"weighting":"quadratic","status":"insufficient|reported",
 "kappa":null,"kappa_linear":null,"exact_agreement":null,"adjacent_agreement":null,
 "message":"Pilot measurement underway — 1 of 30 double-scored decisions collected.",
 "data_source":"demo|pilot|mixed|none",
 "pairs":[{"evidence_label":"Evidence #17","pc_code":"PC10","candidate":"Raj Kumar",
           "assessor_a":"A-07","score_a":3,"assessor_b":"A-12","score_b":3,"is_demo":true}]}
```
κ and the agreement percentages are **null** below the threshold. No value is shown that hasn't been measured.

## Analytics (admin)

`GET /analytics/impact`
Each metric reports **pilot** (records with `is_demo=false`) and **demo** values separately. The UI
headline is always the pilot value, or "Pilot measurement underway" when it's insufficient. Demo values
show only as a secondary line badged DEMO DATA.
```jsonc
{"metrics":[
  {"key":"evidence_linked_pct","label":"% of scores linked to evidence","unit":"%",
   "definition":"Finalized assessments with ≥1 confirmed/edited evidence mapping ÷ all finalized assessments",
   "pilot":{"value":null,"n":0,"status":"insufficient","min_n":10},
   "demo":{"value":100.0,"n":2},
   "note":"…"},
  {"key":"weighted_kappa", …, "pilot":{"value":null,"n":0,"status":"insufficient","min_n":30}, "demo":{"value":null,"n":1}},
  {"key":"minutes_per_candidate", …  /* median (finalized_at − opened_at) summed per candidate */},
  {"key":"offline_sync_success", …   /* synced ÷ (synced + reported failed) items */}],
 "ai_influence":{"post_reveal_change_rate":0.0|null,"n":2,"note":"Share of finalized decisions where the final score differs from the locked initial score."},
 "counts":{"candidates":1,"assessors":2,"evidence":1,"assessments":2,"double_scored":1}}
```

## Sync

| POST `/sync/reserve` | candidate | `{count:1..20}` → `{"numbers":[17,18,19]}` reserved evidence numbers for offline use |
|---|---|---|
| POST `/sync/report` | candidate | `{local_id, outcome:"failed", attempts, error}`: records failed attempts |
| GET `/sync/stats` | admin | `{"items":…, "synced":…, "failed":…, "success_rate":…|null}` |

## Admin

`GET /admin/users?role=` · `POST /admin/users` `{email,password,full_name,role:"assessor"|"candidate"|"admin",assessor_code?}` ·
`PATCH /admin/users/{id}` `{is_active}` · `GET /admin/agencies`

## Research, system, demo

| GET `/research` | public | `[{"number":5,"short":"Buçinca et al. (2021)","citation":"…","url":"…","category":"research","what_it_says":"…","design_decision":"…","where_in_product":["…"]}]` |
|---|---|---|
| GET `/health` | public | `{"status":"ok","mode":"demo","version":"…","time":"…","db":{"ok":true,"engine":"sqlite"},"storage":{"ok":true},"ffmpeg":{"available":true,"version":"…"},"audit_chain":{"ok":true,"entries":…},"services":[{"key":"speech","name":"Speech-to-text","provider":"demo","available":true,"mode":"demo","detail":"…"}]}` |
| GET `/demo/media/practical` | public, demo mode | the demo practical video (for *Use practical recording*) |
| POST `/demo/reset` | admin, demo mode | `{stage:"fresh"\|"processed"\|"assessor_a_scored"\|"both_scored"}`: wipes and re-seeds, then replays real service calls to that stage |

---

## Implementation notes (backend v0.1.0)

Everything above is implemented as written. The differences below are **additive** (extra fields or
endpoints) unless marked otherwise; nothing in the contract above was removed or renamed.

- **Errors:** `422` responses also carry `errors:[{loc,msg}]` next to `detail`/`code`. A disabled account gets
  `403 account_disabled` on login. Media: bad/expired token → `403 invalid_media_token|media_token_expired`;
  unsatisfiable range → `416`.
- **Audit hash:** `hash = sha256(prev_hash + canonical_json({ts, actor_id, action, entity_type, entity_id, summary, details}))`
  (sorted keys, compact, UTF-8, `ts` with microseconds, genesis `prev_hash` = 64 zeros). `summary` is included so a
  rewritten summary is also detected. `/audit/verify` also returns `reason`. Extra actions:
  `sync.numbers_reserved, sync.failure_reported, admin.user_created, admin.user_updated, admin.qualification_created,
  admin.nos_created, admin.pc_created, admin.rubric_versioned`. Pipeline-written entries have
  `actor:{"id":null,"name":"Processing pipeline","role":"system","code":null}`.
- **Processing:** `ProcessingOut` adds `run` (increments on `?force=true`) and per-step `provider`/`model`;
  `status` can be `not_started` before the first `POST /process`. `POST /process` always returns `202`
  (the existing job when one is queued/running/done; a failed job is restarted). `force=true` while running → `409`.
  Steps that do not apply (e.g. OCR on video) are `skipped` with `mode:"real"` and detail "Not applicable to …";
  services that are not installed/configured are `skipped` with `mode:"unavailable"`.
- **Demo vs real:** `is_demo` = the file's server SHA-256 equals the bundled demo video's. Fixture analysis is used
  only when `KP_MODE=demo` **and** `is_demo`; in `KP_MODE=real` the demo video gets real services only.
- **EvidenceOut** adds `pc_hint_id`; `metadata` adds `sync_attempts`, `queued_at`. Upload `meta.client_sha256`
  is required; `meta.local_id` must be 8–64 chars `[A-Za-z0-9_.:-]`.
- **MappingOut** adds `signal` (tier-gated like `confidence`). For candidates `lock_reason` is
  "Interpretive AI output is shown to assessors only". An assessor receiving unlocked fields via `/mappings`
  counts as the AI reveal (stamps `ai_revealed_at`, audits `ai.revealed`), same as `/ai-support`.
- **Mapping edit:** `reason` is optional for `/edit` (required for `/reject`); the span must lie inside the recording.
- **AssessmentOut** adds `is_demo`; `pc` includes `keywords` and the rubric version pinned when the assessment
  was opened. `GET /assessments/{id}/audit` is chronological (oldest first).
- **ai-support** adds `confidence_note`, `ai_revealed_at`; each finding adds `mode`, `status`; `services[]` adds
  `status`. With no surfaced mapping, `findings` holds one `signal:"not_found"` entry with `mapping_id:null`,
  `start_s/end_s:null`, `tags:[]`.
- **Agreement / analytics:** κ undefined (all scores in one category) → `kappa:null` with an explanatory message even
  at n ≥ threshold. `ai_influence` adds `data_source` and counts decisions where AI support was revealed.
  Sync failure reports never followed by an upload count as pilot data.
- **Sync:** extra `GET /sync/status` (candidate: own queue items). `/sync/report` accepts optional
  `offline_captured` and returns the item `{local_id,status,attempts,evidence_id,last_error,synced_at,updated_at}`.
  `success_rate` is a fraction (0–1).
- **Qualifications:** `PUT /pcs/{id}/rubric` requires levels covering every score `0..max_marks` exactly once
  (`422 rubric_levels_invalid`) and accepts `author_note`. `POST /nos/{id}/pcs` accepts `keywords[]` (used by the mapper).
- **Admin:** `POST /admin/users` also accepts `qualification_id`, `preferred_language`, `district`;
  `/admin/agencies` items add `assessor_count`.
- **Health** adds `demo_asset:{available,sha256}`, `ffmpeg.ffprobe`, `audit_chain.broken_at`, and `model` per service.
  `status` is `"degraded"` if the DB, storage, ffmpeg or the audit chain is not OK.
- **Demo:** `/demo/reset` returns `{ok,stage,evidence_id,assessment_ids,audit_chain,message}`; outside demo mode it is
  `409 demo_mode_only` (non-admin `403`). `/demo/media/practical` is `404` outside demo mode.
