# Offline-first Architecture

```
CAPTURE OFFLINE → STORE LOCALLY (encrypted) → SYNC (when connected) → PROCESS (server) → ASSESS (assessor first)
```

RPL happens at worksites and rural centres, and the Assistant Electrician QP's own assessment mode is
*Offline* [4]. So capture must work with **zero signal**, while AI processing runs after sync.

## Components (frontend)

| File | Role |
|---|---|
| `src/lib/offline/crypto.ts` | SHA-256 (WebCrypto), AES-GCM-256 with a **non-extractable** device key |
| `src/lib/offline/store.ts` | IndexedDB (`kaushal-pramaan` DB): `queue`, `keys`, `reservations` stores |
| `src/lib/offline/sync.ts` | `SyncEngine`: capture, reservations, sync loop, retry/backoff semantics |
| `src/lib/offline/useSync.ts` | React bindings (`useSyncExternalStore`) |
| `public/sw.js` | App-shell service worker: reload the candidate app with no network |
| `src/components/candidate/*` | Network card (field simulation) and queue cards |

## Capture → queue

1. The file is recorded (MediaRecorder) or chosen (camera/file input), or in demo mode loaded as the
   demo practical.
2. Metadata is captured automatically: timestamp, geolocation (if permitted; in demo mode, a labelled
   demo-site fallback after 3.5 s), device, and SHA-256 of the **plaintext**.
3. Plaintext is encrypted with AES-GCM (random 96-bit IV) and stored in IndexedDB with status `saved`.
4. The item takes the next **reserved evidence number**. While online, the device reserves a block of
   numbers (`POST /sync/reserve`), so an offline capture really is "Evidence #17", not a placeholder.

## Sync

- Triggers: app start, the browser `online` event, every 15 s, the field-simulation switch turning off,
  and "Sync now".
- Each item is decrypted and uploaded as multipart (`file` + `meta`) with real progress (XHR).
- **Idempotent on `local_id`**: if the connection drops after the server has the file, a retry returns
  the same record.
- The server recomputes SHA-256 and compares it to the device hash (`integrity_ok`). This is audited.
- Network error or 5xx → stays `saved`, retried automatically. 4xx (e.g. 415 file type) → `failed`,
  reported via `POST /sync/report`, retry/remove offered.
- After a verified upload, the device copy's payload is freed to save phone storage.

## What the UI shows

```
OFFLINE  Evidence #17 · ✓ Saved locally (encrypted) · ⏳ Waiting for connection
ONLINE   Evidence #17 · ✓ Synced · ✓ Hash verified by server · ✓ Ready for assessment
```
Statuses after sync come from the server (`received → processing → ready`).

## Service worker

`public/sw.js` registers in production builds only. On install it precaches `/`, `/login`, `/candidate`,
`/candidate/capture` and `/research`, plus every `/_next/static` asset they reference. Navigations are
network-first with a cached fallback. `/api/v1/qualifications*` is network-first with a cache fallback,
so QP/NOS/PC stay readable offline. **Evidence never passes through the SW cache.**

## Security scope (honest)

- The key is generated on the device and is **non-extractable**: script can use it but can't export it.
- This protects queued evidence from casual inspection of browser storage or a copied profile folder.
- It does **not** protect against malware on the device or malicious script in our origin (XSS). Those
  are mitigated elsewhere (CSP and no third-party scripts in production; see `SECURITY.md`).
- WebCrypto needs a secure context: `https://` or `localhost`. Over plain-HTTP LAN the app still
  captures, but hashing and encryption are unavailable, and the UI says so.

## Demonstrating offline honestly

- **Field simulation switch** (Capture screen): pauses the sync engine as if there were no signal. It is
  labelled *simulated*. We need it because the demo server runs on `localhost`, which keeps working
  when Wi-Fi is off.
- **Real offline**: serve over HTTPS on the LAN, open the candidate app on a phone, then turn on airplane
  mode. Capture works and items queue. Turn airplane mode off and they sync. See `DEMO.md`.
- Chrome DevTools → Network → *Offline* also works on the laptop (the browser reports offline).

## Metric

*Offline sync success rate* = synced items ÷ (synced + permanently failed items reported by devices).
Computed by `GET /analytics/impact`, split into pilot and demo data.
