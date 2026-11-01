# Frontend

React + Vite + TypeScript + Tailwind v4. The "Secure card desk" design system: tokens live in
`src/index.css`, components use only semantic token names, and `DESIGN.md` documents the
decisions (colours, type, the ledger rail, Markdown answers, progressive reveal, edit and
replay, the scroll model, accessibility).

```bash
npm ci
npm run dev        # http://localhost:5173, proxies /api and /health to http://127.0.0.1:8000
npm test           # vitest: SSE parser, Markdown and citation markers, reveal, edit/replay, focus
npm run lint && npx tsc -b --noEmit && npm run build
```

`VITE_API_TARGET` changes the dev proxy target; `VITE_API_BASE` points a built app at a
remote API.

Layout: `src/api` (typed client, SSE parser), `src/hooks` (chat state, scroll, reveal, dialogs),
`src/components` (presentation), `src/lib` (formatting, citation markers, demo scenarios).
