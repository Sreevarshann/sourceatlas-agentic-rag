# Demo walkthrough

```bash
make db && make setup && make seed     # SYNTHETIC Halcyon Devices corpus (needs Ollama for nomic embeddings)
make dev-api                           # :8112
cd frontend && npm install && npm run dev -- --port 3102
```

1. **Library** — 8 synthetic documents across 5 collections; filter by *Engineering*; note the
   manual has two versions.
2. **Studio** — ask *“What is the current return window for refunds?”*: watch the stages
   stream; the answer cites the 2025 policy; the *Conflicting sources* card shows the 2024
   policy (14 days) vs 2025 (30 days) with the newer marked.
3. Click a citation chip → the inspector shows the passage with context → *Open in document
   viewer*.
4. Ask *“How do I factory reset the Hub H2?”* → the answer uses manual **v2** (15 seconds);
   v1's 10 seconds is not searchable.
5. Ask *“What discount do authorised partners receive?”* → the inspector's *Quarantined text*
   shows the stripped injection sentence.
6. Ask *“What is the CEO's salary?”* → abstains.
7. **Evidence graph** tab → click a claim to highlight its supporting passages.
8. **Evaluation** → stored benchmark runs.
