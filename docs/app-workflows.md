<!-- last_verified: 2026-08-06 -->
# App Workflows

User journeys inside the application.

## Build a Corpus (create → ingest → validate → preview → re-run/delete)

- User navigates to `/corpora` and clicks **New corpus**
- In the dialog, they name the corpus and pick the ingest parameters with
  selectors (never free text): output format, resize mode, image size, and
  URL-list source. Safe defaults are surfaced as hints — the built-in 24-image
  seed list, 256px, border, webdataset — with no autofill button
- Pressing **Create & ingest** writes a `running` manifest to
  `img2dataset/<corpus-id>/manifest.json` on B2 and launches `img2dataset` on a
  background thread; the browser redirects to the corpus detail page and polls
- **Ingest**: `img2dataset` downloads, resizes, and packages the images into
  WebDataset `.tar` shards (+ metadata parquet + per-shard `_stats.json`) and
  streams them straight to B2 via s3fs — no local staging. The status badge shows
  "Ingesting" until the manifest flips to "Complete" (or "Failed" with the error)
- **Validate**: the detail page reads every shard's `_stats.json` back from B2 and
  shows download yield %, success/fail counts, shard count, and bytes on B2 — a
  zero-yield run is reported honestly, not hidden
- **Preview**: the app GETs the first `.tar` shard and iterates it with the real
  `webdataset` package to decode the first few `(image, caption)` pairs, rendering
  them as thumbnails — proof a training loop can stream shards directly from B2
- **Edit**: the Edit dialog changes name/description only; ingest parameters are
  create-time immutable and shown read-only
- **Re-run ingest**: re-executes with the stored config, wiping and rebuilding the
  corpus's shards (scoped to its own prefix)
- **Delete**: an AlertDialog confirms, then a prefix-scoped batch delete removes
  the manifest and every shard under `img2dataset/<corpus-id>/` — and nothing else
- See: [Corpus Ingest](features/corpus-ingest.md), [Yield Validation](features/yield-validation.md), [Stream-Back Preview](features/stream-back-preview.md), [Corpora Explorer](features/corpora-explorer.md)

## Upload Files

- User navigates to `/upload`
- Drops or selects files in the dropzone
- Client validates file size (max 100MB) and type
- Files upload **directly from the browser to B2** (a presigned PUT). A determinate progress bar tracks the bytes leaving the browser; once they are all sent the row switches to "Verifying upload..." with an *indeterminate* sweeping bar while the API HEADs and magic-byte-sniffs the stored object. That phase has no percentage to report, and a bar parked at a full 100% read as finished-but-stuck
- On success: toast notification, green checkmark, and a "View in Files" link through to the browser
- On failure: red status icon with error message
- User can clear completed uploads
- The queue lives in an app-wide provider: navigating to another page keeps the upload running, shows an "Uploading N files" indicator in the header, and keeps the duplicate-upload guard armed
- Reloading or closing mid-upload asks for confirmation first; if the upload dies anyway, the next load says which file didn't finish
- See: [File Upload](features/file-upload.md)

## Browse and Manage Files

- User navigates to `/files`
- Page loads the 100 most recent objects from the API (sorted most recent first). While it loads, the page says so on screen and escalates the wording if the wait runs long — a full bucket listing measured 2.8s-21s cold
- If that limit was hit, a notice states how many objects the bucket actually holds — the page never claims to show everything
- Files displayed in tree view with folders and type-specific icons
- Folders auto-expand on load until the *majority* of the listed files are reachable without clicking, so the page's own "click a file" instruction is always actionable. Stopping at the first visible file was not enough: one stray top-level object left the other 99 sealed in collapsed folders while the page claimed to show 100
- Clicking a file row opens its preview; the per-row actions menu (preview / download / delete) is always visible, on every viewport
- Arriving at `/files?preview=<key>` expands that file's folders and opens its preview directly. This is how the ⌘K palette and the dashboard's recent-uploads rows hand off a *specific* file; the param is consumed on arrival so it doesn't re-fire later
- **Preview**: opens dialog with image/PDF preview + metadata panel, and the file's Download / Delete actions — the advertised "click a file" path offers everything the row menu does. The loading state holds until the media paints; a failure offers "Open in a new tab". The preview URL is signed with `Content-Disposition: inline` so PDFs render in place
- **Download**: shows a pending state on the row plus a toast while the presigned URL is fetched, then starts the download via an anchor click (which, unlike a popup, still works if the click's user activation expired during a slow presign). Failures are reported; the click can never silently do nothing
- **Delete**: the confirmation dialog stays open showing "Deleting..." until the request settles, then the row disappears with the toast (optimistic cache update) and the list reconciles with the server. The dialog is held deliberately — Radix closes on action click by default, which dismissed the only pending state and left the row looking untouched while the delete was still in flight
- Empty bucket shows "No files found" with upload prompt
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- TanStack Query loads corpus-ingest stats and the corpus list; the corpus list polls while any corpus is still ingesting
- While stats load, the page states it in words above the cards rather than showing silent skeletons
- Stats cards show: corpora built, images ingested, aggregate download yield %, and total corpus bytes on B2
- The chart shows images ingested per corpus for the newest few corpora
- The recent-corpora table lists corpora with a yield % and status badge; each name links to its detail page
- Empty state: "No corpora yet" messages
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User navigates to `/settings`
- A banner at the top states that the page is mostly a demonstration: only Theme is wired up for real, the rest showcases what a settings page can look like when you adapt the kit
- **Theme** (real): editing it and saving applies it immediately and persists it (`next-themes`), and the header's theme toggle drives the same state
- **Profile and preference fields** (demo): Display name, Bio, Default file view (Tree/List/Grid), Email me on every upload, Warn me when approaching quota + threshold. Each is labelled "Demo field", persists to `localStorage` only, and drives no behaviour — there is no account system, mailer, quota banner, activity log, or List/Grid view behind them yet
- Saving reports honestly: a success toast that separates the real theme change from the locally-stored demo values, or a warning toast if the browser blocked storage (theme still changes). It never claims a save that did not happen — the original page toasted "Settings saved" for fields that changed nothing
- Danger Zone actions are a demo — no real delete runs
- See: [Settings](features/settings.md)
