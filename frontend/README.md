# Kaushal Pramaan: frontend

Next.js 16 (App Router, **static export**) PWA. See the [root README](../README.md) and
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

- `npm run build`: writes `out/`, served by FastAPI at `/`
- `npm run dev`: hot reload on :3000 (set `NEXT_PUBLIC_API_BASE=http://localhost:8000`)
- `npm test`: vitest (offline queue, crypto, formatting)

Layout: `src/app` (routes) · `src/components` (UI kit, screens' building blocks) · `src/lib` (API client,
auth, types, offline engine).
