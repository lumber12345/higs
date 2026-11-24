"""HiGHS solver API — FastAPI service deployable on Render.

Run locally:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

On Render the platform injects $PORT; the start command in render.yaml
and the Dockerfile both honour it.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    HealthResponse,
    MpsSolveRequest,
    SolveRequest,
    SolveResponse,
)
from app.solver import highs_version, solve_lp_mip, solve_mps

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("higs-api")

app = FastAPI(
    title="HiGHS Solver API",
    description="Solve linear and mixed-integer programs with HiGHS over HTTP.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "higs-solver-api",
        "description": "Solve LP/MIP models with HiGHS.",
        "highs_version": highs_version(),
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "POST /solve": "Solve an LP/MIP from JSON.",
            "POST /solve/mps": "Solve an MPS model supplied as text.",
            "GET /health": "Health check (used by Render).",
            "GET /version": "HiGHS version.",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe — Render polls this via healthCheckPath."""
    return HealthResponse(status="ok", highs_version=highs_version())


@app.get("/version", tags=["meta"])
def version() -> dict:
    return {"highs_version": highs_version()}


@app.post("/solve", response_model=SolveResponse, tags=["solve"])
def solve(req: SolveRequest) -> SolveResponse:
    """Solve an LP/MIP described as JSON."""
    try:
        result = solve_lp_mip(req)
    except Exception as exc:  # noqa: BLE001 - surface solver errors as 400
        log.exception("solve failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SolveResponse(**result)


@app.post("/solve/mps", response_model=SolveResponse, tags=["solve"])
def solve_from_mps(req: MpsSolveRequest) -> SolveResponse:
    """Solve a model supplied as MPS text."""
    try:
        result = solve_mps(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("mps solve failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SolveResponse(**result)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
