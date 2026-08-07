"""Pydantic models for the primary entity: a Corpus (an img2dataset ingest job).

A Corpus is persisted as a JSON manifest in B2 at
``img2dataset/<id>/manifest.json`` — there is no database. Its derived artifacts
(WebDataset ``.tar`` shards, metadata parquet, per-shard ``_stats.json``) live
alongside it under ``img2dataset/<id>/``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Finite option sets ---------------------------------------------------
# Surfaced as selectors (never free text) in the create/edit forms, and
# validated at the API boundary here.
OutputFormat = Literal["webdataset", "parquet", "files"]
OUTPUT_FORMATS: tuple[OutputFormat, ...] = ("webdataset", "parquet", "files")

ResizeMode = Literal["border", "keep_ratio", "center_crop", "no"]
RESIZE_MODES: tuple[ResizeMode, ...] = ("border", "keep_ratio", "center_crop", "no")

ImageSize = Literal[256, 384, 512]
IMAGE_SIZES: tuple[ImageSize, ...] = (256, 384, 512)

UrlListSource = Literal["seed", "uploaded"]
URL_LIST_SOURCES: tuple[UrlListSource, ...] = ("seed", "uploaded")

CorpusStatus = Literal["running", "complete", "failed"]

# Safe defaults surfaced as hints on the create form.
DEFAULT_OUTPUT_FORMAT: OutputFormat = "webdataset"
DEFAULT_RESIZE_MODE: ResizeMode = "border"
DEFAULT_IMAGE_SIZE: ImageSize = 256


class ShardStat(BaseModel):
    """Per-shard yield, read back from a ``_stats.json`` written by img2dataset."""

    name: str  # "00000"
    count: int = 0  # rows attempted in this shard
    successes: int = 0
    failed_to_download: int = 0
    failed_to_resize: int = 0
    tar_key: str | None = None  # img2dataset/<id>/00000.tar (webdataset output)
    bytes: int = 0
    size_human: str = "0 B"


class CorpusMetrics(BaseModel):
    """Aggregate yield across a corpus — drives the detail page and dashboard."""

    image_count: int = 0  # total rows attempted across shards
    successes: int = 0
    failed: int = 0
    yield_pct: float = 0.0  # successes / image_count * 100
    shard_count: int = 0
    total_bytes: int = 0
    total_bytes_human: str = "0 B"
    duration_seconds: float = 0.0


class CorpusProgress(BaseModel):
    """Live progress of one ingest, derived from what is already on B2.

    A bulk ingest is one long blocking ``img2dataset.download()`` call, so the
    only honest source of "how far along am I" is the output prefix itself:
    img2dataset writes each shard's ``_stats.json`` as that shard finishes and
    deletes the matching ``_tmp`` input shard, so completed + pending is the
    real denominator. Nothing here is timer-driven — a stalled run stops
    advancing instead of animating on.
    """

    corpus_id: str
    status: CorpusStatus
    stage: str  # plain-English phase, e.g. "Downloading and writing shards…"
    shards_completed: int = 0
    shards_total: int | None = None  # None until img2dataset has planned them
    images_written: int = 0  # successes counted so far
    images_attempted: int = 0
    percent: float | None = None  # None while the total is still unknown
    elapsed_seconds: float = 0.0


class CorpusConfig(BaseModel):
    """Tunable ingest inputs shared by create and the persisted manifest.

    Ingest params are create-time immutable (edit only touches name/description),
    so this is the create-form contract.
    """

    name: str = Field(min_length=2, max_length=50)
    description: str = Field(default="", max_length=160)
    output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT
    resize_mode: ResizeMode = DEFAULT_RESIZE_MODE
    image_size: ImageSize = DEFAULT_IMAGE_SIZE
    url_list_source: UrlListSource = "seed"
    # Only used when url_list_source == "uploaded": the bucket key of a
    # previously-uploaded TSV/CSV/parquet URL list (columns: url, caption).
    bucket_key: str | None = None


class CorpusCreate(CorpusConfig):
    """POST /corpora body."""


class CorpusUpdate(BaseModel):
    """PATCH /corpora/{id} body — only name/description are mutable.

    Ingest params are create-time immutable (they determine the shard layout on
    B2), so they are intentionally absent here and shown read-only in the UI.
    """

    name: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=160)


class Corpus(CorpusConfig):
    """Full Corpus record as persisted in B2 and returned to the frontend."""

    id: str
    status: CorpusStatus
    prefix: str  # img2dataset/<id>/
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    metrics: CorpusMetrics = Field(default_factory=CorpusMetrics)
    shards: list[ShardStat] = Field(default_factory=list)


class PreviewSample(BaseModel):
    """One decoded (image, caption) pair streamed back through WebDataset."""

    key: str
    caption: str
    thumbnail: str  # data URL: data:image/png;base64,...
    width: int
    height: int


class CorpusPreview(BaseModel):
    """Stream-back preview result for one corpus."""

    corpus_id: str
    shard_key: str | None
    samples: list[PreviewSample] = Field(default_factory=list)
    note: str | None = None  # e.g. why the preview is empty


class CorpusStats(BaseModel):
    """Aggregate corpus-ingest metrics for the dashboard."""

    total_corpora: int
    running: int
    complete: int
    failed: int
    images_ingested: int
    shards_written: int
    aggregate_yield_pct: float
    total_bytes: int
    total_bytes_human: str
