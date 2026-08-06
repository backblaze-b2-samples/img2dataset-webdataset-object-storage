# Scaffold plan — `img2dataset-webdataset-object-storage`

Source of truth for the starter tree: `.claude/scratch/vcsk-32f8e9d1-ebd1-49b5-8f6a-1b3fbc59d82f/`
(fresh clone; the builder must NOT re-clone and must NOT read any sibling
`vibe-coding-starter-kit/` checkout). Parent standards: `../CLAUDE.md`.

---

## 1. Purpose

A **pure golden-rule ingest** sample: it shows ML engineers and data curators how to
bulk-download public image-text datasets straight into Backblaze B2 as reproducible,
ready-to-train **WebDataset** tar shards using the trending OSS tool
[`img2dataset`](https://github.com/rom1504/img2dataset) — no local staging disk, B2 as
the S3-compatible output target. A user provides (or picks a built-in) URL-caption list;
`img2dataset` fetches, resizes, and packages the images into `.tar` shards +
metadata parquet + per-shard `_stats.json`, streaming them directly to B2 via its S3
output. The app then **validates** yield by reading shard stats back from B2, and
proves training-time consumption by **streaming a shard back** through WebDataset's
`IterableDataset` and decoding a few (image, caption) pairs. Audience: people building
large-scale training corpora (LAION/DataComp-style) who want B2 as the durable,
S3-native home for their shards. No second API key — B2 credentials only.

---

## 2. Architecture delta from `vibe-coding-starter-kit`

The starter kit is the ceiling. Strip what this app doesn't need; keep the reusable
B2 scaffolding intact.

### KEEP (as-is — starter contract, non-negotiable)
- **UI kit / design system**: `apps/web/src/components/ui/**`, `globals.css` tokens,
  `/design` page and its `components/design/**`. Never edit generated `ui/` files.
- **Full-bucket File Explorer** — `/files` route, `app/files/`, `components/files/**`,
  and its sidebar entry. **Non-negotiable keep** (the plan's mandated keep). It browses
  the whole bucket; it is distinct from the sample-specific Corpora explorer added below.
- **Upload** — `/upload` route, `app/upload/`, `components/upload/**`, sidebar entry.
  Kept, and repurposed as the way to bring a **custom URL-list file** (TSV/parquet) into
  the bucket so a corpus job can reference it by key. No rework of the presigned
  direct-to-B2 upload mechanics.
- **Backend layered architecture** (`types → config → repo → service → runtime`), the
  B2 repo layer (`repo/b2_client.py`, `list_cache.py`, `counter.py`), health/metrics/
  ratelimit runtime, structural tests, contract tests, agent-docs gate, CI, infra config.
- Sidebar nav shell (Dashboard, Upload, Files, Settings + Design System utility link).

### TRIM (remove — this app doesn't need it)
- **Metadata-extraction feature** as the dashboard's centerpiece is not the story here;
  the generic per-file metadata panel in the File Explorer stays (it's part of the kept
  Files feature), but the **Dashboard** stops being about "recent uploads / metadata".
  Do NOT delete `service/metadata.py` / the `/files-by-key/detail` route (Files depends
  on them) — only the *dashboard framing* changes (see Adapt).
- No wholesale deletions of starter machinery. This sample is additive: it layers a
  corpus-ingest domain on top of the kept B2 scaffolding. (If the builder finds truly
  dead starter code after the dashboard rewrite, it may trim it, but the default is keep.)

### ADD (new for this sample)
- **Corpus domain (primary entity = "Corpus" = an img2dataset ingest job).** Backend:
  - `repo/img2dataset_ingest.py` — the adapter that wraps `img2dataset.download(...)`,
    configures s3fs for B2 (endpoint from region + creds), and runs a job to a corpus
    prefix in B2. This is the ONLY place the img2dataset / s3fs / fsspec imports live
    (mirrors the "external APIs wrapped in repo/" and "no boto3 outside repo/"
    invariants — img2dataset is the external S3-writing tool, so contain it here).
  - `repo/corpus_store.py` — reads/writes the corpus **manifest.json in B2** (system of
    record lives in the bucket, not on the server) and enumerates shards + `_stats.json`
    under a corpus prefix. Uses the existing `get_s3_client()` (custom-UA S3 client).
  - `repo/webdataset_preview.py` — GET a `.tar` shard from B2 and decode the first N
    `(image, caption)` samples for the preview (see feature 4).
  - `service/corpus.py` — corpus lifecycle orchestration (create/read/edit/delete/run),
    yield-stat aggregation, background-job status registry (in-memory, keyed by corpus id;
    durable truth is the B2 manifest so a restart re-derives corpora by listing the prefix).
  - `runtime/corpus.py` — the corpus router (routes in §3). New Pydantic models in
    `types/corpus.py`.
  - Seed data: `services/api/app/data/seed_urls.tsv` — ~24 rows of stable, license-clean
    placeholder image URLs (`https://picsum.photos/id/<N>/512/512`, Lorem Picsum /
    Unsplash-sourced, free to use, id-addressed → reproducible) with synthetic captions.
    Columns: `url`, `caption`. This is the default input so the demo needs no external
    dataset and no API key.
- **Corpora explorer (`/corpora`) — the mandated sample-specific asset explorer, scoped
  to the sample's own `img2dataset/` prefix** (satisfies "also ADD a sample-specific asset
  explorer scoped to the sample's own folder"). List view = corpus cards (name, status,
  image/shard counts, yield %, size) with New/Edit/Delete/Re-run actions; detail view =
  one corpus's shards + decoded sample thumbnails + stats. This is separate from the kept
  full-bucket File Explorer.
  - Frontend: `app/corpora/page.tsx` (list), `app/corpora/[id]/page.tsx` (detail),
    `components/corpora/**` (corpus-card, corpus-form create/edit, corpus-detail,
    shard-list, sample-preview-grid, yield-stats), a `Corpora` sidebar entry (Boxes /
    Database lucide icon), TanStack Query hooks in `lib/queries.ts`, client routes in
    `lib/api-client.ts`, shared types in `packages/shared/src/types.ts`.
- **Dashboard adapted** to corpus-ingest metrics (see §4 feature 6 / doc transforms).

### Note on the keep/add tension
Two explorers coexist by design: the **kept** full-bucket File Explorer (`/files`,
browses everything) and the **added** Corpora explorer (`/corpora`, scoped to
`img2dataset/`). This is exactly the required pattern — the bucket explorer is never
removed; the sample adds a folder-scoped view on top of it.

---

## 3. B2 surface (S3 operations)

All via the S3-compatible API with the custom user agent. **No b2-native API anywhere.**

| Op | Where | Purpose |
|----|-------|---------|
| `list_objects_v2` | `corpus_store` (scoped to `img2dataset/`), plus kept Files/stats | enumerate corpora, shards, `_stats.json`; list-cache reused |
| `put_object` | `corpus_store` | write/update `manifest.json` (create, edit) |
| `get_object` | `corpus_store`, `webdataset_preview` | read manifest.json, `_stats.json`, metadata parquet; stream `.tar` shard for preview |
| `head_object` | corpus_store / kept files | existence + size checks |
| `delete_object` (batched, prefix-scoped) | `corpus_store` | delete a corpus — **scoped to `img2dataset/<corpus-id>/` only** (never a bucket-wide wipe; honors the repo's scoped-delete safety rule) |
| **`put_object` (multipart) via s3fs** | `img2dataset_ingest` | img2dataset writes tar shards + parquet + stats directly to `s3://<bucket>/img2dataset/<corpus-id>/` — the golden-rule ingest, no local staging |
| presigned GET / PUT | kept Upload + Files | unchanged |

**b2-native justification:** none used. Two S3 clients exist: (a) the app's own
`get_s3_client()` in `repo/b2_client.py` with `user_agent_extra` set — used by every
app read/write; (b) img2dataset's internal s3fs/aiobotocore client for the bulk write.
Standard #2 (custom UA on every S3 client the app constructs) is satisfied by (a).
img2dataset's client is the OSS tool's own and does not expose a UA hook — **record this
as an explicit, justified exception in the plan/README** (the sample can't set a UA on a
third-party tool's client; the app's own client always carries it). Do not fake a UA
into img2dataset.

**Endpoint config for img2dataset → B2 (the single biggest implementation risk — get it
provably right, not a false green):** img2dataset writes output through fsspec/s3fs.
Configure the B2 endpoint + creds in the `img2dataset_ingest` adapter immediately before
calling `download(...)`, using fsspec's env-var config (JSON-valued `FSSPEC_S3_*`):
`FSSPEC_S3_KEY`, `FSSPEC_S3_SECRET`, and
`FSSPEC_S3_CLIENT_KWARGS='{"endpoint_url":"https://s3.<region>.backblazeb2.com"}'`
(equivalently an `~/.config/fsspec/*.json` config, or `client_kwargs` storage options if
the pinned img2dataset version accepts them). **The builder MUST verify empirically that
shards actually land in B2** against the pinned version — that `download()` returning is
not treated as success; the real proof (deferred to the live verify pipeline step) is
objects appearing under the corpus prefix. In the credential-free build suite, the s3fs
boundary is mocked (see §4 verification).

---

## 4. Key features

> **No external API provider. No Genblaze** (the description does not mention
> Genblaze/`genblaze-*`/`genblaze-s3`, so provider routing via Genblaze does not apply).
> The heavy workload (download + PIL resize + tar packaging) is **`deployment: local`** —
> it runs on-device, network- and CPU-bound, no GPU, no model, no second key. It inherits
> the CPU-default rule trivially (nothing to autodetect; there is no accelerated path).
> Estimated cost for one full demo run: **$0** (picsum.photos is free/keyless; B2 storage
> for ~24 small JPEGs is negligible). Env var for a provider key: **none** beyond `B2_*`.

1. **Streaming ingest to B2 (`img2dataset`)** — `deployment: local`. Downloads + resizes
   + packages images into WebDataset `.tar` shards written directly to B2 via its S3
   output; no local staging. Pin `processes_count=1` (small, macOS-spawn-safe) for the
   local demo; document that production scales `processes_count`/`thread_count` up. Runs
   in a background thread; status tracked per corpus id.
2. **WebDataset corpus builder** — configure and launch a job: `output_format`
   (webdataset | parquet | files), `resize_mode` (border | keep_ratio | center_crop | no),
   `image_size` (256 | 384 | 512), URL-list source (built-in seed list | a bucket key of an
   uploaded TSV/parquet), corpus name/description. Writes shards under
   `img2dataset/<corpus-id>/`.
3. **Yield validation** — read every per-shard `_stats.json` (and the metadata parquet)
   back from B2, sum `count` / `successes` / `failed_to_download`, report download
   yield % and total corpus bytes. Surfaces honestly if a run yielded 0 (e.g. seed host
   unreachable) rather than showing a false green.
4. **Stream-back preview (WebDataset `IterableDataset`)** — `deployment: local`. GET a
   `.tar` shard from B2 and iterate it with `webdataset` (`wds.WebDataset(...).decode("pil")`)
   to pull the first N `(image, caption)` pairs; return small base64 thumbnails + captions
   to prove "downstream training jobs stream shards directly from B2." **Vendor fidelity:**
   use the real `webdataset` package (this is the headline Serve/Query claim). Pin a
   torch-optional `webdataset` version so `import webdataset` + `WebDataset(...)` iteration
   works **without pulling torch**; verify at clean install. If the pinned version hard-requires
   torch, prefer bumping webdataset; only as a documented last resort, decode with stdlib
   `tarfile` + Pillow while keeping the real `wds.WebDataset` snippet in the training-consumption
   doc. Do NOT add a multi-GB torch dependency just for a thumbnail preview.
5. **Corpora explorer (sample-specific, `img2dataset/`-scoped)** — the added asset
   explorer: corpus cards + per-corpus shard list and decoded sample grid. Distinct from
   the kept full-bucket File Explorer.
6. **Ingest dashboard** — replaces the starter's upload dashboard: stat cards (corpora
   built, images ingested, shards written, aggregate yield %, total corpus bytes in B2),
   an activity chart (images ingested per corpus, or per day), and a recent-corpora table.
   All aggregations flow `runtime → service → repo` and are exposed via TanStack Query
   hooks (no bare `useEffect + fetch`).

### Primary-entity lifecycle — entity = **Corpus** (all five verbs built in the UI)

| Verb | UI | Backend route | B2 op |
|------|----|--------------|-------|
| **create** | "New corpus" dialog form on `/corpora` | `POST /corpora` | write `manifest.json` (status=running) → run img2dataset → update manifest (complete + stats) |
| **read** | `/corpora` list + `/corpora/[id]` detail | `GET /corpora`, `GET /corpora/{id}`, `GET /corpora/{id}/shards`, `GET /corpora/{id}/preview` | list prefix, get manifest/stats, stream shard |
| **edit** | "Edit corpus" form (pre-filled) | `PATCH /corpora/{id}` | get→mutate name/description→put manifest (ingest params are create-time immutable, shown read-only) |
| **delete** | Delete button + `AlertDialog` confirm | `DELETE /corpora/{id}` | list corpus prefix → **prefix-scoped batch delete** |
| **run** | "Re-run ingest" button | `POST /corpora/{id}/reingest` | re-execute img2dataset with the stored config, overwrite shards, update manifest |

`omitted_ui_verbs`: **none** — every verb is user-accessible and built. (Empty array in
build-result.json.)

### Form UX conventions (create/edit corpus forms) — follow `settings-form.tsx` exemplar
- **Finite-value fields use selectors, never free text** (both create and edit):
  `output_format`, `resize_mode`, `image_size`, and `url_list_source` → shadcn `Select` /
  `RadioGroup` (segmented). Follow the `Select`/`RadioGroup` + `FormField` pattern already
  in `settings-form.tsx`.
- **Free-text fields**: corpus `name` (required, 2–50 chars), `description` (optional,
  ≤160), optional `bucket_key` (only when `url_list_source = uploaded file`).
- **CREATE form default hints via placeholder / `FormDescription`** (guidance only, NO
  autofill button): e.g. "Defaults to the built-in 24-image sample list — a sound test
  run with no external data", image_size default 256, resize_mode "border", output_format
  "webdataset". The **edit** form opens pre-filled from the real corpus manifest (no
  default hints), with ingest params shown read-only.

### Verification posture (build phase, credential-free)
- New routes get pytest coverage; the s3fs/img2dataset/B2 boundary is **mocked** so
  `pnpm test:api` and `pnpm verify` stay credential-free and network-free (no live picsum
  fetch, no live B2 in the canonical suite). Live ingest is proven later by the verify
  pipeline step.
- Every route change re-exports `docs/api/openapi.json` (`pnpm contract:export`);
  backend-only routes (if any) added to `SERVER_ONLY_OPERATIONS`. Frontend
  `API_CLIENT_ROUTES` kept in sync (`apps/web/src/lib/api-contract.test.ts`).
- Keep `pnpm check:agent-docs`, structural tests, branding (one `b2ai-…` token across
  `user_agent_extra` + `utm_content`), and APP_NAME single-source gates green.

---

## 5. Doc transforms

- **README.md** — full rewrite: img2dataset → WebDataset on B2 story, quick start (seed
  list, run a corpus, validate, preview), the img2dataset-UA exception note, keep the
  Backblaze links but swap the project slug + `utm_content` token. Screenshots are added
  by a later pipeline step — leave the image placeholders/paths but don't fabricate images.
- **docs/features/** — rewrite/replace:
  - `dashboard.md` → rewrite to the ingest dashboard (corpus metrics).
  - `file-upload.md`, `file-browser.md` → keep (still accurate for kept Upload/Files),
    light edits for the URL-list-upload framing.
  - `metadata-extraction.md` → keep (Files still uses it) or trim to reflect it's now only
    the File Explorer's per-file panel.
  - `settings.md` → keep (Settings is kept, lightly adapted).
  - **New stubs** (from `_template.md`): `corpus-ingest.md`, `webdataset-corpus.md`,
    `yield-validation.md`, `stream-back-preview.md`, `corpora-explorer.md` (one per §4
    feature 1–5). Each stub filled with real Used-By / Inputs / Outputs / Flow / Verify.
- **docs/app-workflows.md** — add the corpus lifecycle journey (create → ingest → validate
  → preview → re-run/delete).
- **ARCHITECTURE.md** — add the corpus domain (new repo/service/runtime modules, the B2
  manifest-as-system-of-record, the img2dataset s3fs write path).
- **AGENTS.md + shims** — update the "Building on this starter kit" adapt/keep notes only
  if the identity/branding surface changes require it; register nothing new in
  `check-agent-docs.mjs` unless a new agent shim is added (none is). Keep AGENTS.md within
  its size gate.
- **docs/exec-plans/** — the completed initial-scaffold plan lands here on PASS (Phase 5).

---

## 6. Rename table

| From (`vibe-coding-starter-kit`) | To (`img2dataset-webdataset-object-storage`) |
|---|---|
| repo / root `package.json` name `vibe-coding-starter-kit` | `img2dataset-webdataset-object-storage` |
| `@vibe-coding-starter-kit/shared` (pkg name + all imports) | `@img2dataset-webdataset-object-storage/shared` |
| `@vibe-coding-starter-kit/web` | `@img2dataset-webdataset-object-storage/web` |
| APP_NAME display `"Vibe Coding Starter Kit"` (`app-config.ts`) | `"img2dataset → WebDataset on B2"` |
| APP_DESCRIPTION | `"Bulk-download image-text datasets into Backblaze B2 as reproducible WebDataset shards with img2dataset."` |
| API_TITLE `"Vibe Coding Starter Kit API"` / description (`main.py`) | **must derive from APP_NAME** (branding gate) → `"img2dataset → WebDataset on B2 API"` |
| `user_agent_extra="b2ai-oss-start"` (`b2_client.py`) | `b2ai-img2dataset-webdataset-object-storage` |
| `utm_content=b2ai-oss-start` (all Backblaze links: sidebar, README) | `b2ai-img2dataset-webdataset-object-storage` (ONE token, must match the UA — branding gate) |
| README project-page slug `/projects/vibe-coding-starter-kit/` | `/projects/img2dataset-webdataset-object-storage/` |
| railway/vercel service names + image tags `vibe-coding-starter-kit*` | `img2dataset-webdataset-object-storage*` |
| **Env vars (standardize to parent CLAUDE.md #3 — every recent sample does this):** | |
| `B2_KEY_ID` / `b2_key_id` | `B2_APPLICATION_KEY_ID` / `b2_application_key_id` |
| `B2_ENDPOINT` (required) | derive endpoint from `B2_REGION` / `b2_region` as `https://s3.<region>.backblazeb2.com` (property), optional `B2_ENDPOINT` override kept empty by default |
| `B2_PUBLIC_URL` / `b2_public_url` | `B2_PUBLIC_URL_BASE` / `b2_public_url_base` |
| `B2_APPLICATION_KEY`, `B2_BUCKET_NAME` | unchanged (already standard) |

Standardizing env vars means updating: `.env.example`, `settings.py` (fields + derived
`b2_endpoint` property), `main.py` (`REQUIRED_B2_SETTINGS`, `PLACEHOLDER_VALUES`),
`b2_client.py` (creds from new fields), `setup_b2_cors.py`, `doctor.mjs`/setup scripts,
any tests referencing the old names, and docs. Match the exact pattern in
`open3d-point-cloud-pipeline` / `nemo-curator-training-data` (region-derived endpoint +
optional override). Keep all `check:agent-docs` / branding / contract gates green.
