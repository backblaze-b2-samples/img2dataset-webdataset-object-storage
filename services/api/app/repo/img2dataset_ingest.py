"""The img2dataset ingest adapter — the golden-rule streaming write to B2.

This is the ONLY place ``img2dataset`` / ``s3fs`` / ``fsspec`` are used. It wraps
``img2dataset.download(...)`` and points its S3 output straight at a corpus
prefix in Backblaze B2, so images are fetched, resized, and packaged into
WebDataset ``.tar`` shards (+ metadata parquet + per-shard ``_stats.json``) and
streamed to B2 with no local staging.

Endpoint config (the single biggest implementation risk — done here, right
before ``download()``): img2dataset writes through fsspec/s3fs, so the B2
endpoint + credentials are supplied via fsspec's config
(``FSSPEC_S3_KEY`` / ``FSSPEC_S3_SECRET`` / ``FSSPEC_S3_CLIENT_KWARGS``). The
endpoint is derived from ``B2_REGION`` (no hardcoded region string). Crucially
that config is applied to fsspec's *live* config dict as well as to the
environment — see ``_configure_b2_fsspec_env`` for why exporting the variables
alone is not enough.

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

import contextlib
import json
import logging
import os
import signal
import threading

from app.config import settings
from app.repo import corpus_store

logger = logging.getLogger(__name__)

# Captured once, at import, so nested/concurrent guards can never restore a
# stand-in over the real function (see _suppressed_signal_registration).
_REAL_SIGNAL_SIGNAL = signal.signal
_signal_guard_lock = threading.Lock()
_signal_guard_depth = 0

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

    Applied in TWO places, because one alone is not enough:

    1. ``os.environ`` — img2dataset fans shards out to *spawned* worker
       processes (``multiprocessing`` "spawn" context). Each child imports
       fsspec fresh and picks the settings up from the environment it inherits.
    2. ``fsspec.config.conf`` — fsspec scans ``FSSPEC_*`` exactly ONCE, at
       import time (module-level ``set_conf_env(conf)`` in ``fsspec/config.py``).
       In this long-lived API process fsspec may already be imported by the time
       an ingest runs — by ``import img2dataset`` itself, by the webdataset
       preview, or by any future import — and its config cache is then frozen
       empty, so exporting the variables would silently do nothing and every
       write would fail with "Unable to locate credentials". Writing fsspec's
       live config dict makes this correct regardless of import order, for the
       first ingest and every later one in the same worker.

    Applied at call time rather than at import so a mocked build never touches
    the network and so the region-derived endpoint is always current. The
    endpoint comes from ``settings.endpoint_url`` (derived from ``B2_REGION``);
    no region string is hardcoded.
    """
    key = settings.b2_application_key_id
    secret = settings.b2_application_key
    client_kwargs = {
        "endpoint_url": settings.endpoint_url,
        "region_name": settings.b2_region,
    }

    os.environ["FSSPEC_S3_KEY"] = key
    os.environ["FSSPEC_S3_SECRET"] = secret
    os.environ["FSSPEC_S3_CLIENT_KWARGS"] = json.dumps(client_kwargs)

    # Deferred like the img2dataset import: importing this module must stay
    # cheap, and fsspec stays confined to this adapter.
    import fsspec.config

    fsspec.config.conf.setdefault("s3", {}).update(
        {"key": key, "secret": secret, "client_kwargs": client_kwargs}
    )


def _ignore_signal_registration(signalnum, handler):
    """Stand-in for ``signal.signal``: registers nothing, reports the current handler."""
    del handler  # deliberately dropped — that is the point of the stand-in
    return signal.getsignal(signalnum)


@contextlib.contextmanager
def _suppressed_signal_registration():
    """Stop ``download()`` from installing its CLI SIGINT handler.

    ``img2dataset.download`` registers a process-global SIGINT handler that
    deletes its temp dir and calls ``sys.exit(0)`` — right for its CLI, wrong
    twice over inside this API:

    * ingests run on a background worker thread, and ``signal.signal`` raises
      ``ValueError: signal only works in main thread of the main interpreter``
      there, so EVERY ingest dies before a single shard is written;
    * even on the main thread it would replace the server's own Ctrl-C handling
      with img2dataset's ``sys.exit(0)``, so one ingest would silently change
      how the whole API shuts down.

    Registration is neutralized only for the duration of the call (refcounted,
    so concurrent ingests can't restore it early) and the real
    ``signal.signal`` is put back afterwards. Handlers already installed by
    uvicorn/the app are never touched — this only makes img2dataset's
    registration a no-op.
    """
    global _signal_guard_depth
    with _signal_guard_lock:
        _signal_guard_depth += 1
        if _signal_guard_depth == 1:
            signal.signal = _ignore_signal_registration
    try:
        yield
    finally:
        with _signal_guard_lock:
            _signal_guard_depth -= 1
            if _signal_guard_depth == 0:
                signal.signal = _REAL_SIGNAL_SIGNAL


def s3_output_folder(corpus_id: str) -> str:
    """s3://<bucket>/img2dataset/<corpus-id>/shards — where shards land in B2.

    A sub-folder of the corpus prefix, never the prefix itself: ``download()``
    runs with ``incremental_mode="overwrite"``, which recursively deletes its
    output folder first. Pointing it at the corpus prefix would delete the
    corpus's own ``manifest.json`` on every run (see ``corpus_store``).
    """
    prefix = corpus_store.shards_prefix(corpus_id).rstrip("/")
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
    # Configure BEFORE the heavy import so a first-ever fsspec import in this
    # process already sees the credentials; _configure_b2_fsspec_env also fixes
    # up fsspec's live config, so the ordering here is defence in depth, not the
    # thing correctness depends on.
    _configure_b2_fsspec_env()

    from img2dataset import download  # deferred heavy import (see module docs)

    output_folder = s3_output_folder(corpus_id)
    logger.info(
        "img2dataset ingest starting: corpus=%s output=%s format=%s size=%s",
        corpus_id,
        output_folder,
        output_format,
        image_size,
    )
    with _suppressed_signal_registration():
        download(
            url_list=url_list_path,
            output_folder=output_folder,
            input_format=input_format_for(url_list_path),
            output_format=output_format,
            url_col="url",
            caption_col="caption",
            image_size=image_size,
            resize_mode=resize_mode,
            # Small, macOS-spawn-safe local demo settings; production scales
            # these up.
            processes_count=settings.corpus_processes_count,
            thread_count=settings.corpus_thread_count,
            number_sample_per_shard=settings.corpus_samples_per_shard,
            timeout=settings.corpus_download_timeout,
            # Overwrite on re-ingest (the service deletes the prefix first, but
            # be explicit so a partial prior run can't be double-counted).
            incremental_mode="overwrite",
            encode_format="jpg",
            enable_wandb=False,
        )
    logger.info("img2dataset ingest finished: corpus=%s", corpus_id)
    return output_folder
