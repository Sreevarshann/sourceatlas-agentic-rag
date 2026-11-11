# Security

| Threat | Mitigation | Tests |
|---|---|---|
| Malicious uploads | Extension + magic-byte checks, 25 MB cap, PDF page cap, encrypted PDFs rejected, DOCX zip-size guard, no macro/JS execution, content-free parser errors | `test_extract.py`, `test_documents_api.py` |
| Path traversal | Filenames reduced to basename; storage paths are server-generated; file serving checks the resolved path stays in storage | `test_extract.py`, `test_documents_api.py` |
| Stored XSS via uploaded HTML | Originals served with `text/plain` for text types, `nosniff`, and `CSP: default-src 'none'; sandbox`; UI renders text via React escaping | `test_documents_api.py` |
| SQL injection | All queries are SQLAlchemy Core with bound parameters; user search text only enters `websearch_to_tsquery` as a parameter | `test_search.py` |
| SSRF (web ingest) | http(s) only, ports 80/443, no credentials, all resolved IPs must be public (blocks loopback, RFC1918, link-local/metadata 169.254.169.254, CGNAT, ULA), IP pinning, manual redirects re-validated, timeouts, size/content-type caps, optional allow-list | `test_web.py` |
| Prompt injection | See PROMPT_INJECTION.md | `test_research.py` |
| Fabricated citations / numbers | Claim verification | `test_research.py`, `test_benchmark.py` |
| Resource exhaustion | Bounded rounds/queries/claims, upload caps, LLM timeouts | — |
| Secrets | No secrets in code; local compose password is explicitly local-only; gitleaks scans history in CI | CI |

Single-tenant, unauthenticated local application: bind to localhost or deploy behind an
authenticating proxy. Multi-tenant authorisation is out of scope (see ReviewPilot).
