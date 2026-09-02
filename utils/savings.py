"""Ahorro potencial por tanque frente al promedio de la zona del usuario."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from utils.constants import TANK_GALLONS

MIN_SAMPLE = 3  # menos de esto no es un promedio confiable


@dataclass
class Savings:
    """Resultado del calculo de ahorro."""
    amount: float          # soles por tanque lleno
    reference_price: float # promedio usado como referencia
    best_price: float      # precio final de la mejor opcion
    scope: str             # distrito | provincia | radio | muestra
    scope_label: str
    sample_size: int

    @property
    def is_positive(self) -> bool:
        return self.amount > 0


def _average(df: pd.DataFrame, column: str = "precio_base") -> float | None:
    if len(df) < MIN_SAMPLE:
        return None
    value = df[column].mean()
    return float(value) if pd.notna(value) else None


def reference_price(
    dataset: pd.DataFrame, visible: pd.DataFrame, fuel: str, admin: dict
) -> tuple[float | None, str, str, int]:
    """Precio de referencia con cadena de respaldo.

    distrito -> provincia -> radio local -> muestra visible.
    Usa precio_base (sin descuento) para que el ahorro compare contra el
    mercado, no contra otra promocion.
    """
    same_fuel = dataset[dataset["fuel"] == fuel]

    district = same_fuel[
        (same_fuel["dep_norm"] == admin.get("dep_norm"))
        & (same_fuel["dist_norm"] == admin.get("dist_norm"))
    ]
    avg = _average(district)
    if avg is not None:
        return avg, "distrito", admin.get("label", "tu distrito"), len(district)

    province = same_fuel[
        (same_fuel["dep_norm"] == admin.get("dep_norm"))
        & (same_fuel["prov_norm"] == admin.get("prov_norm"))
    ]
    avg = _average(province)
    if avg is not None:
        return avg, "provincia", "tu provincia", len(province)

    avg = _average(visible)
    if avg is not None:
        return avg, "radio", "los grifos cerca de ti", len(visible)

    if len(visible):
        return float(visible["precio_base"].mean()), "muestra", "la muestra cercana", len(visible)
    return None, "muestra", "", 0


def compute_savings(
    dataset: pd.DataFrame, visible: pd.DataFrame, best_row: pd.Series,
    fuel: str, admin: dict,
) -> Savings | None:
    """Ahorro = (promedio de la zona - precio final sugerido) * galones del tanque."""
    ref, scope, label, sample = reference_price(dataset, visible, fuel, admin)
    if ref is None:
        return None

    best = float(best_row["precio_final"])
    return Savings(
        amount=(ref - best) * TANK_GALLONS,
        reference_price=ref,
        best_price=best,
        scope=scope,
        scope_label=label,
        sample_size=sample,
    )
