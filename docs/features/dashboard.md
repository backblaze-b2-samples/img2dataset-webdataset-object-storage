<!-- last_verified: 2026-08-06 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance overview of img2dataset ingest into B2 — corpora built, images packaged into WebDataset shards, aggregate download yield, and total corpus bytes on B2.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /corpora/stats`, `GET /corpora`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 stat cards (corpora built, images ingested, aggregate yield %, corpus bytes on B2)
- `apps/web/src/components/dashboard/corpora-chart.tsx` — bar chart of images ingested per corpus
- `apps/web/src/components/dashboard/recent-corpora-table.tsx` — recent corpora with yield + status
- `apps/web/src/lib/queries.ts` — `useCorpusStats()`, `useCorpora()`
- `services/api/app/runtime/corpus.py` — `GET /corpora/stats` handler
- `services/api/app/service/corpus.py` — `get_corpus_stats()` aggregation
- `services/api/app/repo/corpus_store.py` — lists the `img2dataset/` prefix (shared list cache)

## Canonical Files
- Stats aggregation: `services/api/app/service/corpus.py` (`get_corpus_stats`)
- Dashboard cards: `apps/web/src/components/dashboard/stats-cards.tsx`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /corpora/stats` → `CorpusStats` (total_corpora, running, complete, failed, images_ingested, shards_written, aggregate_yield_pct, total_bytes, total_bytes_human)
- `GET /corpora` → `Corpus[]` for the chart and recent-corpora table (newest-first)

## Flow
- Page loads → TanStack Query fetches corpus stats and the corpus list
- Stat cards show corpora built, images ingested (sum of successes), aggregate yield %, and corpus bytes on B2
- The chart plots images-ingested-per-corpus for the newest few corpora
- The recent-corpora table links each corpus to its detail page with a yield % and a status badge
- The corpus list polls every 3s while any corpus is still ingesting, so a run's status flip and metrics appear without a manual refresh

## Edge Cases
- API unavailable → inline error state with retry rather than rendering zeros (which would lie about the bucket)
- No corpora yet → empty chart and table messages
- A corpus still running → contributes 0 to images/yield until its manifest flips to complete
- Bucket changed elsewhere → numbers can lag by up to `LIST_CACHE_TTL_SECONDS`; the app's own writes/deletes invalidate the cache

## UX States
- Loading: an on-screen "Loading ingest metrics…" notice with skeleton cards/chart/table
- Empty: "No corpora yet" / "No ingests yet"
- Loaded: populated cards, chart, table

## Verification
- Test files: `services/api/tests/test_corpus.py` (`test_corpus_stats_aggregate`)
- Required cases: stats aggregate across multiple corpora, empty state, per-corpus yield
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites in [Dev Workflows](../dev-workflows.md#commands) are available
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
