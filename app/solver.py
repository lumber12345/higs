"""Thin wrapper around HiGHS (via highspy) for solving LP/MIP models."""

from __future__ import annotations

import tempfile
from pathlib import Path

import highspy
import numpy as np

from app.models import MpsSolveRequest, SolveRequest, SolverOptions

INF = highspy.kHighsInf


def _apply_options(h: highspy.Highs, options: SolverOptions) -> None:
    """Map API solver options onto HiGHS options."""
    h.setOptionValue("output_flag", bool(options.output_flag))
    if options.time_limit is not None:
        h.setOptionValue("time_limit", float(options.time_limit))
    if options.mip_rel_gap is not None:
        h.setOptionValue("mip_rel_gap", float(options.mip_rel_gap))
    if options.mip_abs_gap is not None:
        h.setOptionValue("mip_abs_gap", float(options.mip_abs_gap))
    if options.threads is not None:
        h.setOptionValue("threads", int(options.threads))
    if options.presolve is not None:
        h.setOptionValue("presolve", options.presolve)


def _status_str(h: highspy.Highs) -> str:
    """Return a lowercase status string, e.g. 'optimal', 'infeasible'."""
    try:
        raw = str(h.getModelStatus()).split(".")[-1].lower()
        # HiGHS enum names look like 'kOptimal' -> 'optimal'
        return raw[1:] if raw.startswith("k") else raw
    except Exception:
        return "unknown"


def _extract_result(h: highspy.Highs) -> dict:
    """Pull solution + info out of a solved HiGHS instance."""
    status = _status_str(h)
    result: dict = {"status": status}

    sol = h.getSolution()
    info = h.getInfo()

    if sol.value_valid:
        result["solution"] = [float(v) for v in sol.col_value]
        result["objective_value"] = float(h.getObjectiveValue())
    if sol.row_value is not None and len(sol.row_value) > 0:
        result["constraint_values"] = [float(v) for v in sol.row_value]
    if sol.dual_valid:
        if sol.row_dual is not None and len(sol.row_dual) > 0:
            result["row_duals"] = [float(v) for v in sol.row_dual]
        if sol.col_dual is not None and len(sol.col_dual) > 0:
            result["col_duals"] = [float(v) for v in sol.col_dual]

    result["info"] = {
        "simplex_iterations": int(info.simplex_iteration_count),
        "ipm_iterations": int(info.ipm_iteration_count),
        "mip_node_count": int(info.mip_node_count),
        "mip_dual_bound": float(info.mip_dual_bound),
        "mip_gap": float(info.mip_gap),
        "primal_solution_status": int(info.primal_solution_status),
        "dual_solution_status": int(info.dual_solution_status),
    }
    return result


def solve_lp_mip(req: SolveRequest) -> dict:
    """Solve an LP/MIP described by a SolveRequest."""
    n = len(req.objective.c)
    m = len(req.constraints)

    # Bounds: default [0, +inf)
    if req.bounds is None:
        lb = np.zeros(n, dtype=np.float64)
        ub = np.full(n, INF, dtype=np.float64)
    else:
        lb = np.array(
            [b.lb if b.lb is not None else -INF for b in req.bounds],
            dtype=np.float64,
        )
        ub = np.array(
            [b.ub if b.ub is not None else INF for b in req.bounds],
            dtype=np.float64,
        )

    # Integrality
    integrality = req.integrality or ["continuous"] * n

    h = highspy.Highs()
    h.silent()
    _apply_options(h, req.options)

    h.addVars(n, lb, ub)

    # Constraints in row-wise sparse format
    if m > 0:
        row_lb = np.empty(m, dtype=np.float64)
        row_ub = np.empty(m, dtype=np.float64)
        starts: list[int] = []
        indices: list[int] = []
        values: list[float] = []
        pos = 0
        for con in req.constraints:
            starts.append(pos)
            for j, coeff in enumerate(con.a):
                if coeff != 0.0:
                    indices.append(j)
                    values.append(float(coeff))
                    pos += 1
            if con.sense == "le":
                row_lb[len(starts) - 1] = -INF
                row_ub[len(starts) - 1] = float(con.rhs)
            elif con.sense == "ge":
                row_lb[len(starts) - 1] = float(con.rhs)
                row_ub[len(starts) - 1] = INF
            else:  # eq
                row_lb[len(starts) - 1] = float(con.rhs)
                row_ub[len(starts) - 1] = float(con.rhs)
        starts.append(pos)
        h.addRows(
            m,
            row_lb,
            row_ub,
            pos,
            np.array(starts, dtype=np.int32),
            np.array(indices, dtype=np.int32),
            np.array(values, dtype=np.float64),
        )

    # Objective
    h.changeColsCost(
        n,
        np.arange(n, dtype=np.int32),
        np.array(req.objective.c, dtype=np.float64),
    )
    if req.objective.offset != 0.0:
        h.changeObjectiveOffset(float(req.objective.offset))
    if req.objective.sense == "maximize":
        h.changeObjectiveSense(highspy.ObjSense.kMaximize)

    # Integrality
    for j, kind in enumerate(integrality):
        if kind == "integer":
            h.changeColIntegrality(j, highspy.HighsVarType.kInteger)
        elif kind == "binary":
            h.changeColIntegrality(j, highspy.HighsVarType.kInteger)
            h.changeColBounds(j, 0.0, 1.0)

    if req.variable_names:
        for j, name in enumerate(req.variable_names):
            h.setColName(j, name)

    h.run()
    return _extract_result(h)


def solve_mps(req: MpsSolveRequest) -> dict:
    """Solve a model given as MPS text."""
    h = highspy.Highs()
    h.silent()
    _apply_options(h, req.options)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mps", delete=False
    ) as f:
        f.write(req.mps)
        path = f.name

    try:
        status = h.readModel(path)
        if status != highspy.HighsStatus.kOk:
            raise ValueError(f"HiGHS could not parse the MPS model (status: {status})")
        h.run()
        return _extract_result(h)
    finally:
        Path(path).unlink(missing_ok=True)


def highs_version() -> str:
    """Return the HiGHS version string."""
    h = highspy.Highs()
    h.silent()
    return h.version()
