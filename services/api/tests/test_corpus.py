"""Corpus lifecycle tests with an in-memory stand-in for B2 object storage.

The img2dataset ingest itself is faked (a fast stub that writes plausible
per-shard ``_stats.json`` — and, for a webdataset corpus, a REAL ``.tar`` built
with Pillow) so these stay unit-fast, credential-free, and network-free. The
stream-back preview is NOT mocked: it decodes the real tar through the real
``webdataset`` package, proving vendor fidelity.
"""

import io
import json
import tarfile
import threading
import time

import pytest
from PIL import Image

from app.repo import corpus_store, img2dataset_ingest
from app.service import corpus as corpus_service
from app.service.corpus import CorpusConflictError, CorpusNotFoundError, CorpusValidationError
from app.types import CorpusCreate, CorpusUpdate


@pytest.fixture
def mem_store(monkeypatch):
    store: dict[str, bytes] = {}

    def put_bytes(key, data, content_type):
        store[key] = data
        return len(data)

    def get_bytes(key):
        return store.get(key)

    def list_under(prefix):
        return [
            {"Key": k, "Size": len(v)} for k, v in store.items() if k.startswith(prefix)
        ]

    def delete_under(prefix):
        assert prefix.endswith("/"), "delete must be prefix-scoped"
        keys = [k for k in store if k.startswith(prefix)]
        for k in keys:
            del store[k]
        return len(keys)

    monkeypatch.setattr(corpus_store, "put_bytes", put_bytes)
    monkeypatch.setattr(corpus_store, "get_bytes", get_bytes)
    monkeypatch.setattr(corpus_store, "list_under", list_under)
    monkeypatch.setattr(corpus_store, "delete_under", delete_under)
    return store


def _real_webdataset_tar(n: int) -> bytes:
    """A tar shaped exactly like img2dataset webdataset output: key.jpg/.txt/.json."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for i in range(n):
            key = f"{i:09d}"
            image = Image.new("RGB", (48, 48), (i * 30 % 255, 120, 200))
            jpg = io.BytesIO()
            image.save(jpg, format="JPEG")
            payloads = {
                ".jpg": jpg.getvalue(),
                ".txt": f"caption {i}".encode(),
                ".json": json.dumps({"caption": f"caption {i}", "status": "success"}).encode(),
            }
            for ext, data in payloads.items():
                info = tarfile.TarInfo(name=key + ext)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _fake_ingest(store, *, shards=2, per_shard=4, successes_per_shard=3, real_tar=True):
    """Build a run_ingest stub that writes fake shards into the mem store.

    Mirrors the real adapter closely enough to catch layout bugs: shards go in
    img2dataset's own ``shards/`` sub-folder, and the stub first WIPES that
    folder exactly like ``incremental_mode="overwrite"`` does. The corpus
    manifest must survive that wipe.
    """

    def run_ingest(corpus_id, *, url_list_path, output_format, resize_mode, image_size):
        prefix = corpus_store.shards_prefix(corpus_id)
        for key in [k for k in store if k.startswith(prefix)]:
            del store[key]
        for s in range(shards):
            name = f"{s:05d}"
            stats = {
                "count": per_shard,
                "successes": successes_per_shard,
                "failed_to_download": per_shard - successes_per_shard,
                "failed_to_resize": 0,
            }
            store[f"{prefix}{name}_stats.json"] = json.dumps(stats).encode()
            if output_format == "webdataset":
                store[f"{prefix}{name}.tar"] = (
                    _real_webdataset_tar(successes_per_shard) if real_tar else b"TAR"
                )
            elif output_format == "parquet":
                store[f"{prefix}{name}.parquet"] = b"PARQUET-BYTES"
        return img2dataset_ingest.s3_output_folder(corpus_id)

    return run_ingest


def _wait_for_status(corpus_id, status, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        corpus = corpus_service.get_corpus(corpus_id)
        if corpus.status == status:
            return corpus
        time.sleep(0.02)
    return corpus_service.get_corpus(corpus_id)


# --- create / read --------------------------------------------------------

def test_create_runs_ingest_and_reports_yield(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Seed corpus", output_format="webdataset")
    )
    assert corpus.status == "running"
    assert corpus.prefix.endswith(f"{corpus.id}/")

    done = _wait_for_status(corpus.id, "complete")
    assert done.status == "complete"
    # 2 shards * 4 attempted = 8 images, 6 successes -> 75% yield.
    assert done.metrics.image_count == 8
    assert done.metrics.successes == 6
    assert done.metrics.yield_pct == 75.0
    assert done.metrics.shard_count == 2
    assert done.metrics.total_bytes > 0
    assert {s.name for s in done.shards} == {"00000", "00001"}


def test_list_and_get(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    corpus = corpus_service.create_corpus(CorpusCreate(name="Listed"))
    _wait_for_status(corpus.id, "complete")
    assert any(c.id == corpus.id for c in corpus_service.list_corpora())
    assert corpus_service.get_corpus(corpus.id).name == "Listed"


def test_missing_corpus_raises(mem_store):
    with pytest.raises(CorpusNotFoundError):
        corpus_service.get_corpus("does-not-exist")


def test_corpus_stays_readable_while_the_ingest_overwrites(mem_store, monkeypatch):
    """The manifest must survive img2dataset wiping its output folder mid-run.

    "Create & ingest" navigates straight to the detail page, which polls while
    the ingest is still running. When the manifest lived inside the folder
    img2dataset overwrites, that poll 404'd for the whole run and the finished
    corpus was then treated as deleted and silently dropped.
    """
    started = threading.Event()
    release = threading.Event()

    def overwriting_ingest(corpus_id, **kwargs):
        # Exactly what incremental_mode="overwrite" does first.
        corpus_store.delete_under(corpus_store.shards_prefix(corpus_id))
        started.set()
        release.wait(5)
        return _fake_ingest(mem_store)(corpus_id, **kwargs)

    monkeypatch.setattr(img2dataset_ingest, "run_ingest", overwriting_ingest)
    corpus = corpus_service.create_corpus(CorpusCreate(name="Mid-run"))

    assert started.wait(5)
    assert corpus_service.get_corpus(corpus.id).status == "running"

    release.set()
    done = _wait_for_status(corpus.id, "complete")
    assert done.status == "complete"
    assert done.metrics.shard_count == 2


# --- edit -----------------------------------------------------------------

def test_update_only_name_and_description(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Draft", image_size=384, resize_mode="center_crop")
    )
    _wait_for_status(corpus.id, "complete")
    updated = corpus_service.update_corpus(
        corpus.id, CorpusUpdate(name="Final", description="edited")
    )
    assert updated.name == "Final"
    assert updated.description == "edited"
    # Ingest params are create-time immutable and preserved verbatim.
    assert updated.image_size == 384
    assert updated.resize_mode == "center_crop"


# --- delete ---------------------------------------------------------------

def test_delete_is_prefix_scoped(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    keep = corpus_service.create_corpus(CorpusCreate(name="Keep"))
    drop = corpus_service.create_corpus(CorpusCreate(name="Drop"))
    _wait_for_status(keep.id, "complete")
    _wait_for_status(drop.id, "complete")

    corpus_service.delete_corpus(drop.id)
    with pytest.raises(CorpusNotFoundError):
        corpus_service.get_corpus(drop.id)
    # The other corpus and its objects are untouched.
    assert corpus_service.get_corpus(keep.id).name == "Keep"
    assert any(k.startswith(keep.prefix) for k in mem_store)
    assert not any(k.startswith(drop.prefix) for k in mem_store)


# --- run (re-ingest) ------------------------------------------------------

def test_reingest_reruns_and_guards_concurrency(mem_store, monkeypatch):
    def slow_ingest(corpus_id, **kwargs):
        time.sleep(0.3)
        return _fake_ingest(mem_store)(corpus_id, **kwargs)

    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    corpus = corpus_service.create_corpus(CorpusCreate(name="Rerun"))
    _wait_for_status(corpus.id, "complete")

    monkeypatch.setattr(img2dataset_ingest, "run_ingest", slow_ingest)
    started = corpus_service.reingest_corpus(corpus.id)
    assert started.status == "running"
    with pytest.raises(CorpusConflictError):
        corpus_service.reingest_corpus(corpus.id)
    assert _wait_for_status(corpus.id, "complete").status == "complete"


# --- validation -----------------------------------------------------------

def test_uploaded_source_requires_bucket_key(mem_store):
    with pytest.raises(CorpusValidationError):
        corpus_service.create_corpus(
            CorpusCreate(name="No file", url_list_source="uploaded")
        )


def test_uploaded_source_with_key_ingests(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    mem_store["uploads/list.tsv"] = b"url\tcaption\nhttp://x/1.jpg\thi\n"
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Uploaded", url_list_source="uploaded", bucket_key="uploads/list.tsv")
    )
    assert _wait_for_status(corpus.id, "complete").status == "complete"


# --- live ingest progress -------------------------------------------------

def test_progress_advances_while_the_ingest_runs(mem_store, monkeypatch):
    """Progress must move mid-run, and only because objects landed on B2.

    The stub writes img2dataset's real layout: three ``_tmp`` input shards up
    front, then one ``_stats.json`` per finished shard, deleting that shard's
    ``_tmp`` file — exactly what the progress reader counts.
    """
    release_shard = threading.Semaphore(0)

    def staged_ingest(corpus_id, **kwargs):
        prefix = corpus_store.shards_prefix(corpus_id)
        for shard in range(3):  # planned up front, into _tmp
            mem_store[f"{prefix}_tmp/{shard:05d}.feather"] = b"FEATHER"
        for shard in range(3):
            assert release_shard.acquire(timeout=5)
            name = f"{shard:05d}"
            stats = {"count": 4, "successes": 3, "failed_to_download": 1}
            mem_store[f"{prefix}{name}_stats.json"] = json.dumps(stats).encode()
            mem_store[f"{prefix}{name}.tar"] = b"TAR"
            del mem_store[f"{prefix}_tmp/{name}.feather"]
        return img2dataset_ingest.s3_output_folder(corpus_id)

    monkeypatch.setattr(img2dataset_ingest, "run_ingest", staged_ingest)
    corpus = corpus_service.create_corpus(CorpusCreate(name="Progressing"))

    def progress_when(predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = corpus_service.get_progress(corpus.id)
            if predicate(current):
                return current
            time.sleep(0.02)
        return corpus_service.get_progress(corpus.id)

    first = progress_when(lambda p: p.shards_total == 3)
    assert first.status == "running"
    assert first.shards_total == 3  # read from the pending _tmp shards
    assert first.shards_completed == 0
    assert first.percent == 0.0
    assert first.images_written == 0

    release_shard.release()
    second = progress_when(lambda p: p.shards_completed == 1)
    # The whole point of the finding: the numbers visibly move mid-run.
    assert second.shards_completed == 1
    assert second.images_written == 3
    assert second.images_attempted == 4
    assert second.percent and second.percent > (first.percent or 0)
    assert second.shards_total == 3
    assert second.elapsed_seconds >= 0

    release_shard.release()
    release_shard.release()
    done = _wait_for_status(corpus.id, "complete")
    assert done.status == "complete"

    final = corpus_service.get_progress(corpus.id)
    assert final.percent == 100.0
    assert final.shards_completed == 3


def test_progress_is_indeterminate_before_shards_are_planned(mem_store, monkeypatch):
    """No shards planned yet -> no invented percentage."""
    release = threading.Event()

    def blocked_ingest(corpus_id, **kwargs):
        release.wait(5)
        return img2dataset_ingest.s3_output_folder(corpus_id)

    monkeypatch.setattr(img2dataset_ingest, "run_ingest", blocked_ingest)
    corpus = corpus_service.create_corpus(CorpusCreate(name="Planning"))
    progress = corpus_service.get_progress(corpus.id)
    assert progress.status == "running"
    assert progress.percent is None
    assert progress.shards_total is None
    assert progress.stage
    release.set()
    _wait_for_status(corpus.id, "complete")


def test_progress_of_a_missing_corpus_raises(mem_store):
    with pytest.raises(CorpusNotFoundError):
        corpus_service.get_progress("does-not-exist")


# --- stream-back preview (real webdataset, not mocked) --------------------

def test_preview_decodes_real_webdataset_shard(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Preview", output_format="webdataset")
    )
    _wait_for_status(corpus.id, "complete")

    preview = corpus_service.preview_corpus(corpus.id)
    assert preview.shard_key and preview.shard_key.endswith(".tar")
    assert len(preview.samples) >= 1
    first = preview.samples[0]
    assert first.caption.startswith("caption")
    assert first.thumbnail.startswith("data:image/png;base64,")
    assert first.width == 48 and first.height == 48


def test_preview_note_when_no_tar(mem_store, monkeypatch):
    # A parquet-format corpus writes no .tar, so there is nothing to stream back.
    monkeypatch.setattr(
        img2dataset_ingest, "run_ingest", _fake_ingest(mem_store, real_tar=False)
    )
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Parquet", output_format="parquet")
    )
    _wait_for_status(corpus.id, "complete")
    preview = corpus_service.preview_corpus(corpus.id)
    assert preview.samples == []
    assert preview.note


def test_preview_of_a_zero_yield_shard_is_empty_not_an_error(mem_store, monkeypatch):
    # A corpus can legitimately COMPLETE with zero successful downloads (a URL
    # list whose URLs are all unfetchable); img2dataset still writes a valid
    # but member-less .tar. That has to read back as an empty preview so the UI
    # renders its "Nothing to stream back yet" empty state — not a raw 500.
    monkeypatch.setattr(
        img2dataset_ingest,
        "run_ingest",
        _fake_ingest(mem_store, shards=1, successes_per_shard=0),
    )
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Zero yield", output_format="webdataset")
    )
    _wait_for_status(corpus.id, "complete")

    preview = corpus_service.preview_corpus(corpus.id)
    assert preview.shard_key and preview.shard_key.endswith(".tar")
    assert preview.samples == []


def test_preview_of_an_unreadable_shard_still_raises(mem_store, monkeypatch):
    # The empty-shard tolerance must not swallow genuine failures: a shard that
    # is not a readable tar is a real error, not an empty dataset.
    monkeypatch.setattr(
        img2dataset_ingest,
        "run_ingest",
        _fake_ingest(mem_store, shards=1, real_tar=False),
    )
    corpus = corpus_service.create_corpus(
        CorpusCreate(name="Corrupt shard", output_format="webdataset")
    )
    _wait_for_status(corpus.id, "complete")

    with pytest.raises(tarfile.ReadError):
        corpus_service.preview_corpus(corpus.id)


# --- dashboard stats ------------------------------------------------------

def test_corpus_stats_aggregate(mem_store, monkeypatch):
    monkeypatch.setattr(img2dataset_ingest, "run_ingest", _fake_ingest(mem_store))
    a = corpus_service.create_corpus(CorpusCreate(name="Corpus A"))
    b = corpus_service.create_corpus(CorpusCreate(name="Corpus B"))
    _wait_for_status(a.id, "complete")
    _wait_for_status(b.id, "complete")

    stats = corpus_service.get_corpus_stats()
    assert stats.total_corpora == 2
    assert stats.complete == 2
    assert stats.images_ingested == 12  # 2 corpora * 6 successes
    assert stats.shards_written == 4
    assert stats.aggregate_yield_pct == 75.0
    assert stats.total_bytes > 0
