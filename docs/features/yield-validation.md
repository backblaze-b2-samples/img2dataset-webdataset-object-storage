<!-- last_verified: 2026-08-06 -->
# Feature: Yield Validation

## Purpose
Prove how many URLs actually became training images by reading each shard's `_stats.json` back from B2 — the honest measure of ingest quality, never a false green.

## Used By
- UI: the "Yield validation" card and shard list on `/corpora/[id]`; dashboard aggregate
- API: `GET /corpora/{corpus_id}` (metrics on the manifest), `GET /corpora/{corpus_id}/shards`

## Core Functions
- `services/api/app/service/yield_reader.py` — `collect_yield()`; reads every `_stats.json` + object sizes under the corpus prefix and aggregates
- `services/api/app/service/corpus.py` — `get_shards()`, and `_execute()` which stamps metrics onto the manifest
- `apps/web/src/components/corpora/yield-stats.tsx`, `shard-list.tsx`

## Canonical Files
- Yield aggregation: `services/api/app/service/yield_reader.py`

## Inputs
- Per-shard `_stats.json` on B2 (source: img2dataset output): count, successes, failed_to_download, failed_to_resize
- Object sizes listed from B2 for total corpus bytes

## Outputs
- `CorpusMetrics`: image_count, successes, failed, yield_pct, shard_count, total_bytes, total_bytes_human, duration_seconds
- `ShardStat[]`: per-shard success/attempted, failed downloads, tar key, size

## Flow
- After ingest, `collect_yield` lists the corpus prefix, reads each `_stats.json`, and matches each shard to its `.tar` (or `.parquet`) for size
- image_count = Σ count, successes = Σ successes, yield_pct = successes / image_count × 100
- total_bytes = sum of every object under the prefix except the manifest — the true footprint on B2
- Metrics are stamped onto the manifest at completion and re-derivable on demand via `/shards`

## Edge Cases
- 0 downloads succeeded → yield_pct = 0, reported honestly (not hidden)
- image_count = 0 (nothing attempted) → yield_pct = 0 with no division error
- A `_stats.json` that is unreadable/corrupt → skipped, not fatal
- parquet/files output (no `.tar`) → shard size falls back to the parquet size or 0

## UX States
- Loading: skeletons on the detail page while the manifest loads
- Empty: "No shards" in the shard list for a zero-yield run
- Loaded: yield % with a progress bar, success/fail counts, and the shard table

## Verification
- Test files: `services/api/tests/test_corpus.py` (`test_create_runs_ingest_and_reports_yield`, `test_corpus_stats_aggregate`)
- Required cases: multi-shard yield math, aggregate across corpora, zero-yield path
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
