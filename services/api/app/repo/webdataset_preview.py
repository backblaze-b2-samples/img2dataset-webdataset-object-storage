"""Stream-back preview: decode a WebDataset ``.tar`` shard read from B2.

This proves the "downstream training jobs stream shards directly from B2" claim
using the REAL ``webdataset`` package: ``wds.WebDataset(...).decode("pil")``
iterates the tar exactly the way a PyTorch/JAX ``IterableDataset`` training loop
would, yielding decoded ``(image, caption)`` samples. We pin a torch-optional
``webdataset`` so ``import webdataset`` and iteration work WITHOUT pulling torch
(verified at clean install) — a multi-GB torch dep is never added just for a
thumbnail preview.

The heavy import is deferred to call time to keep module import fast; PIL is
cheap and imported at module scope.
"""

from __future__ import annotations

import base64
import contextlib
import io
import logging
import os
import tempfile

from PIL import Image

logger = logging.getLogger(__name__)

# img2dataset writes the image under a format-named key and the caption under
# .txt; some outputs also carry a .json sidecar with the caption.
_IMAGE_KEYS = ("jpg", "jpeg", "png", "webp")
_THUMBNAIL_MAX = 160  # px, longest edge


def _thumbnail_data_url(image: Image.Image) -> tuple[str, int, int]:
    """Return (data-URL PNG thumbnail, width, height) for a decoded image."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    rgb.thumbnail((_THUMBNAIL_MAX, _THUMBNAIL_MAX))
    buffer = io.BytesIO()
    rgb.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}", width, height


def _caption_of(sample: dict) -> str:
    raw = sample.get("txt")
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").strip()
    if isinstance(raw, str):
        return raw.strip()
    meta = sample.get("json")
    if isinstance(meta, dict):
        caption = meta.get("caption")
        if isinstance(caption, str):
            return caption.strip()
    return ""


def decode_samples(tar_bytes: bytes, limit: int) -> list[dict]:
    """Decode up to ``limit`` (image, caption) pairs from one tar shard.

    Uses the real ``webdataset`` iterable pipeline. Returns a list of dicts:
    ``{key, caption, thumbnail, width, height}``. Never raises on a single bad
    sample — it skips it — so a preview degrades gracefully.
    """
    import webdataset as wds  # deferred: torch-optional, still no torch pulled

    # webdataset reads shards by path/URL, so materialize the bytes to a temp
    # .tar and let the real pipeline iterate it exactly as training would.
    fd, path = tempfile.mkstemp(suffix=".tar")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(tar_bytes)
        dataset = wds.WebDataset(path, shardshuffle=False).decode("pil")
        out: list[dict] = []
        for sample in dataset:
            image = next(
                (sample[key] for key in _IMAGE_KEYS if key in sample), None
            )
            if not isinstance(image, Image.Image):
                continue
            try:
                thumbnail, width, height = _thumbnail_data_url(image)
            except (OSError, ValueError):
                # One undecodable image must not kill the whole preview.
                logger.warning("Skipping undecodable preview sample", exc_info=True)
                continue
            out.append(
                {
                    "key": str(sample.get("__key__", "")),
                    "caption": _caption_of(sample),
                    "thumbnail": thumbnail,
                    "width": width,
                    "height": height,
                }
            )
            if len(out) >= limit:
                break
        return out
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)
