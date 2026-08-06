<!-- last_verified: 2026-07-30 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Corpora explorer (`/corpora`) — the primary domain: create/read/edit/delete/re-run corpus ingest jobs
  - Dashboard adapted to corpus-ingest metrics (corpora, images ingested, yield, bytes)
  - Full-bucket File browser + direct-to-B2 Upload (kept starter surface)
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - Corpus domain: img2dataset ingest to B2, yield validation, WebDataset stream-back preview
  - REST API for corpora, file upload, listing, deletion
  - B2 S3 integration via boto3; img2dataset streaming write via s3fs/fsspec
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (FileMetadata, UploadStats, etc.)
    config/                Settings loaded from environment
    repo/                  B2 S3 client (data access layer)
    service/               Business logic (upload, files, metadata)
    runtime/               FastAPI route handlers
  tests/                   pytest tests (structural + integration)
```

## Corpus Domain

The primary entity is a **Corpus** — an img2dataset ingest job. It has no
database: its system of record is a `manifest.json` in B2 at
`img2dataset/<corpus-id>/manifest.json`, alongside the WebDataset `.tar` shards,
metadata parquet, and per-shard `_stats.json` the ingest writes. A restart
re-derives every corpus by listing the `img2dataset/` prefix.

Modules (all within the standard layering):

- `types/corpus.py` — `Corpus`, `CorpusCreate/Update`, `ShardStat`, `CorpusMetrics`, `CorpusPreview`, `CorpusStats`; finite options (`OutputFormat`, `ResizeMode`, `ImageSize`, `UrlListSource`) as `Literal`s validated at the boundary
- `repo/corpus_store.py` — reads/writes the manifest and enumerates shards/stats; prefix-scoped `delete_under` refuses any non-`/`-terminated prefix
- `repo/img2dataset_ingest.py` — the ONLY place img2dataset/s3fs/fsspec are imported; configures the B2 fsspec endpoint (from `B2_REGION`) and calls `img2dataset.download(output_folder="s3://<bucket>/img2dataset/<id>", …)`
- `repo/webdataset_preview.py` — the ONLY place `webdataset` is imported; decodes a shard's first samples via `wds.WebDataset(...).decode("pil")`
- `service/corpus.py` — lifecycle (create/read/edit/delete/re-run) on a background daemon thread per corpus
- `service/yield_reader.py` — reads shard stats back from B2 and builds the stream-back preview (kept separate so both stay under 300 lines)
- `runtime/corpus.py` — the `/corpora` router

The **img2dataset user-agent exception**: img2dataset's internal s3fs/aiobotocore
client exposes no UA hook, so it does not carry the `b2ai-…` custom user agent.
That client is confined to `repo/img2dataset_ingest.py`; every S3 client the app
itself constructs (`repo/b2_client.get_s3_client`) always carries the custom UA.
See [README](README.md#the-img2dataset-user-agent-exception).

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`. img2dataset/s3fs/fsspec are confined to `app/repo/img2dataset_ingest.py` and `webdataset` to `app/repo/webdataset_preview.py`. All other layers interact with B2 through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No cross-layer mutable state**: Configuration is read-only after init, and no mutable state is shared *between* layers. Intra-layer caches/counters (the listing cache in `repo/list_cache.py`, the B2 connectivity cache in `repo/b2_client.py`, the download counter in `repo/counter.py`, the rate-limit and metrics state in `runtime/`) are module-local and guarded by a `threading.Lock`. The listing cache also owns the only background thread in the app: a stale entry is served immediately while that thread re-scans (stale-while-revalidate), and `main.lifespan` warms it once at startup so no user pays for the cold full-bucket scan.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys reject empty and path-traversal patterns; optional prefix confinement via `ALLOWED_KEY_PREFIX` (off by default).

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repository: `web` builds from the
  repository root because it consumes `packages/shared`; `api` builds from
  `services/api`. The versioned per-service configs and the human-approved
  staging/production contract live in [infra/railway/README.md](infra/railway/README.md).
- **Vercel** — one project using [Vercel Services](https://vercel.com/docs/services):
  the `web` (Next.js) and `api` (FastAPI) services build from the same repo and
  share one origin — the web app at `/`, the API under `/api`. The repo-root
  `vercel.json` declares both services and routes `/api/*` to the API service;
  the Vercel-only `services/api/index.py` strips the `/api` prefix so FastAPI
  keeps its native paths (`/health`, `/files`, …). Uploads go directly from the
  browser to B2 via a presigned PUT (see
  [File Upload](docs/features/file-upload.md)), so they bypass the Function's
  4.5 MB payload ceiling entirely — the bucket must allow the deploy origin in
  its CORS. A two-separate-Projects alternative and the full delivery contract
  live in [infra/vercel/README.md](infra/vercel/README.md).

External provisioning and deployment remain explicit user-approved actions.

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - All uploaded files stored in a single bucket
  - Corpus system of record: `manifest.json` per corpus under `img2dataset/<id>/`, plus its WebDataset `.tar` shards, metadata parquet, and `_stats.json`
  - File listing and metadata via S3 `list_objects_v2` / `head_object`
  - No application database — B2 is the sole data store

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling). A per-IP rate-limit middleware sits inner to CORS; see [docs/SECURITY.md](docs/SECURITY.md#rate-limiting).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Corpus ingest**: Browser -> `POST /corpora` (write `running` manifest) -> background thread: resolve URL list -> `img2dataset.download(... s3://<bucket>/img2dataset/<id>)` streams shards to B2 via s3fs -> read shard `_stats.json` back from B2 -> update manifest to `complete|failed`
- **Yield/preview**: Browser -> `GET /corpora/{id}` (manifest + metrics), `GET /corpora/{id}/shards` (re-derived stats), `GET /corpora/{id}/preview` (GET first `.tar` -> `wds.WebDataset` decode)
- **Corpus delete**: Browser -> `DELETE /corpora/{id}` -> service confirms existence -> prefix-scoped batch delete of `img2dataset/<id>/` only
- **Upload**: Browser -> `POST /upload/presign` (API validates + signs a PUT) -> Browser PUTs bytes **directly to B2** -> `POST /upload/verify` (API HEADs + Range-sniffs the stored object) -> response
- **List**: Browser -> `GET /files` -> service calls repo -> returns file list
- **Download**: Browser -> `GET /files/{key}/download` -> service validates key -> repo generates presigned URL -> browser downloads
- **Delete**: Browser -> `DELETE /files/{key}` -> service validates key -> repo deletes from B2

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## API Contract

- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export/check command: `pnpm contract:export` / `pnpm contract:check`
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The frontend client keeps a small `API_CLIENT_ROUTES` registry in
`apps/web/src/lib/api-client.ts`. Tests compare that registry to the checked-in
OpenAPI artifact so route changes fail loudly before the hand-written client can
silently drift from FastAPI. `GET /metrics` is intentionally server-only.

## Canonical Files

- Corpus router: `services/api/app/runtime/corpus.py`
- Corpus lifecycle: `services/api/app/service/corpus.py`
- img2dataset ingest adapter: `services/api/app/repo/img2dataset_ingest.py`
- WebDataset decode: `services/api/app/repo/webdataset_preview.py`
- Layered API handler: `services/api/app/runtime/upload.py`
- Service orchestration: `services/api/app/service/upload.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`files.py`, `upload.py`, `stats.py`, `formatting.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- OpenAPI contract: `docs/api/openapi.json`
- OpenAPI exporter: `services/api/scripts/export_openapi.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Corpus Ingest](docs/features/corpus-ingest.md)
- [WebDataset Corpus Builder](docs/features/webdataset-corpus.md)
- [Yield Validation](docs/features/yield-validation.md)
- [Stream-Back Preview](docs/features/stream-back-preview.md)
- [Corpora Explorer](docs/features/corpora-explorer.md)
- [File Upload](docs/features/file-upload.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)
- [Metadata Extraction](docs/features/metadata-extraction.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
