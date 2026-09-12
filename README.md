# braedach/spiderfoot — fix fork

This is a fork of [poppopjmp/spiderfoot](https://github.com/poppopjmp/spiderfoot) holding a specific set of bug fixes to the AI report-generation and scanning pipeline, pending merge upstream.

**→ For the actual project — docs, issues, general use — go to [poppopjmp/spiderfoot](https://github.com/poppopjmp/spiderfoot).**

**Pending PR:** [poppopjmp/spiderfoot#393](https://github.com/poppopjmp/spiderfoot/pull/393)

## ⚠️ Breaking change

`requirements.txt` no longer installs `sentence-transformers`/`torch` **at all**, as
of image tag `6.1.0-g529d9da2` and every commit/build after it. If you have
`SF_EMBEDDING_PROVIDER=sentence_transformer` set anywhere, it will **silently**
degrade to mock (fake, hash-derived) embeddings via that backend's existing
`ImportError` fallback — no error, no warning, just quietly wrong report content.
Set `SF_EMBEDDING_PROVIDER=fastembed` instead (the new default in both compose
files below) — same job, no torch, ~67MB instead of ~1GB+.

## What's fixed here

- AI report generation returning empty/generic output (nine stacked bugs — service registry access, DB wiring, event-column mapping, Qdrant never populated, timeouts too short)
- Scan progress API (`/progress`, `/progress/stream`) returning 404 for every scan
- Local embeddings switched from `sentence-transformers`+`torch` (~1GB+, mandatory regardless of backend choice, per PyPI's own metadata) to `fastembed` (onnxruntime-backed, ~67MB, no torch anywhere) — real semantic search at a fraction of the size, with an optional `fastembed-gpu` build for deployments with GPU passthrough
- Two Postgres connection leaks (`ConfigManager`, `AuthService`) — reads that never committed, leaving connections stuck open indefinitely
- Deleting a scan never cleaned up its vectors in Qdrant — fixed to delete by `scan_id` from the shared events collection
- AI reports silently capped at 500 analysed events per scan regardless of how many were actually indexed — now configurable (`SF_REPORT_MAX_EVENTS_PER_SCAN`)
- The generic `docker-compose.yml` + `docker/compose/*.yml` reference deployment had a real bug of its own: its general-purpose Celery worker still listened on the `scan` queue alongside the dedicated active-scanner worker, even though it lacks the recon tooling — scans could silently lose active modules depending on which worker claimed them

See the PR for full detail on each.

## Deploying this fork

Two reference compose files, covering different use cases:

- **`docker-compose.yml`** (+ `docker/compose/*.yml`) — builds every image from source locally, Traefik-fronted, feature-profiled (`--profile full` for everything, or pick individual profiles: `ai`, `scan`, `storage`, `monitor`, `scheduler`, `sso`). Build the base image first (`docker compose build base`), then everything else — see that file's own header comment for why.
- **`docker-compose-podman.yml`** — pulls this fork's own pre-built, pushed images (`ghcr.io/braedach/spiderfoot/spiderfoot-*`) instead of building anything locally. No Traefik, no profiles — just the core services needed to run scans and generate AI reports. Genuinely Podman-compatible (standard Compose syntax throughout). See its own header comment for required env vars and usage.

Both default local embeddings to `fastembed` — no API key, no GPU needed, though GPU passthrough is supported (see either file's comments) if you have it.
