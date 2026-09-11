# braedach/spiderfoot — fix fork

This is a fork of [poppopjmp/spiderfoot](https://github.com/poppopjmp/spiderfoot) holding a specific set of bug fixes to the AI report-generation and scanning pipeline, pending merge upstream.

**→ For the actual project — docs, issues, general use — go to [poppopjmp/spiderfoot](https://github.com/poppopjmp/spiderfoot).**

**Pending PR:** [poppopjmp/spiderfoot#393](https://github.com/poppopjmp/spiderfoot/pull/393)

## What's fixed here

- AI report generation returning empty/generic output (nine stacked bugs — service registry access, DB wiring, event-column mapping, Qdrant never populated, timeouts too short)
- Scan progress API (`/progress`, `/progress/stream`) returning 404 for every scan
- CPU-only `torch` — the default PyPI wheel pulls in ~5GB of unused CUDA/nvidia runtime regardless of whether a GPU exists
- Two Postgres connection leaks (`ConfigManager`, `AuthService`) — reads that never committed, leaving connections stuck open indefinitely

See the PR for full detail on each.
