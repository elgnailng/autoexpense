from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import pipeline_lock, require_pipeline_idle
from api.schemas import LLMCategorizeRequest, PipelineResultResponse, ResetRequest, ResetResponse, RunAllRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level — stores latest LLM progress event for any client to read
_llm_progress: dict | None = None
_llm_progress_lock = threading.Lock()


def _sanitize_error(exc: Exception) -> str:
    """Return a user-safe error message without internal paths."""
    msg = str(exc)
    import re
    msg = re.sub(r'[A-Za-z]:\\[^\s:]+', '<path>', msg)
    msg = re.sub(r'/[^\s:]*expense_elt[^\s:]*', '<path>', msg)
    return msg


def _acquire_lock():
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Another pipeline operation is already running.",
        )


@router.post("/extract", response_model=PipelineResultResponse)
def run_extract():
    _acquire_lock()
    try:
        from staging.database import initialize_db
        from staging.load_transactions import load_all_pdfs

        initialize_db()
        stats = load_all_pdfs()
        return PipelineResultResponse(
            step="extract",
            success=True,
            stats=stats,
            message=f"Parsed {stats['total_parsed']} transactions, inserted {stats['total_inserted']} new.",
        )
    except Exception as e:
        logger.error("Pipeline step 'extract' failed", exc_info=True)
        return PipelineResultResponse(
            step="extract", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/transform", response_model=PipelineResultResponse)
def run_transform():
    _acquire_lock()
    try:
        from transform.normalize import normalize_transactions
        from transform.dedupe import find_and_log_duplicates

        norm_stats = normalize_transactions()
        dupe_stats = find_and_log_duplicates()
        combined = {**norm_stats, **dupe_stats}
        return PipelineResultResponse(
            step="transform",
            success=True,
            stats=combined,
            message=f"Normalized {norm_stats['normalized']} records. Found {dupe_stats['duplicate_records']} duplicates.",
        )
    except Exception as e:
        logger.error("Pipeline step 'transform' failed", exc_info=True)
        return PipelineResultResponse(
            step="transform", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/categorize", response_model=PipelineResultResponse)
def run_categorize(req: LLMCategorizeRequest = LLMCategorizeRequest()):
    _acquire_lock()
    try:
        from categorization.categorizer import categorize_all

        stats = categorize_all(force=req.force)
        cleared = stats.get("cleared", 0)
        message = f"Categorized {stats['categorized']} records. {stats['review_required']} need review."
        if cleared:
            message = f"Recategorized: cleared {cleared} previous categorizations. " + message
        return PipelineResultResponse(
            step="categorize",
            success=True,
            stats=stats,
            message=message,
        )
    except Exception as e:
        logger.error("Pipeline step 'categorize' failed", exc_info=True)
        return PipelineResultResponse(
            step="categorize", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/export", response_model=PipelineResultResponse)
def run_export():
    _acquire_lock()
    try:
        from output.csv_export import export_all

        stats = export_all()
        total_rows = sum(stats.values())
        return PipelineResultResponse(
            step="export",
            success=True,
            stats=stats,
            message=f"Exported {total_rows} total rows across {len(stats)} files.",
        )
    except Exception as e:
        logger.error("Pipeline step 'export' failed", exc_info=True)
        return PipelineResultResponse(
            step="export", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/llm-categorize", response_model=PipelineResultResponse)
def run_llm_categorize(req: LLMCategorizeRequest = LLMCategorizeRequest()):
    _acquire_lock()
    try:
        from categorization.categorizer import categorize_all
        from llm.config import load_llm_config

        cfg = load_llm_config()
        llm_provider = req.provider or cfg.provider
        llm_model = req.model or None
        stats = categorize_all(
            use_llm=True,
            llm_provider=llm_provider,
            dry_run=req.dry_run,
            llm_model=llm_model,
            llm_api_key=req.api_key,
            force=req.force,
        )
        if req.dry_run:
            return PipelineResultResponse(
                step="llm-categorize",
                success=True,
                stats=stats,
                message=(
                    f"Dry run: {stats.get('llm_candidates', 0)} transactions would be sent to LLM "
                    f"in {stats.get('estimated_batches', 0)} batches."
                ),
            )
        error_count = stats.get("errors", 0)
        message = (
            f"LLM categorized {stats.get('llm_evaluated', 0)} transactions. "
            f"{stats['review_required']} need review. "
            f"Cost: ${stats.get('total_cost_usd', 0):.4f}"
        )
        if error_count > 0:
            error_msgs = stats.get("error_messages", [])
            message += f" | {error_count} errors: " + "; ".join(error_msgs) if error_msgs else f" | {error_count} errors"

        return PipelineResultResponse(
            step="llm-categorize",
            success=error_count == 0,
            stats=stats,
            message=message,
        )
    except Exception as e:
        logger.error("Pipeline step 'llm-categorize' failed", exc_info=True)
        return PipelineResultResponse(
            step="llm-categorize", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/run", response_model=PipelineResultResponse)
def run_full_pipeline(req: RunAllRequest = RunAllRequest()):
    _acquire_lock()
    try:
        from staging.database import initialize_db
        from staging.load_transactions import load_all_pdfs
        from transform.normalize import normalize_transactions
        from transform.dedupe import find_and_log_duplicates
        from categorization.categorizer import categorize_all
        from output.csv_export import export_all

        initialize_db()
        extract_stats = load_all_pdfs()
        norm_stats = normalize_transactions()
        dupe_stats = find_and_log_duplicates()

        if req.use_llm:
            from llm.config import load_llm_config
            cfg = load_llm_config()
            llm_provider = req.provider or cfg.provider
            cat_stats = categorize_all(
                use_llm=True,
                llm_provider=llm_provider,
                llm_model=req.model or None,
                force=req.force,
            )
        else:
            cat_stats = categorize_all(force=req.force)

        export_stats = export_all()

        combined = {}
        for prefix, d in [("extract", extract_stats), ("transform", {**norm_stats, **dupe_stats}), ("categorize", cat_stats), ("export", export_stats)]:
            for k, v in d.items():
                combined[f"{prefix}_{k}"] = v

        message = (
            f"Pipeline complete. Parsed {extract_stats['total_parsed']}, "
            f"normalized {norm_stats['normalized']}, "
            f"categorized {cat_stats['categorized']}, "
            f"{cat_stats['review_required']} need review."
        )
        if req.use_llm:
            message += f" LLM cost: ${cat_stats.get('total_cost_usd', 0):.4f}"

        return PipelineResultResponse(
            step="run",
            success=True,
            stats=combined,
            message=message,
        )
    except Exception as e:
        logger.error("Pipeline step 'run' failed", exc_info=True)
        return PipelineResultResponse(
            step="run", success=False, stats={}, message=_sanitize_error(e)
        )
    finally:
        pipeline_lock.release()


@router.post("/llm-categorize/stream")
def stream_llm_categorize(req: LLMCategorizeRequest = LLMCategorizeRequest()):
    """SSE endpoint streaming batch-by-batch progress during LLM categorization."""
    global _llm_progress

    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Another pipeline operation is already running.",
        )

    q: queue.Queue = queue.Queue()

    def _run():
        global _llm_progress
        try:
            from categorization.categorizer import categorize_all
            from llm.config import load_llm_config

            cfg = load_llm_config()
            llm_provider = req.provider or cfg.provider
            llm_model = req.model or None
            logger.info(
                "SSE llm-categorize stream started (provider=%s, model=%s, dry_run=%s)",
                llm_provider, llm_model or "default", req.dry_run,
            )

            def _progress_callback(event):
                global _llm_progress
                with _llm_progress_lock:
                    _llm_progress = event
                q.put(event)

            stats = categorize_all(
                use_llm=True,
                llm_provider=llm_provider,
                dry_run=req.dry_run,
                progress_callback=_progress_callback,
                llm_model=llm_model,
                llm_api_key=req.api_key,
                force=req.force,
            )

            error_count = stats.get("errors", 0)
            message = (
                f"LLM categorized {stats.get('llm_evaluated', 0)} transactions. "
                f"{stats.get('review_required', 0)} need review. "
                f"Cost: ${stats.get('total_cost_usd', 0):.4f}"
            )
            if error_count > 0:
                error_msgs = stats.get("error_messages", [])
                message += f" | {error_count} errors: " + "; ".join(error_msgs) if error_msgs else f" | {error_count} errors"

            logger.info("SSE llm-categorize stream complete: %s", message)
            q.put({
                "type": "complete",
                "step": "llm-categorize",
                "success": error_count == 0,
                "stats": {k: v for k, v in stats.items() if k != "evaluations"},
                "message": message,
            })
        except Exception as exc:
            logger.error("SSE llm-categorize stream failed", exc_info=True)
            q.put({"type": "error", "message": _sanitize_error(exc)})
        finally:
            with _llm_progress_lock:
                _llm_progress = None
            q.put(None)  # sentinel

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    def _event_stream():
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    continue

                if event is None:
                    break

                yield f"data: {json.dumps(event)}\n\n"
        finally:
            pipeline_lock.release()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/llm-config")
def get_llm_config():
    """Return current LLM config, suggested models, and env var key status."""
    from llm.config import load_llm_config

    cfg = load_llm_config()
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "batch_size": cfg.batch_size,
        "max_cost_per_run": cfg.max_cost_per_run,
        "temperature": cfg.temperature,
        "suggested_models": {
            "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"],
            "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        },
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "has_openai_key": bool(os.environ.get("OPENAI_API_KEY")),
    }


@router.get("/llm-progress")
def get_llm_progress():
    """Return current LLM progress state for polling clients."""
    with _llm_progress_lock:
        if _llm_progress is None:
            return {"active": False}
        return {"active": True, **_llm_progress}


@router.post("/reset", response_model=ResetResponse)
def run_reset(req: ResetRequest, _=Depends(require_pipeline_idle)):
    """Reset pipeline data at the specified level."""
    from services.reset_service import execute_reset

    try:
        result = execute_reset(level=req.level)
        return ResetResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Reset failed", exc_info=True)
        raise HTTPException(status_code=500, detail=_sanitize_error(e))
