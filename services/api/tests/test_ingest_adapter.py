"""Regression tests for the img2dataset ingest adapter's process-level setup.

Both cases below made EVERY ingest fail while the app itself looked healthy, so
they are pinned here rather than left to a live run:

* fsspec reads ``FSSPEC_*`` once at import — exporting the credentials
  afterwards is a no-op and every write fails with "Unable to locate
  credentials";
* ``img2dataset.download`` installs a SIGINT handler, which raises
  ``ValueError: signal only works in main thread of the main interpreter`` on
  the background worker thread the ingest runs on.

These touch process-global state (``os.environ``, ``fsspec.config.conf``,
``signal.signal``) and restore it afterwards.
"""

import signal
import threading

import pytest

from app.config import settings
from app.repo import corpus_store, img2dataset_ingest


@pytest.fixture
def fsspec_conf():
    """The live fsspec config dict, with the ``s3`` entry restored afterwards."""
    import fsspec.config

    previous = fsspec.config.conf.get("s3")
    yield fsspec.config.conf
    if previous is None:
        fsspec.config.conf.pop("s3", None)
    else:
        fsspec.config.conf["s3"] = previous


def test_fsspec_configured_even_when_already_imported(fsspec_conf, monkeypatch):
    """Credentials must land in fsspec's LIVE config, not just the environment.

    fsspec is imported here before the adapter runs — exactly the state a
    long-lived API worker is in — so its one-shot env scan has already
    happened. Setting the variables alone would leave the config empty.
    """
    monkeypatch.setattr(settings, "b2_application_key_id", "test-key-id")
    monkeypatch.setattr(settings, "b2_application_key", "test-secret")
    monkeypatch.setattr(settings, "b2_region", "us-test-000")
    monkeypatch.setattr(settings, "b2_endpoint", "")
    fsspec_conf.pop("s3", None)  # frozen, empty scan

    img2dataset_ingest._configure_b2_fsspec_env()

    assert fsspec_conf["s3"]["key"] == "test-key-id"
    assert fsspec_conf["s3"]["secret"] == "test-secret"
    assert fsspec_conf["s3"]["client_kwargs"] == {
        "endpoint_url": "https://s3.us-test-000.backblazeb2.com",
        "region_name": "us-test-000",
    }
    # Still exported too: img2dataset's spawned workers read the environment.
    import os

    assert os.environ["FSSPEC_S3_KEY"] == "test-key-id"


def test_signal_registration_suppressed_on_worker_thread():
    """download() may register a SIGINT handler from the ingest worker thread."""
    before = signal.getsignal(signal.SIGINT)
    errors: list[BaseException] = []

    def work():
        try:
            with img2dataset_ingest._suppressed_signal_registration():
                # What img2dataset.download does; raises without the guard.
                signal.signal(signal.SIGINT, signal.SIG_IGN)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(5)

    assert errors == []
    # The app's own handler is untouched and the real function is restored.
    assert signal.getsignal(signal.SIGINT) is before
    assert signal.signal is img2dataset_ingest._REAL_SIGNAL_SIGNAL


def test_shards_are_written_below_the_manifest():
    """img2dataset's output folder must not contain the corpus manifest.

    ``incremental_mode="overwrite"`` recursively deletes that folder at the
    start of every run, so a manifest inside it would be destroyed by the very
    ingest it tracks.
    """
    corpus_id = "abc123"
    shards = corpus_store.shards_prefix(corpus_id)
    manifest = corpus_store.manifest_key(corpus_id)

    assert shards.startswith(corpus_store.corpus_prefix(corpus_id))
    assert not manifest.startswith(shards)
    assert img2dataset_ingest.s3_output_folder(corpus_id).endswith(shards.rstrip("/"))
