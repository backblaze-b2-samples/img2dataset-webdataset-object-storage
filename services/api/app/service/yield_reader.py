"""Read corpus yield back from B2 — the honest validation of an ingest.

Kept separate from ``service/corpus.py`` (lifecycle) so each stays under the
300-line boundary. This module never mutates state: it lists a corpus prefix,
reads every per-shard ``_stats.json`` and (for the stream-back preview) the first
``.tar`` shard, and reports what actually landed in B2. If a run yielded zero it
says so, rather than showing a false green.
"""

import json
import logging
import os
from datetime import UTC, datetime

from app.config import settings
from app.repo import corpus_store, webdataset_preview
from app.types.corpus import (
    Corpus,
    CorpusMetrics,
    CorpusPreview,
    CorpusProgress,
    PreviewSample,
    ShardStat,
)
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

# Plain-English phases for the live progress panel.
STAGE_PREPARING = "Preparing the URL list and planning shards"
STAGE_DOWNLOADING = "Downloading images and writing shards to B2"
STAGE_FINALIZING = "Reading the yield back from B2"
STAGE_COMPLETE = "Ingest complete"
STAGE_FAILED = "Ingest failed"


def collect_yield(corpus_id: str) -> tuple[list[ShardStat], CorpusMetrics]:
    """Read every per-shard ``_stats.json`` back from B2 and aggregate yield."""
    prefix = corpus_store.corpus_prefix(corpus_id)
    objects = corpus_store.list_under(prefix)
    sizes = {o["Key"]: o["Size"] for o in objects}
    manifest = corpus_store.manifest_key(corpus_id)

    shards: list[ShardStat] = []
    for key in sorted(k for k in sizes if k.endswith("_stats.json")):
        raw = corpus_store.get_bytes(key)
        if raw is None:
            continue
        try:
            stat = json.loads(raw)
        except ValueError:
            continue
        # Derive the shard's artifacts from the stats key itself (same folder,
        # same basename) rather than assuming a layout, so this keeps working
        # wherever img2dataset's output folder sits under the corpus prefix.
        base = key[: -len("_stats.json")]
        name = os.path.basename(base)
        tar_key = f"{base}.tar"
        parquet_key = f"{base}.parquet"
        artifact_key = (
            tar_key
            if tar_key in sizes
            else (parquet_key if parquet_key in sizes else None)
        )
        shard_bytes = sizes.get(artifact_key, 0) if artifact_key else 0
        shards.append(
            ShardStat(
                name=name,
                count=int(stat.get("count", 0)),
                successes=int(stat.get("successes", 0)),
                failed_to_download=int(stat.get("failed_to_download", 0)),
                failed_to_resize=int(stat.get("failed_to_resize", 0)),
                tar_key=tar_key if tar_key in sizes else None,
                bytes=shard_bytes,
                size_human=humanize_bytes(shard_bytes),
            )
        )

    image_count = sum(s.count for s in shards)
    successes = sum(s.successes for s in shards)
    total_bytes = sum(v for k, v in sizes.items() if k != manifest)
    metrics = CorpusMetrics(
        image_count=image_count,
        successes=successes,
        failed=max(image_count - successes, 0),
        yield_pct=round(successes / image_count * 100, 1) if image_count else 0.0,
        shard_count=len(shards),
        total_bytes=total_bytes,
        total_bytes_human=humanize_bytes(total_bytes),
    )
    return shards, metrics


def pending_shard_count(corpus_id: str) -> int:
    """Shards img2dataset has planned but not finished yet.

    It writes one ``.feather`` input shard per output shard into its ``_tmp``
    folder up front, then deletes each one as that shard's images land — so what
    is still there is exactly the work outstanding, read straight from B2.
    """
    tmp_prefix = f"{corpus_store.shards_prefix(corpus_id)}_tmp/"
    return sum(
        1 for obj in corpus_store.list_under(tmp_prefix) if obj["Key"].endswith(".feather")
    )


def collect_progress(corpus: Corpus) -> CorpusProgress:
    """How far along this corpus's ingest is, measured from objects on B2.

    ``img2dataset.download()`` is a single blocking call, so progress is derived
    by re-reading the output prefix while it runs: completed shards (their
    ``_stats.json`` exists) against the shards still pending in ``_tmp``. No
    timers, no interpolation — if the run stalls, the numbers stop moving.
    """
    if corpus.status != "running":
        done = corpus.status == "complete"
        metrics = corpus.metrics
        return CorpusProgress(
            corpus_id=corpus.id,
            status=corpus.status,
            stage=STAGE_COMPLETE if done else STAGE_FAILED,
            shards_completed=metrics.shard_count,
            shards_total=metrics.shard_count or None,
            images_written=metrics.successes,
            images_attempted=metrics.image_count,
            percent=100.0 if done else None,
            elapsed_seconds=metrics.duration_seconds,
        )

    _, metrics = collect_yield(corpus.id)
    pending = pending_shard_count(corpus.id)
    total = metrics.shard_count + pending
    if total == 0:
        stage = STAGE_PREPARING
    elif pending:
        stage = STAGE_DOWNLOADING
    else:
        stage = STAGE_FINALIZING
    # The manifest's updated_at is stamped when the run starts (create and
    # re-ingest both write it), so it is the run's real start time.
    started_at = corpus.updated_at
    if started_at.tzinfo is None:  # defensive: a manifest written without a tz
        started_at = started_at.replace(tzinfo=UTC)
    return CorpusProgress(
        corpus_id=corpus.id,
        status=corpus.status,
        stage=stage,
        shards_completed=metrics.shard_count,
        shards_total=total or None,
        images_written=metrics.successes,
        images_attempted=metrics.image_count,
        percent=round(metrics.shard_count / total * 100, 1) if total else None,
        elapsed_seconds=round((datetime.now(UTC) - started_at).total_seconds(), 1),
    )


def build_preview(corpus_id: str) -> CorpusPreview:
    """Stream the first ``.tar`` shard back through WebDataset and decode it."""
    prefix = corpus_store.corpus_prefix(corpus_id)
    tars = sorted(
        o["Key"]
        for o in corpus_store.list_under(prefix)
        if o["Key"].endswith(".tar")
    )
    if not tars:
        return CorpusPreview(
            corpus_id=corpus_id,
            shard_key=None,
            samples=[],
            note=(
                "No WebDataset .tar shards to stream back yet. Preview needs a "
                "completed webdataset-format corpus with a non-zero yield."
            ),
        )
    shard_key = tars[0]
    data = corpus_store.get_bytes(shard_key)
    if data is None:
        return CorpusPreview(
            corpus_id=corpus_id,
            shard_key=shard_key,
            samples=[],
            note="Shard vanished from B2.",
        )
    decoded = webdataset_preview.decode_samples(data, settings.corpus_preview_samples)
    return CorpusPreview(
        corpus_id=corpus_id,
        shard_key=shard_key,
        samples=[PreviewSample(**sample) for sample in decoded],
    )
