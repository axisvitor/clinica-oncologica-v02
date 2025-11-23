"""
Metrics API Endpoint
Exposes Prometheus metrics at /metrics
"""

from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    """
    Expose Prometheus metrics

    This endpoint is scraped by Prometheus to collect application metrics.
    Returns metrics in Prometheus text format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
