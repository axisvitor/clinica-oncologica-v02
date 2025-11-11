"""
Endpoint de teste para debug
"""

import pytest
from fastapi import APIRouter, Depends, Request
from app.middleware.csrf import validate_csrf_token
from pydantic import BaseModel

# Prevent pytest from collecting this helper module as a test suite.
pytestmark = pytest.mark.skip("Helper router file, not intended for pytest collection.")

router = APIRouter(prefix="/test", tags=["Test"])


class TestRequest(BaseModel):
    message: str


@router.post("/csrf", dependencies=[Depends(validate_csrf_token)])
async def test_csrf(
    request: Request,
    data: TestRequest
):
    """
    Endpoint de teste simples para verificar se CSRF está funcionando
    sem usar ServiceProvider.
    """
    return {
        "status": "success",
        "message": f"CSRF OK! Received: {data.message}",
        "client_ip": request.client.host if request.client else "unknown"
    }

@router.post("/simple")
async def test_simple(
    data: TestRequest
):
    """
    Endpoint de teste ultra simples sem CSRF nem dependências.
    """
    return {
        "status": "success",
        "message": f"Simple test OK! Received: {data.message}",
        "timestamp": "2025-10-10T19:25:00Z"
    }
