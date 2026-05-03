"""Signal ingestion endpoints — HTTP + WebSocket."""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.queue import enqueue_signal, get_signal_queue
from app.core.rate_limiter import get_rate_limiter
from app.models.schemas import SignalIngestResponse, SignalPayload

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/signals", tags=["signals"])


def _build_signal_dict(payload: SignalPayload) -> dict:
    return {
        "signal_id": str(uuid.uuid4()),
        "component_id": payload.component_id,
        "component_type": payload.component_type,
        "error_type": payload.error_type,
        "message": payload.message,
        "latency_ms": payload.latency_ms,
        "metadata": payload.metadata or {},
        "timestamp": payload.timestamp or datetime.now(timezone.utc),
        "work_item_id": None,
    }


@router.post(
    "/ingest",
    response_model=SignalIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single signal via HTTP",
)
async def ingest_signal(payload: SignalPayload):
    limiter = get_rate_limiter(settings.rate_limit_per_second)
    allowed = await limiter.consume(1)

    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=SignalIngestResponse(
                accepted=False, rate_limited=True
            ).model_dump(mode="json"),
        )

    queue = get_signal_queue(settings.queue_max_size)
    signal = _build_signal_dict(payload)
    accepted = await enqueue_signal(signal, queue)

    return SignalIngestResponse(
        accepted=accepted,
        signal_id=signal["signal_id"] if accepted else None,
        rate_limited=False,
        queue_size=queue.qsize(),
    )


@router.post(
    "/ingest/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of signals via HTTP",
)
async def ingest_batch(payloads: list[SignalPayload]):
    if len(payloads) > 1000:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Batch size must not exceed 1000"},
        )

    limiter = get_rate_limiter(settings.rate_limit_per_second)
    queue = get_signal_queue(settings.queue_max_size)

    accepted = 0
    rejected = 0

    for payload in payloads:
        allowed = await limiter.consume(1)
        if not allowed:
            rejected += 1
            continue
        signal = _build_signal_dict(payload)
        ok = await enqueue_signal(signal, queue)
        if ok:
            accepted += 1
        else:
            rejected += 1

    return {
        "accepted": accepted,
        "rejected": rejected,
        "queue_size": queue.qsize(),
    }


@router.websocket("/ws")
async def websocket_ingest(websocket: WebSocket):
    """
    WebSocket endpoint for high-throughput signal streaming.
    Clients send JSON payloads; server responds with ack per signal.
    """
    await websocket.accept()
    logger.info("WebSocket client connected from %s", websocket.client)
    limiter = get_rate_limiter(settings.rate_limit_per_second)
    queue = get_signal_queue(settings.queue_max_size)

    try:
        while True:
            data = await websocket.receive_json()
            allowed = await limiter.consume(1)

            if not allowed:
                await websocket.send_json({"status": "rate_limited"})
                continue

            try:
                payload = SignalPayload(**data)
                signal = _build_signal_dict(payload)
                accepted = await enqueue_signal(signal, queue)
                await websocket.send_json({
                    "status": "accepted" if accepted else "queue_full",
                    "signal_id": signal["signal_id"] if accepted else None,
                })
            except Exception as e:
                await websocket.send_json({"status": "error", "detail": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        await websocket.close()

