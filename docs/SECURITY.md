# Security

Scope: an SIH prototype that handles evidence about real workers (video, voice, location). The
controls below are implemented and tested. The gaps are listed honestly at the end.

## Implemented

| Area | Control | Where | Tested |
|---|---|---|---|
| Passwords | bcrypt (12 rounds); never logged | `security/passwords.py` | ✓ |
| Sessions | JWT HS256, 8 h expiry, secret from `.env` (random per install) | `security/jwt.py` | ✓ |
| Brute force | 8 failed logins per (email, IP) per 10 min → 429 | `security/login_throttle.py` | ✓ |
| Authorization | RBAC per route (`require_roles`) **and** ownership checks in services (candidate sees own evidence; assessor sees own assessments) | `api/deps.py`, services | ✓ |
| Self-registration | Candidate/assessor only; admin → 403 | `services/users.py` | ✓ |
| Assessor-first | Enforced server-side (409 before the initial score; immutable initial score) | `services/assessment.py` | ✓ |
| Blind double-scoring | Other assessors' scores never serialised to an assessor | `services/presenters.py` | ✓ |
| Uploads | Size limit (413, enforced via Content-Length and while streaming), MIME + extension allow-list, **magic-byte sniffing** (415), server-generated filenames `<sha256>.<ext>`, no user-supplied paths | `security/file_validation.py`, `services/evidence.py` | ✓ |
| Integrity | Server recomputes SHA-256 and compares it with the device hash; mismatches are audited | `services/evidence.py` | ✓ |
| Media access | Short-lived HMAC media tokens (15 min, bound to the evidence id) instead of bearer tokens in URLs | `security/media_tokens.py` | ✓ |
| Audit | Hash-chained log of every state change; `/audit/verify` detects edits and deletions | `services/audit.py` | ✓ |
| Headers | CSP (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), nosniff, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, Permissions-Policy | `main.py` | ✓ |
| Errors | Uniform `{detail, code}`; no stack traces to clients | `main.py` handlers | ✓ |
| Static files | Path-traversal guard (resolved path must stay inside `frontend/out`) | `main.py` | ✓ |
| Secrets | `.env` git-ignored; `.env.example` has no secrets; AI keys optional and server-side only | `.env.example` | n/a |
| Offline queue | AES-GCM-256 with a non-extractable device key; plaintext hash recorded before encryption | `frontend/src/lib/offline/*` | ✓ (vitest) |
| AI output | Guardrail strips competency verdicts and score predictions from AI text | `ai/guardrails.py` | ✓ |

## Known gaps (prototype → production)

1. **Token storage:** the JWT is kept in `localStorage`. This is vulnerable to XSS, mitigated by the CSP
   and no third-party scripts. Production: HttpOnly, SameSite cookies with refresh-token rotation.
2. **CSP needs `'unsafe-inline'` for scripts** because the static export injects inline bootstrap
   scripts. Production: nonce-based CSP from a server-rendered deployment.
3. **Demo credentials** are seeded and shown on the login page in demo mode only. Remove them
   (`KP_MODE=real`, re-seed without demo users) before any real data enters the system.
4. **Single-process assumptions:** the login throttle and audit-chain lock are in-memory. Several workers
   need Redis and a database advisory lock.
5. **HTTPS** is not terminated by the app. Put it behind TLS (reverse proxy) with HSTS. WebCrypto and
   camera access also require HTTPS off localhost.
6. **Data protection:** evidence contains biometric-adjacent data (faces, voice) and location. A pilot
   needs informed consent, a retention policy, access logging review and DPDP Act 2023 compliance review.
   None of this is claimed as done.
7. **Malware scanning** of uploads is not implemented (only type and magic-byte checks).
8. **Offline encryption** protects queued files from casual inspection, not from a compromised device or
   script running in our origin.

## Reporting

For this prototype, report issues to the team lead. Never paste real candidate data, passwords or API
keys into issues or chat.
