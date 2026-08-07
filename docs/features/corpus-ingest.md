<!-- last_verified: 2026-08-06 -->
# Feature: Corpus Ingest (img2dataset → B2)

## Purpose
Stream an image-text dataset straight into Backblaze B2 as WebDataset shards using `img2dataset`, with no local staging disk — the golden-rule ingest at the heart of this sample.

## Used By
- UI: `/corpora` "New corpus" dialog, the "Re-run ingest" button on `/corpora/[id]`, and the live "Ingest in progress" card on that page
- API: `POST /corpora`, `POST /corpora/{corpus_id}/reingest`, `GET /corpora/{corpus_id}/progress`
- Job: background daemon thread per corpus (`service/corpus._execute`)

## Core Functions
- `services/api/app/repo/img2dataset_ingest.py` — `run_ingest()`; the ONLY place img2dataset/s3fs/fsspec are imported, and where the B2 fsspec endpoint is configured
- `services/api/app/service/corpus.py` — `create_corpus()`, `reingest_corpus()`, `_execute()`, `_resolve_url_list()`, `get_progress()`
- `services/api/app/service/yield_reader.py` — `collect_progress()`, `pending_shard_count()`; live progress read back from B2
- `apps/web/src/components/corpora/corpus-ingest-progress.tsx` — the polling progress card
- `services/api/app/repo/corpus_store.py` — writes the `manifest.json` system of record
- `services/api/app/data/seed_urls.tsv` — built-in 24-row URL+caption seed list

## Canonical Files
- Ingest adapter: `services/api/app/repo/img2dataset_ingest.py`

## Inputs
- `CorpusCreate` (source): name, description, output_format, resize_mode, image_size, url_list_source (seed | uploaded), bucket_key
- URL list: the built-in seed TSV, or an uploaded TSV/CSV/parquet with `url`,`caption` columns (from B2)

## Outputs
- WebDataset `.tar` shards + metadata `.parquet` + per-shard `_stats.json` under `img2dataset/<corpus-id>/shards/` on B2
- `manifest.json` (at `img2dataset/<corpus-id>/manifest.json`, deliberately OUTSIDE the shards folder) flipped `running → complete|failed`
- Side effects: network downloads from the URL list; multipart writes to B2 via s3fs

## Flow
- `create_corpus` writes a `running` manifest and launches `_execute` on a daemon thread
- `_execute` resolves the URL list to a local file and wipes only `img2dataset/<id>/shards/`, so the manifest stays readable while the detail page polls
- `img2dataset_ingest.run_ingest` publishes the B2 credentials/endpoint (derived from `B2_REGION`) to BOTH `os.environ` (`FSSPEC_S3_KEY` / `FSSPEC_S3_SECRET` / `FSSPEC_S3_CLIENT_KWARGS`, read by img2dataset's spawned workers) and fsspec's live `config.conf` (this process scans those variables only once, at import), then calls `img2dataset.download(output_folder="s3://<bucket>/img2dataset/<id>/shards", …)` with img2dataset's CLI SIGINT handler suppressed — `signal.signal` raises on the worker thread the ingest runs on
- While `download()` runs, the detail page polls `GET /corpora/{id}/progress` every 2s. `download()` is one blocking call, so progress is measured from B2 instead: img2dataset writes each shard's `_stats.json` as that shard finishes and deletes the matching `_tmp/*.feather` input shard it planned up front, so **completed + pending is the real denominator**. The response carries stage, shards completed/total, images written/attempted, a derived percent, and elapsed seconds
- Nothing about that progress is timer-driven: if a run stalls, the counters stop moving instead of animating on. The percent stays `null` (indeterminate bar) until the shards have been planned
- After `download()` returns, the service re-reads the shard stats from B2 (see [Yield Validation](yield-validation.md)) — `download()` returning is NOT treated as success
- The manifest is updated to `complete` with shards + metrics, or `failed` with an error

## Edge Cases
- URL host unreachable / all downloads fail → corpus completes with 0 yield, surfaced honestly (not a false green)
- Uploaded source with no `bucket_key` → 400 at create time
- Second ingest while one is running → 409 conflict (in-process guard)
- img2dataset error / B2 outage → manifest marked `failed` with the message; the worker is never wedged

## UX States
- Empty: "No corpora yet" on `/corpora`
- Loading: the detail page shows an "Ingest in progress" card — stage, a determinate percent bar (indeterminate until the shards are planned), shards completed/total, images ingested, and elapsed time, all advancing as shards land on B2. The status badge shows "Ingesting" with a spinner; list/detail poll
- Error: red "Ingest failed" alert with the error on the detail page

## Verification
- Test files: `services/api/tests/test_corpus.py` (`test_create_runs_ingest_and_reports_yield`, `test_reingest_reruns_and_guards_concurrency`, `test_uploaded_source_requires_bucket_key`, `test_progress_advances_while_the_ingest_runs`, `test_progress_is_indeterminate_before_shards_are_planned`), `apps/web/src/components/corpora/corpus-ingest-progress.test.ts`
- Required cases: happy-path ingest, re-ingest + concurrency guard, uploaded-source validation, missing-source failure, and progress that advances mid-run only as shards land (plus no invented percent before they are planned). The s3fs/img2dataset/B2 boundary is mocked; a live ingest is proven by running the app.
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
