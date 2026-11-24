"""Pydantic request/response models for the HiGHS solver API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Objective(BaseModel):
    """Linear objective: minimize/maximize c^T x."""

    c: list[float] = Field(..., description="Objective coefficients, one per variable.")
    sense: Literal["minimize", "maximize"] = Field(
        default="minimize", description="Optimization sense."
    )
    offset: float = Field(default=0.0, description="Constant added to the objective.")


class Constraint(BaseModel):
    """Single linear constraint: a^T x <sense> rhs."""

    a: list[float] = Field(..., description="Constraint coefficients, one per variable.")
    sense: Literal["le", "ge", "eq"] = Field(
        ..., description="Constraint sense: <=, >=, or ==."
    )
    rhs: float = Field(..., description="Right-hand side value.")


class VariableBound(BaseModel):
    """Bounds for one variable. Use null for unbounded."""

    lb: Optional[float] = Field(default=0.0, description="Lower bound (null = -inf).")
    ub: Optional[float] = Field(default=None, description="Upper bound (null = +inf).")


class SolverOptions(BaseModel):
    """Optional HiGHS solver settings."""

    time_limit: Optional[float] = Field(
        default=None, gt=0, description="Time limit in seconds."
    )
    mip_rel_gap: Optional[float] = Field(
        default=None, ge=0, description="Relative MIP gap tolerance."
    )
    mip_abs_gap: Optional[float] = Field(
        default=None, ge=0, description="Absolute MIP gap tolerance."
    )
    threads: Optional[int] = Field(
        default=None, gt=0, description="Number of threads (0 = auto)."
    )
    presolve: Optional[Literal["on", "off", "choose"]] = Field(
        default=None, description="Presolve setting."
    )
    output_flag: bool = Field(
        default=False, description="Enable HiGHS solver log output."
    )


class SolveRequest(BaseModel):
    """JSON description of an LP/MIP to solve."""

    objective: Objective
    constraints: list[Constraint] = Field(default_factory=list)
    bounds: Optional[list[VariableBound]] = Field(
        default=None,
        description="Per-variable bounds. Defaults to [0, +inf) for all variables.",
    )
    integrality: Optional[list[Literal["continuous", "integer", "binary"]]] = Field(
        default=None,
        description="Per-variable integrality. Defaults to all continuous.",
    )
    variable_names: Optional[list[str]] = Field(
        default=None, description="Optional names for variables."
    )
    options: SolverOptions = Field(default_factory=SolverOptions)

    @model_validator(mode="after")
    def _check_dimensions(self) -> "SolveRequest":
        n = len(self.objective.c)
        if n == 0:
            raise ValueError("objective.c must contain at least one coefficient")
        for i, con in enumerate(self.constraints):
            if len(con.a) != n:
                raise ValueError(
                    f"constraints[{i}].a has length {len(con.a)}, expected {n}"
                )
        if self.bounds is not None and len(self.bounds) != n:
            raise ValueError(
                f"bounds has length {len(self.bounds)}, expected {n}"
            )
        if self.integrality is not None and len(self.integrality) != n:
            raise ValueError(
                f"integrality has length {len(self.integrality)}, expected {n}"
            )
        if self.variable_names is not None and len(self.variable_names) != n:
            raise ValueError(
                f"variable_names has length {len(self.variable_names)}, expected {n}"
            )
        return self


class SolveResponse(BaseModel):
    """Result of a solve."""

    status: str = Field(..., description="HiGHS model status, e.g. 'optimal'.")
    objective_value: Optional[float] = Field(
        default=None, description="Objective value at the solution."
    )
    solution: Optional[list[float]] = Field(
        default=None, description="Primal variable values."
    )
    constraint_values: Optional[list[float]] = Field(
        default=None, description="Constraint activity values (a^T x)."
    )
    row_duals: Optional[list[float]] = Field(
        default=None, description="Dual values for constraints (LP only)."
    )
    col_duals: Optional[list[float]] = Field(
        default=None, description="Dual values for variables (LP only)."
    )
    info: dict = Field(default_factory=dict, description="Solver info (iterations, nodes, etc.).")


class MpsSolveRequest(BaseModel):
    """Solve from an MPS file supplied as a string."""

    mps: str = Field(..., description="Full contents of an MPS file.")
    options: SolverOptions = Field(default_factory=SolverOptions)


class HealthResponse(BaseModel):
    status: str = "ok"
    highs_version: str
    service: str = "higs-solver-api"
