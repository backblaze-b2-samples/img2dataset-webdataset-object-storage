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

from app.config import settings
from app.repo import corpus_store, webdataset_preview
from app.types.corpus import (
    CorpusMetrics,
    CorpusPreview,
    PreviewSample,
    ShardStat,
)
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)


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
        name = os.path.basename(key)[: -len("_stats.json")]
        tar_key = f"{prefix}{name}.tar"
        parquet_key = f"{prefix}{name}.parquet"
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
