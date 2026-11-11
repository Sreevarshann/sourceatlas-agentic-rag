# Prompt-injection threat model

**Assets:** answer integrity, citations, the system prompt, the user's trust.
**Untrusted inputs:** uploaded documents, fetched web pages, and model output.

| Vector | Mitigation |
|---|---|
| Instructions embedded in documents/web pages ("ignore previous instructions…") | Sentences matching instruction patterns are **removed before the passage reaches the model**; the passage is marked `sanitized`, and the removed text is stored and shown under "Quarantined text". |
| Instructions that evade the pattern | Evidence is wrapped in `<evidence>` and the system prompt declares it data; more importantly, any claim must pass citation verification, so an injected *fact* is accepted only if it is literally stated by a non-quarantined passage. |
| Model fabricating sources | Citations must reference evidence shown in this request; invalid refs are reported. |
| Exfiltration via tools | The model has no tools: retrieval, fetching and storage are performed by code; the model only returns JSON that is validated. |
| Web pages as an SSRF vector | See SECURITY.md (resolved-IP checks, pinning, redirect re-validation). |

Verified by: `tests/test_research.py` (planted injection is stripped, legitimate content
kept, payload never in a supported claim), the benchmark's `partner_discount` and
`inject_warranty` questions, and the live test run.

**Residual risk:** pattern-based detection can be evaded; a malicious document that
states false facts *as facts* (not as instructions) will be cited faithfully. Provenance
and the conflict detector are the mitigations, not a guarantee.
