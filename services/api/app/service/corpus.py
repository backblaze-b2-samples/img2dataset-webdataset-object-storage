"""Corpus lifecycle: create / read / update / delete / re-ingest.

A Corpus is an img2dataset ingest job whose system of record is a
``manifest.json`` in B2 (``img2dataset/<id>/manifest.json``) — no database, so a
restart re-derives every corpus by listing the prefix. ``create`` and
``reingest`` launch the ingest on a background daemon thread and flip the
manifest ``running -> complete|failed``; the frontend polls. All B2 access goes
through ``repo/`` (``corpus_store`` for objects/manifests, ``img2dataset_ingest``
for the streaming write, ``webdataset_preview`` for stream-back decode).
"""

import contextlib
import logging
import os
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.repo import corpus_store, img2dataset_ingest
from app.service import yield_reader
from app.types.corpus import (
    Corpus,
    CorpusCreate,
    CorpusPreview,
    CorpusStats,
    CorpusUpdate,
    ShardStat,
)
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_urls.tsv"

# In-process guard so two concurrent ingests for one corpus can't both launch.
_run_lock = threading.Lock()
_running: set[str] = set()


class CorpusNotFoundError(Exception):
    def __init__(self, detail: str = "Corpus not found"):
        self.detail = detail
        super().__init__(detail)


class CorpusConflictError(Exception):
    def __init__(self, detail: str = "Corpus is already ingesting"):
        self.detail = detail
        super().__init__(detail)


class CorpusValidationError(Exception):
    def __init__(self, detail: str = "Invalid corpus"):
        self.detail = detail
        super().__init__(detail)


def _now() -> datetime:
    return datetime.now(UTC)


def _save(corpus: Corpus) -> None:
    corpus_store.put_bytes(
        corpus_store.manifest_key(corpus.id),
        corpus.model_dump_json().encode("utf-8"),
        "application/json",
    )


def _load(corpus_id: str) -> Corpus | None:
    data = corpus_store.get_bytes(corpus_store.manifest_key(corpus_id))
    if data is None:
        return None
    return Corpus.model_validate_json(data)


def list_corpora() -> list[Corpus]:
    """Every corpus, newest first — one read per manifest under the prefix."""
    corpora: list[Corpus] = []
    for key in corpus_store.list_manifest_keys():
        data = corpus_store.get_bytes(key)
        if data is None:
            continue
        try:
            corpora.append(Corpus.model_validate_json(data))
        except ValueError:
            logger.warning("Skipping unreadable corpus manifest: %s", key)
    corpora.sort(key=lambda c: c.created_at, reverse=True)
    return corpora


def get_corpus(corpus_id: str) -> Corpus:
    corpus = _load(corpus_id)
    if corpus is None:
        raise CorpusNotFoundError()
    return corpus


def create_corpus(payload: CorpusCreate) -> Corpus:
    if payload.url_list_source == "uploaded" and not payload.bucket_key:
        raise CorpusValidationError(
            "Choose an uploaded URL-list file, or use the built-in seed list."
        )
    now = _now()
    corpus_id = uuid.uuid4().hex
    corpus = Corpus(
        id=corpus_id,
        status="running",
        prefix=corpus_store.corpus_prefix(corpus_id),
        created_at=now,
        updated_at=now,
        **payload.model_dump(),
    )
    _save(corpus)
    _launch(corpus_id)
    logger.info("Corpus created: id=%s name=%s", corpus_id, corpus.name)
    return corpus


def update_corpus(corpus_id: str, payload: CorpusUpdate) -> Corpus:
    """Edit name/description only — ingest params are create-time immutable."""
    corpus = get_corpus(corpus_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return corpus
    updated = corpus.model_copy(update={**updates, "updated_at": _now()})
    _save(updated)
    logger.info("Corpus updated: id=%s fields=%s", corpus_id, sorted(updates))
    return updated


def delete_corpus(corpus_id: str) -> None:
    # Confirm existence first (clean 404), then delete ONLY this corpus's own
    # prefix — never bucket-wide.
    get_corpus(corpus_id)
    corpus_store.delete_under(corpus_store.corpus_prefix(corpus_id))
    logger.info("Corpus deleted: id=%s", corpus_id)


def reingest_corpus(corpus_id: str) -> Corpus:
    """Re-run the ingest with the stored config, overwriting the shards."""
    corpus = get_corpus(corpus_id)
    with _run_lock:
        if corpus.status == "running" or corpus_id in _running:
            raise CorpusConflictError()
        _running.add(corpus_id)
    started = corpus.model_copy(
        update={"status": "running", "error": None, "updated_at": _now()}
    )
    _save(started)
    threading.Thread(target=_execute, args=(corpus_id,), daemon=True).start()
    logger.info("Corpus re-ingest started: id=%s", corpus_id)
    return started


def _launch(corpus_id: str) -> None:
    with _run_lock:
        _running.add(corpus_id)
    threading.Thread(target=_execute, args=(corpus_id,), daemon=True).start()


def _resolve_url_list(corpus: Corpus) -> tuple[str, bool]:
    """Return (local url-list path, is_temp) for the ingest.

    Seed uses the built-in TSV directly; an uploaded list is pulled from B2 to a
    temp file preserving its extension so img2dataset picks the right parser.
    """
    if corpus.url_list_source == "seed":
        return str(_SEED_PATH), False
    if not corpus.bucket_key:
        raise CorpusValidationError("Uploaded corpus has no URL-list bucket key")
    data = corpus_store.get_bytes(corpus.bucket_key)
    if data is None:
        raise CorpusValidationError(
            f"URL-list file not found in B2: {corpus.bucket_key}"
        )
    ext = os.path.splitext(corpus.bucket_key)[1] or ".tsv"
    fd, path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return path, True


def _execute(corpus_id: str) -> None:
    started_at = time.monotonic()
    url_list_path = None
    is_temp = False
    try:
        corpus = _load(corpus_id)
        if corpus is None:  # deleted between launch and here
            return
        # Re-ingest overwrites: wipe the prior prefix (scoped to this corpus
        # only) then restore the running manifest so shards rebuild cleanly. On
        # a first run the prefix holds only the manifest, so this is a no-op
        # beyond re-writing it.
        corpus_store.delete_under(corpus_store.corpus_prefix(corpus_id))
        _save(corpus)
        url_list_path, is_temp = _resolve_url_list(corpus)
        img2dataset_ingest.run_ingest(
            corpus_id,
            url_list_path=url_list_path,
            output_format=corpus.output_format,
            resize_mode=corpus.resize_mode,
            image_size=corpus.image_size,
        )
        shards, metrics = yield_reader.collect_yield(corpus_id)
        metrics = metrics.model_copy(
            update={"duration_seconds": round(time.monotonic() - started_at, 2)}
        )
        done = _load(corpus_id)
        if done is None:  # deleted mid-run
            return
        _save(
            done.model_copy(
                update={
                    "status": "complete",
                    "updated_at": _now(),
                    "shards": shards,
                    "metrics": metrics,
                }
            )
        )
        logger.info(
            "Corpus complete: id=%s images=%s yield=%.1f%%",
            corpus_id,
            metrics.image_count,
            metrics.yield_pct,
        )
    except Exception as exc:
        # Any failure (bad URL list, img2dataset error, B2 outage) becomes a
        # failed manifest rather than a wedged worker.
        logger.warning("Corpus ingest failed: id=%s err=%s", corpus_id, exc)
        _mark_failed(corpus_id, str(exc))
    finally:
        if is_temp and url_list_path:
            with contextlib.suppress(OSError):
                os.unlink(url_list_path)
        with _run_lock:
            _running.discard(corpus_id)


def _mark_failed(corpus_id: str, detail: str) -> None:
    corpus = _load(corpus_id)
    if corpus is None:
        return
    _save(corpus.model_copy(update={"status": "failed", "error": detail, "updated_at": _now()}))


def get_shards(corpus_id: str) -> list[ShardStat]:
    """The corpus's shard stats (re-derived from B2 so they're never stale)."""
    get_corpus(corpus_id)
    shards, _ = yield_reader.collect_yield(corpus_id)
    return shards


def preview_corpus(corpus_id: str) -> CorpusPreview:
    """Stream the first ``.tar`` shard back through WebDataset and decode it."""
    get_corpus(corpus_id)
    return yield_reader.build_preview(corpus_id)


def get_corpus_stats() -> CorpusStats:
    """Aggregate corpus-ingest metrics for the dashboard."""
    corpora = list_corpora()
    by_status = {"running": 0, "complete": 0, "failed": 0}
    images = shards = total_bytes = successes = 0
    for corpus in corpora:
        by_status[corpus.status] = by_status.get(corpus.status, 0) + 1
        images += corpus.metrics.image_count
        successes += corpus.metrics.successes
        shards += corpus.metrics.shard_count
        total_bytes += corpus.metrics.total_bytes
    return CorpusStats(
        total_corpora=len(corpora),
        running=by_status["running"],
        complete=by_status["complete"],
        failed=by_status["failed"],
        images_ingested=successes,
        shards_written=shards,
        aggregate_yield_pct=round(successes / images * 100, 1) if images else 0.0,
        total_bytes=total_bytes,
        total_bytes_human=humanize_bytes(total_bytes),
    )
