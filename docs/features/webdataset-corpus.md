<!-- last_verified: 2026-08-06 -->
# Feature: WebDataset Corpus Builder

## Purpose
Configure and launch an img2dataset ingest job through a form, choosing output format, resize mode, image size, and URL-list source — the create/edit surface for the primary Corpus entity.

## Used By
- UI: `/corpora` "New corpus" dialog (create), `/corpora/[id]` "Edit" dialog (edit)
- API: `POST /corpora`, `PATCH /corpora/{corpus_id}`

## Core Functions
- `apps/web/src/components/corpora/corpus-form-dialog.tsx` — the create/edit dialog with Select/RadioGroup inputs
- `apps/web/src/lib/queries.ts` — `useCreateCorpus()`, `useUpdateCorpus()`
- `services/api/app/types/corpus.py` — `CorpusCreate` / `CorpusUpdate` validation; finite option Literals
- `services/api/app/service/corpus.py` — `create_corpus()`, `update_corpus()`

## Canonical Files
- Form exemplar: `apps/web/src/components/settings/settings-form.tsx`
- Corpus form: `apps/web/src/components/corpora/corpus-form-dialog.tsx`

## Inputs
- name: string (2–50), description: string (≤160, optional)
- output_format: webdataset | parquet | files (Select)
- resize_mode: border | keep_ratio | center_crop | no (Select)
- image_size: 256 | 384 | 512 (RadioGroup)
- url_list_source: seed | uploaded (RadioGroup); bucket_key (Select, uploaded only)

## Outputs
- A new `Corpus` record (create) or an updated name/description (edit)
- Ingest params are create-time immutable — the edit form shows them read-only

## Flow
- Create: fill the form → `POST /corpora` → ingest starts, redirect to the detail page. Finite-value fields are selectors (never free text); safe defaults are surfaced as placeholder/FormDescription hints (built-in seed list, 256px, border, webdataset) with no autofill button
- Edit: open pre-filled → change name/description → `PATCH /corpora/{id}`; the ingest parameters are displayed read-only because they determine the shard layout on B2

## Edge Cases
- name < 2 or > 50 chars → inline validation error
- url_list_source = uploaded with no file selected → "Pick an uploaded URL-list file"
- No TSV/CSV/parquet in the bucket → the uploaded-file selector is empty with a hint to upload one first

## UX States
- Empty: default create form with hint text
- Loading: "Saving…" on the submit button while the mutation is in flight
- Error: a toast with the API message

## Verification
- Test files: `services/api/tests/test_corpus.py` (`test_create_runs_ingest_and_reports_yield`, `test_update_only_name_and_description`), `apps/web/src/lib/api-contract.test.ts`
- Required cases: create happy path, edit name/description only (params preserved), finite-field validation
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
