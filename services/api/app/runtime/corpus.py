import logging

# Sync `def` handlers on purpose: the whole chain is blocking boto3 + img2dataset,
# so Starlette runs these in its threadpool instead of stalling the event loop
# (see runtime/files.py for the full rationale).
from fastapi import APIRouter, HTTPException

from app.service.corpus import (
    CorpusConflictError,
    CorpusNotFoundError,
    CorpusValidationError,
    create_corpus,
    delete_corpus,
    get_corpus,
    get_corpus_stats,
    get_progress,
    get_shards,
    list_corpora,
    preview_corpus,
    reingest_corpus,
    update_corpus,
)
from app.types import (
    Corpus,
    CorpusCreate,
    CorpusPreview,
    CorpusProgress,
    CorpusStats,
    CorpusUpdate,
    ShardStat,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/corpora", response_model=list[Corpus])
def list_corpora_endpoint():
    return list_corpora()


# Declared before /corpora/{corpus_id} so "stats" is not swallowed by the id.
@router.get("/corpora/stats", response_model=CorpusStats)
def corpus_stats_endpoint():
    return get_corpus_stats()


@router.post("/corpora", response_model=Corpus, status_code=201)
def create_corpus_endpoint(payload: CorpusCreate):
    try:
        return create_corpus(payload)
    except CorpusValidationError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None


@router.get("/corpora/{corpus_id}", response_model=Corpus)
def get_corpus_endpoint(corpus_id: str):
    try:
        return get_corpus(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.patch("/corpora/{corpus_id}", response_model=Corpus)
def update_corpus_endpoint(corpus_id: str, payload: CorpusUpdate):
    try:
        return update_corpus(corpus_id, payload)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.delete("/corpora/{corpus_id}")
def delete_corpus_endpoint(corpus_id: str) -> dict[str, bool | str]:
    try:
        delete_corpus(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(
            status_code=502, detail="Failed to delete corpus from storage"
        ) from None
    return {"deleted": True, "id": corpus_id}


@router.post("/corpora/{corpus_id}/reingest", response_model=Corpus)
def reingest_corpus_endpoint(corpus_id: str):
    try:
        return reingest_corpus(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except CorpusConflictError as e:
        raise HTTPException(status_code=409, detail=e.detail) from None
    except CorpusValidationError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None


@router.get("/corpora/{corpus_id}/shards", response_model=list[ShardStat])
def corpus_shards_endpoint(corpus_id: str):
    try:
        return get_shards(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/corpora/{corpus_id}/progress", response_model=CorpusProgress)
def corpus_progress_endpoint(corpus_id: str):
    """Live ingest progress — polled by the detail page while status=running."""
    try:
        return get_progress(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/corpora/{corpus_id}/preview", response_model=CorpusPreview)
def corpus_preview_endpoint(corpus_id: str):
    try:
        return preview_corpus(corpus_id)
    except CorpusNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
