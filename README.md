# HiGHS Solver API

A small [FastAPI](https://fastapi.tiangolo.com/) service that solves linear
and mixed-integer programs with [HiGHS](https://highs.dev/) (via
[`highspy`](https://pypi.org/project/highspy/)) over HTTP — ready to deploy
on [Render](https://render.com/).

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000/docs for interactive API docs.

## Deploy on Render

### Option A — Blueprint (recommended)

1. Push this repo to GitHub.
2. In the [Render dashboard](https://dashboard.render.com/), choose
   **New → Blueprint** and connect the repo. Render reads [`render.yaml`](./render.yaml)
   and creates the web service automatically.
3. Wait for the first deploy, then visit your service URL
   (e.g. `https://higs-solver-api.onrender.com`).

### Option B — Manual web service

Create a **Web Service** with:

| Setting | Value |
|---|---|
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Python version | `3.12.7` (env var `PYTHON_VERSION`) |

> Render injects the `PORT` environment variable — the start command above
> binds to it. The free tier sleeps after inactivity; the first request
> after a sleep takes ~30–60s while the service wakes up.

### Option C — Docker

The [`Dockerfile`](./Dockerfile) builds the same service as a container.
To use it on Render, set the service runtime to **Docker** (or uncomment
the `runtime: docker` lines in `render.yaml`).

```bash
docker build -t higs-solver-api .
docker run -p 8000:8000 -e PORT=8000 higs-solver-api
```

## API

### `GET /health`

Liveness probe (used by Render). Returns the HiGHS version.

```bash
curl https://<your-service>.onrender.com/health
# {"status":"ok","highs_version":"1.16.0","service":"higs-solver-api"}
```

### `POST /solve`

Solve an LP/MIP described as JSON.

```bash
curl -X POST https://<your-service>.onrender.com/solve \
  -H "Content-Type: application/json" \
  -d '{
    "objective": {"c": [1, 1], "sense": "minimize"},
    "constraints": [
      {"a": [1, 2], "sense": "ge", "rhs": 4},
      {"a": [4, 2], "sense": "ge", "rhs": 12}
    ]
  }'
```

Response:

```json
{
  "status": "optimal",
  "objective_value": 3.3333333333333335,
  "solution": [2.6666666666666665, 0.6666666666666666],
  "constraint_values": [4.0, 12.0],
  "row_duals": [0.3333333333333333, 0.16666666666666669],
  "col_duals": [0.0, 0.0],
  "info": {
    "simplex_iterations": 2,
    "ipm_iterations": 0,
    "mip_node_count": -1,
    "mip_dual_bound": 0.0,
    "mip_gap": null,
    "primal_solution_status": 2,
    "dual_solution_status": 2
  }
}
```

Request fields:

| Field | Description |
|---|---|
| `objective.c` | Objective coefficients (one per variable). |
| `objective.sense` | `"minimize"` (default) or `"maximize"`. |
| `objective.offset` | Constant added to the objective (default `0`). |
| `constraints[]` | Each: `a` (coefficients), `sense` (`le`/`ge`/`eq`), `rhs`. |
| `bounds[]` | Per-variable `{lb, ub}`; `null` = unbounded. Default `[0, +inf)`. |
| `integrality[]` | Per-variable: `continuous` / `integer` / `binary`. Default all continuous. |
| `variable_names[]` | Optional names for variables. |
| `options` | `time_limit`, `mip_rel_gap`, `mip_abs_gap`, `threads`, `presolve`, `output_flag`. |

### `POST /solve/mps`

Solve a model supplied as MPS text:

```bash
curl -X POST https://<your-service>.onrender.com/solve/mps \
  -H "Content-Type: application/json" \
  -d '{"mps": "NAME ...\n..."}'
```

### `GET /version`

Returns the HiGHS version string.

## Tests

```bash
pip install pytest httpx
pytest -q
```

## Project layout

```
app/
  main.py    FastAPI app (routes, CORS, PORT handling)
  models.py  Pydantic request/response schemas
  solver.py  HiGHS wrapper (LP/MIP + MPS)
render.yaml  Render Blueprint (IaC deploy)
Dockerfile   Container image (alternative deploy path)
requirements.txt
tests/       Smoke tests
```
