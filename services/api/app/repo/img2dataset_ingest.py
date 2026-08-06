"""The img2dataset ingest adapter — the golden-rule streaming write to B2.

This is the ONLY place ``img2dataset`` / ``s3fs`` / ``fsspec`` are used. It wraps
``img2dataset.download(...)`` and points its S3 output straight at a corpus
prefix in Backblaze B2, so images are fetched, resized, and packaged into
WebDataset ``.tar`` shards (+ metadata parquet + per-shard ``_stats.json``) and
streamed to B2 with no local staging.

Endpoint config (the single biggest implementation risk — done here, right
before ``download()``): img2dataset writes through fsspec/s3fs, so the B2
endpoint + credentials are supplied via fsspec's JSON-valued env config
(``FSSPEC_S3_KEY`` / ``FSSPEC_S3_SECRET`` / ``FSSPEC_S3_CLIENT_KWARGS``). The
endpoint is derived from ``B2_REGION`` (no hardcoded region string).

UA note / justified exception: img2dataset's internal s3fs/aiobotocore client is
the OSS tool's own and exposes no user-agent hook, so the ``b2ai-…`` custom user
agent cannot be set on it (it is not a client this app constructs). The app's own
``get_s3_client()`` always carries the custom UA for every read/write the app
makes; see README ("img2dataset user-agent exception"). We never fake a UA into
img2dataset.

The heavy import is deferred to call time so importing this module (and the app)
stays fast and network-free — importing ``img2dataset`` pulls albumentations,
which otherwise runs an update check on import.
"""

from __future__ import annotations

import json
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)

# Map a stored url_list_source file to img2dataset's input_format token.
INPUT_FORMAT_BY_EXT = {
    ".tsv": "tsv",
    ".csv": "csv",
    ".parquet": "parquet",
    ".json": "json",
    ".jsonl": "jsonl",
    ".txt": "txt",
}


def input_format_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return INPUT_FORMAT_BY_EXT.get(ext, "tsv")


def _configure_b2_fsspec_env() -> None:
    """Point fsspec/s3fs (img2dataset's S3 output) at Backblaze B2.

    Set immediately before ``download()`` rather than at import so a mocked
    build never touches the network and so the region-derived endpoint is always
    current. The endpoint comes from ``settings.endpoint_url`` (derived from
    ``B2_REGION``); no region string is hardcoded.
    """
    os.environ["FSSPEC_S3_KEY"] = settings.b2_application_key_id
    os.environ["FSSPEC_S3_SECRET"] = settings.b2_application_key
    os.environ["FSSPEC_S3_CLIENT_KWARGS"] = json.dumps(
        {
            "endpoint_url": settings.endpoint_url,
            "region_name": settings.b2_region,
        }
    )


def s3_output_folder(corpus_id: str) -> str:
    """s3://<bucket>/img2dataset/<corpus-id> — where shards land in B2."""
    prefix = f"{settings.corpus_prefix}{corpus_id}".rstrip("/")
    return f"s3://{settings.b2_bucket_name}/{prefix}"


def run_ingest(
    corpus_id: str,
    *,
    url_list_path: str,
    output_format: str,
    resize_mode: str,
    image_size: int,
) -> str:
    """Run img2dataset for one corpus, streaming shards straight to B2.

    Returns the ``s3://`` output folder the shards were written to. Raises on
    failure. The real proof of success is objects appearing under the corpus
    prefix (verified live by the pipeline); ``download()`` returning is not
    treated as success by callers — the service re-reads the shard stats from B2.
    """
    from img2dataset import download  # deferred heavy import (see module docs)

    _configure_b2_fsspec_env()
    output_folder = s3_output_folder(corpus_id)
    logger.info(
        "img2dataset ingest starting: corpus=%s output=%s format=%s size=%s",
        corpus_id,
        output_folder,
        output_format,
        image_size,
    )
    download(
        url_list=url_list_path,
        output_folder=output_folder,
        input_format=input_format_for(url_list_path),
        output_format=output_format,
        url_col="url",
        caption_col="caption",
        image_size=image_size,
        resize_mode=resize_mode,
        # Small, macOS-spawn-safe local demo settings; production scales these up.
        processes_count=settings.corpus_processes_count,
        thread_count=settings.corpus_thread_count,
        number_sample_per_shard=settings.corpus_samples_per_shard,
        timeout=settings.corpus_download_timeout,
        # Overwrite on re-ingest (the service deletes the prefix first, but be
        # explicit so a partial prior run can't be double-counted).
        incremental_mode="overwrite",
        encode_format="jpg",
        enable_wandb=False,
    )
    logger.info("img2dataset ingest finished: corpus=%s", corpus_id)
    return output_folder
