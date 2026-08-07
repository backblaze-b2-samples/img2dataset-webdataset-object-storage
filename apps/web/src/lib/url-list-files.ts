/**
 * Which stored B2 objects may be offered as an img2dataset URL list.
 *
 * The corpus create dialog used to list every `.tsv` / `.csv` / `.parquet` in
 * the whole bucket. That buried the user's own uploads under the app's OWN
 * ingest output — img2dataset writes a metadata
 * `img2dataset/<corpus-id>/shards/00000.parquet` per shard, so after a few
 * corpora the picker was almost entirely internal artifacts, any of which
 * could be selected and then ingested as if it were a URL list.
 *
 * The picker is therefore scoped to the prefix the Upload page writes into.
 */

/**
 * Prefix the Upload page stores into — mirrors `UPLOAD_PREFIX` in
 * `services/api/app/service/upload.py`. Keep the two in sync.
 */
export const UPLOAD_PREFIX = "uploads/";

/** Extensions the img2dataset URL-list parser accepts for an uploaded list. */
export const URL_LIST_EXTS = [".tsv", ".csv", ".parquet"];

/**
 * True for a user-uploaded object img2dataset can parse as a URL list.
 *
 * The listing is already narrowed to `UPLOAD_PREFIX` server-side; re-asserting
 * the prefix here means a wider listing (or a cached one from another call
 * site) still can't leak the app's own `img2dataset/` output into the picker.
 */
export function isUrlListFile(objectKey: string): boolean {
  const lower = objectKey.toLowerCase();
  return (
    lower.startsWith(UPLOAD_PREFIX) &&
    URL_LIST_EXTS.some((ext) => lower.endsWith(ext))
  );
}
