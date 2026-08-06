<!-- last_verified: 2026-08-06 -->
# Feature: Stream-Back Preview (WebDataset)

## Purpose
Prove that downstream training jobs can stream shards directly from B2 by GET-ing a `.tar` shard and iterating it with the real `webdataset` package to decode the first few `(image, caption)` pairs.

## Used By
- UI: the "Stream-back preview" grid on `/corpora/[id]`
- API: `GET /corpora/{corpus_id}/preview`

## Core Functions
- `services/api/app/repo/webdataset_preview.py` — `decode_samples()`; the ONLY place `webdataset` is imported
- `services/api/app/service/yield_reader.py` — `build_preview()`; picks the first `.tar` shard and GETs it from B2
- `apps/web/src/components/corpora/sample-preview-grid.tsx`

## Canonical Files
- Decode path: `services/api/app/repo/webdataset_preview.py`

## Inputs
- The first `.tar` shard of a corpus (source: B2 `get_object`)
- `corpus_preview_samples` (settings, default 8)

## Outputs
- `CorpusPreview`: shard_key + `PreviewSample[]` (key, caption, base64 PNG thumbnail, width, height), or a `note` explaining why it is empty

## Flow
- `build_preview` lists the corpus prefix, picks the first `.tar`, and GETs its bytes from B2
- `decode_samples` materializes the bytes to a temp file and iterates `wds.WebDataset(path, shardshuffle=False).decode("pil")` — exactly what a PyTorch/JAX `IterableDataset` training loop does
- For each sample it extracts the image (`jpg`/`png`/`webp`) and caption (`txt`, or the `.json` sidecar), builds a small PNG thumbnail, and stops at the sample limit

## Edge Cases
- No `.tar` shards (parquet/files output, or zero yield) → empty preview with a clear `note`
- One undecodable image → skipped, the rest still render (preview degrades gracefully)
- `webdataset` is pinned torch-optional → `import webdataset` and iteration work WITHOUT pulling torch (verified at clean install); no multi-GB dep is added for a thumbnail

## UX States
- Loading: 4 skeleton tiles
- Empty: "Nothing to stream back yet" with the note
- Loaded: a grid of decoded thumbnails with captions

## Verification
- Test files: `services/api/tests/test_corpus.py` (`test_preview_decodes_real_webdataset_shard`, `test_preview_note_when_no_tar`)
- Required cases: decode a real WebDataset tar (not mocked), empty-preview note for a non-webdataset corpus
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
