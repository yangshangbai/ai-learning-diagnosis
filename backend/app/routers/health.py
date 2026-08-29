"""健康探针（liveness / readiness）。"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    # 真实环境应探测 DB / Redis；dev 简化为 ok
    return {"status": "ok", "checks": {"database": "ok"}}
