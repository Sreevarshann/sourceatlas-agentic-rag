# SourceAtlas web

Next.js 16 + React 19 + Tailwind 4 + Radix + TanStack Query + Motion + React Flow + pdf.js +
Plotly. `/api/*` is rewritten to the FastAPI backend (`SOURCEATLAS_API_ORIGIN`, default
`http://127.0.0.1:8112`). `npm install` copies the pdf.js worker into `public/`.

```bash
npm install && npm run dev -- --port 3102
```
