"""B2 object store for corpus manifests, shards, stats, and metadata parquet.

The Corpus system of record is a ``manifest.json`` in B2 (not a database), so
this module is the read/write path for it plus the shard/stats enumeration the
yield-validation and preview features need. It reuses the cached, custom-UA S3
client from ``b2_client`` (boto3 stays confined to ``repo/``) and invalidates the
same shared listing cache so a just-finished ingest shows up everywhere at once.

Delete is prefix-scoped: ``delete_under`` refuses anything but a specific,
slash-terminated prefix, so a corpus delete can only ever touch
``img2dataset/<corpus-id>/`` — never a bucket-wide wipe.
"""

from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client, invalidate_listing

MANIFEST_NAME = "manifest.json"
# Batch ceiling for the S3 DeleteObjects API.
_DELETE_BATCH = 1000


def corpus_prefix(corpus_id: str) -> str:
    """The single B2 prefix that holds everything for one corpus."""
    return f"{settings.corpus_prefix}{corpus_id}/"


def manifest_key(corpus_id: str) -> str:
    return f"{corpus_prefix(corpus_id)}{MANIFEST_NAME}"


def put_bytes(key: str, data: bytes, content_type: str) -> int:
    """Write ``data`` to ``key``. Returns the byte count. Raises RuntimeError."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e
    invalidate_listing()
    return len(data)


def get_bytes(key: str) -> bytes | None:
    """Download an object's body, or None if it does not exist.

    Raises RuntimeError on any S3 failure other than a 404.
    """
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
        return response["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e


def list_under(prefix: str) -> list[dict]:
    """Every object under ``prefix`` (paginated). Raises RuntimeError."""
    client = get_s3_client()
    items: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            items.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e
    return items


def delete_under(prefix: str) -> int:
    """Delete every object under ``prefix``. Returns the count deleted.

    SAFETY: the caller MUST pass a specific, slash-terminated prefix (e.g.
    ``img2dataset/<id>/``). An empty or non-``/``-terminated prefix is refused so
    a bug can never issue a bucket-wide delete. Raises RuntimeError on failure.
    """
    if not prefix or not prefix.endswith("/"):
        raise ValueError("delete_under requires a non-empty prefix ending in '/'")
    client = get_s3_client()
    keys = [{"Key": obj["Key"]} for obj in list_under(prefix)]
    if not keys:
        return 0
    deleted = 0
    try:
        for start in range(0, len(keys), _DELETE_BATCH):
            batch = keys[start : start + _DELETE_BATCH]
            client.delete_objects(
                Bucket=settings.b2_bucket_name,
                Delete={"Objects": batch, "Quiet": True},
            )
            deleted += len(batch)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 delete failed for '{prefix}': {e}") from e
    invalidate_listing()
    return deleted


def list_manifest_keys() -> list[str]:
    """Every corpus manifest key under the sample's corpus prefix."""
    return [
        obj["Key"]
        for obj in list_under(settings.corpus_prefix)
        if obj["Key"].endswith("/" + MANIFEST_NAME)
    ]
