from __future__ import annotations

import io
import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from scipy import stats

app = FastAPI(title="CP_CORRELACION", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "https://irinabw98.github.io",
        "https://irinabw98.github.io/CP_CORRELACION",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=1)
    se_col: str = "se_name_mod"
    value_col: str = "assessment_value"
    variable_x: str
    variable_y: str
    group_cols: list[str] = Field(default_factory=list)
    unit_cols: list[str] = Field(default_factory=list)
    descriptive_cols: list[str] = Field(default_factory=list)
    method: Literal["pearson", "spearman"] = "pearson"
    aggregation: Literal["mean", "median", "first", "max", "min"] = "mean"
    conflict_mode: Literal["join", "varios", "first"] = "join"
    min_n: int = 3
    analysis_name: str = "correlacion"


def _clean_colname(x: Any) -> str:
    return str(x).strip()


def _normalize_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.columns = [_clean_colname(c) for c in df.columns]
    df = df.replace({"": np.nan, " ": np.nan})
    return df


def _to_numeric_series_strong(series: pd.Series) -> pd.Series:
    def convert_one(v: Any) -> float:
        if pd.isna(v):
            return np.nan
        if isinstance(v, (int, float, np.integer, np.floating)):
            return float(v)
        s = str(v).strip()
        if not s:
            return np.nan
        s = s.replace("%", "").replace(" ", "")
        # Soporta formatos 1.234,56 y 1,234.56
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return np.nan

    return series.apply(convert_one)


def _agg_func(name: str):
    if name == "mean":
        return "mean"
    if name == "median":
        return "median"
    if name == "max":
        return "max"
    if name == "min":
        return "min"
    return "first"


def _safe_key_cols(cols: list[str], df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for col in cols:
        c = _clean_colname(col)
        if c in df.columns and c not in out:
            out.append(c)
    return out


def _unique_join(values: pd.Series, mode: str) -> Any:
    vals = [str(v) for v in values.dropna().astype(str).unique() if str(v).strip()]
    if not vals:
        return np.nan
    if len(vals) == 1:
        return vals[0]
    if mode == "varios":
        return "VARIOS"
    if mode == "first":
        return vals[0]
    return " | ".join(sorted(vals))


def _corr(x: pd.Series, y: pd.Series, method: str) -> tuple[float, float, str | None]:
    clean = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(clean) < 2:
        return np.nan, np.nan, "No hay pares suficientes."
    if clean["x"].nunique() < 2 or clean["y"].nunique() < 2:
        return np.nan, np.nan, "Una de las variables no tiene variabilidad dentro del grupo."
    try:
        if method == "spearman":
            r, p = stats.spearmanr(clean["x"], clean["y"])
        else:
            r, p = stats.pearsonr(clean["x"], clean["y"])
        return float(r), float(p), None
    except Exception as exc:  # noqa: BLE001
        return np.nan, np.nan, str(exc)


def _strength(r: float) -> str:
    if pd.isna(r):
        return "no calculable"
    ar = abs(r)
    if ar < 0.30:
        return "débil"
    if ar < 0.60:
        return "moderada"
    if ar < 0.80:
        return "fuerte"
    return "muy fuerte"


def _direction(r: float) -> str:
    if pd.isna(r):
        return "no calculable"
    if r > 0:
        return "positiva"
    if r < 0:
        return "negativa"
    return "nula"


def _p_label(p: float) -> str:
    if pd.isna(p):
        return "no calculable"
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.4f}"


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "app": "CP_CORRELACION"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    df = _normalize_df(req.rows)

    required = [req.se_col, req.value_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {', '.join(missing)}")

    if req.variable_x == req.variable_y:
        raise HTTPException(status_code=400, detail="La variable X y la variable Y deben ser distintas.")

    df["assessment_value_num"] = _to_numeric_series_strong(df[req.value_col])
    df[req.se_col] = df[req.se_col].astype(str).str.strip()

    group_cols = _safe_key_cols(req.group_cols, df)
    unit_cols = _safe_key_cols(req.unit_cols, df)
    descriptive_cols = _safe_key_cols(req.descriptive_cols, df)

    reserved = {req.se_col, req.value_col, "assessment_value_num"}
    descriptive_cols = [c for c in descriptive_cols if c not in reserved]

    if not unit_cols:
        # Modo flexible: si el usuario no eligió unidad experimental, usa todas las columnas no numéricas
        # que no sean variables ni descriptivas como clave de emparejamiento. Esto ayuda cuando la tabla es dinámica.
        candidates = [c for c in df.columns if c not in reserved and c not in descriptive_cols]
        unit_cols = [c for c in candidates if c not in group_cols]

    key_cols = group_cols + [c for c in unit_cols if c not in group_cols]

    filtered = df[df[req.se_col].isin([req.variable_x, req.variable_y])].copy()
    if filtered.empty:
        raise HTTPException(status_code=400, detail="No se encontraron filas para las variables seleccionadas.")

    filtered_valid = filtered.dropna(subset=["assessment_value_num"]).copy()
    if filtered_valid.empty:
        raise HTTPException(status_code=400, detail="Las variables seleccionadas no tienen valores numéricos válidos.")

    agg_name = _agg_func(req.aggregation)
    pivot_index = key_cols if key_cols else ["__all__"]
    if not key_cols:
        filtered_valid["__all__"] = "TODOS"

    grouped_values = (
        filtered_valid
        .groupby(pivot_index + [req.se_col], dropna=False)["assessment_value_num"]
        .agg(agg_name)
        .reset_index()
    )

    paired = grouped_values.pivot_table(
        index=pivot_index,
        columns=req.se_col,
        values="assessment_value_num",
        aggfunc="first",
    ).reset_index()

    if req.variable_x not in paired.columns or req.variable_y not in paired.columns:
        raise HTTPException(status_code=400, detail="No se pudieron armar pares X/Y. Revisá las columnas de unidad experimental.")

    paired = paired.rename(columns={req.variable_x: "valor_variable_1", req.variable_y: "valor_variable_2"})
    paired["variable_1"] = req.variable_x
    paired["variable_2"] = req.variable_y
    paired["par_valido"] = paired["valor_variable_1"].notna() & paired["valor_variable_2"].notna()

    # Agrega columnas descriptivas a nivel de grupo o unidad, conservando contexto.
    if descriptive_cols:
        desc_source = filtered.copy()
        if not key_cols:
            desc_source["__all__"] = "TODOS"
        desc_rows = (
            desc_source
            .groupby(pivot_index, dropna=False)[descriptive_cols]
            .agg(lambda s: _unique_join(s, req.conflict_mode))
            .reset_index()
        )
        paired = paired.merge(desc_rows, on=pivot_index, how="left")

    # Orden de columnas amigable
    ordered = []
    for c in group_cols + [c for c in unit_cols if c not in group_cols]:
        if c in paired.columns and c not in ordered:
            ordered.append(c)
    for c in descriptive_cols:
        if c in paired.columns and c not in ordered:
            ordered.append(c)
    ordered += ["variable_1", "valor_variable_1", "variable_2", "valor_variable_2", "par_valido"]
    paired = paired[[c for c in ordered if c in paired.columns]]

    corr_groups = group_cols if group_cols else ["__all__"]
    if "__all__" not in paired.columns and not group_cols:
        paired["__all__"] = "TODOS"

    correlation_rows: list[dict[str, Any]] = []
    warning_rows: list[dict[str, Any]] = []

    for group_key, sub in paired.groupby(corr_groups, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        group_dict = dict(zip(corr_groups, group_key, strict=False))
        valid = sub[sub["par_valido"]].copy()
        n = len(valid)
        r, p, err = _corr(valid["valor_variable_1"], valid["valor_variable_2"], req.method)
        row = {
            **group_dict,
            "analysis_name": req.analysis_name,
            "variable_1": req.variable_x,
            "variable_2": req.variable_y,
            "method": req.method,
            "n_pares": n,
            "r": r,
            "r_abs": abs(r) if not pd.isna(r) else np.nan,
            "p_value": p,
            "direccion": _direction(r),
            "fuerza": _strength(r),
            "significativo_0_05": bool(p < 0.05) if not pd.isna(p) else False,
            "interpretacion": f"Correlación {_direction(r)} {_strength(r)} ({_p_label(p)})." if not err else err,
        }
        correlation_rows.append(row)
        if n < req.min_n or err:
            warning_rows.append({
                **group_dict,
                "warning": err or f"Grupo con n menor al mínimo configurado ({n} < {req.min_n}).",
                "n_pares": n,
            })

    correlations = pd.DataFrame(correlation_rows)
    warnings = pd.DataFrame(warning_rows) if warning_rows else pd.DataFrame(columns=[*corr_groups, "warning", "n_pares"])

    config = pd.DataFrame([
        {"campo": "se_col", "valor": req.se_col},
        {"campo": "value_col", "valor": req.value_col},
        {"campo": "variable_1", "valor": req.variable_x},
        {"campo": "variable_2", "valor": req.variable_y},
        {"campo": "group_cols", "valor": " | ".join(group_cols)},
        {"campo": "unit_cols", "valor": " | ".join(unit_cols)},
        {"campo": "descriptive_cols", "valor": " | ".join(descriptive_cols)},
        {"campo": "method", "valor": req.method},
        {"campo": "aggregation", "valor": req.aggregation},
        {"campo": "conflict_mode", "valor": req.conflict_mode},
        {"campo": "min_n", "valor": req.min_n},
    ])

    variable_summary = (
        filtered_valid
        .groupby([req.se_col], dropna=False)
        .agg(
            n=("assessment_value_num", "count"),
            mean=("assessment_value_num", "mean"),
            median=("assessment_value_num", "median"),
            sd=("assessment_value_num", "std"),
            min=("assessment_value_num", "min"),
            max=("assessment_value_num", "max"),
        )
        .reset_index()
        .rename(columns={req.se_col: "se_name_mod"})
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="input_enriched", index=False)
        paired.to_excel(writer, sheet_name="paired_data", index=False)
        correlations.to_excel(writer, sheet_name="correlations", index=False)
        variable_summary.to_excel(writer, sheet_name="variable_summary", index=False)
        config.to_excel(writer, sheet_name="config", index=False)
        warnings.to_excel(writer, sheet_name="warnings", index=False)

        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for col in sheet.columns:
                max_len = 10
                letter = col[0].column_letter
                for cell in col[:1000]:
                    if cell.value is not None:
                        max_len = max(max_len, min(len(str(cell.value)) + 2, 45))
                sheet.column_dimensions[letter].width = max_len

    output.seek(0)
    filename = f"CP_CORRELACION_{req.analysis_name or 'analisis'}.xlsx".replace(" ", "_")
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
