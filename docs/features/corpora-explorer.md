<!-- last_verified: 2026-08-06 -->
# Feature: Corpora Explorer

## Purpose
Browse the sample's own ingest artifacts — a folder-scoped view of the `img2dataset/` prefix — distinct from, and alongside, the kept full-bucket File Explorer.

## Used By
- UI: `/corpora` (list of corpus cards) and `/corpora/[id]` (one corpus's shards + decoded sample grid)
- API: `GET /corpora`, `GET /corpora/{corpus_id}`, `GET /corpora/{corpus_id}/shards`, `GET /corpora/{corpus_id}/preview`, `GET /corpora/{corpus_id}/progress`

## Core Functions
- `apps/web/src/components/corpora/corpora-list.tsx`, `corpus-card.tsx` — the scoped list view
- `apps/web/src/components/corpora/corpus-detail.tsx` — detail view with all five verbs' actions
- `apps/web/src/components/corpora/shard-list.tsx`, `sample-preview-grid.tsx`, `yield-stats.tsx`, `corpus-ingest-progress.tsx`
- `apps/web/src/components/corpora/corpus-status-badge.tsx` — the one status pill every surface renders (list, detail, dashboard table)
- `apps/web/src/lib/corpus-labels.ts` — the single source of truth for the plain-English enum labels
- `apps/web/src/lib/queries.ts` — `useCorpora()`, `useCorpus()`, `useCorpusShards()`, `useCorpusPreview()`, `useCorpusProgress()`

## Canonical Files
- List: `apps/web/src/components/corpora/corpora-list.tsx`
- Detail: `apps/web/src/components/corpora/corpus-detail.tsx`

## Inputs
- None to browse; a corpus id for the detail route

## Outputs
- Read-only views of corpora and their shards/samples. Mutations (create/edit/delete/re-run) are surfaced here but implemented by the corpus lifecycle features.

## Flow
- `/corpora` lists corpus cards (name, status, images/shards/yield, size) with a "New corpus" action; it polls while any corpus is ingesting
- Clicking a card opens `/corpora/[id]`: configuration, yield validation, the stream-back preview grid, and the shard list — plus Re-run, Edit, and Delete
- A corpus's stored enums (`webdataset`, `center_crop`, `no`) are never shown raw: every surface — create dialog, detail Configuration card, list card — renders them through `lib/corpus-labels.ts`, so one value reads the same everywhere
- Status is legible at a glance, not by reading the label: blue = ingesting, green = complete, red = failed, each with its own icon (spinner / check / cross) so colour is never the only cue
- This view is scoped to `img2dataset/`; the full-bucket File Explorer at `/files` is unchanged and browses everything

## Edge Cases
- No corpora → empty state with a "New corpus" CTA
- API error → inline error state with retry
- Detail route for a deleted/unknown id → 404 surfaced as an error state

## UX States
- Loading: skeleton cards / detail skeleton
- Empty: "No corpora yet"
- Ingesting: blue "Ingesting" badge plus, on the detail page, the live progress card (see [Corpus Ingest](corpus-ingest.md))
- Loaded: corpus cards, then a full detail page

## Verification
- Test files: `services/api/tests/test_corpus.py`, `apps/web/src/lib/api-contract.test.ts`, `apps/web/src/lib/corpus-labels.test.ts`, `apps/web/src/components/corpora/corpus-status-badge.test.ts`
- Required cases: list/read happy path, contract routes present in the OpenAPI artifact, every stored enum value having a label (no raw token can reach a screen), and each status badge resolving to a visually distinct token set (success is never a red)
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
