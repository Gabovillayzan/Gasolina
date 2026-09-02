"""Ranking de conveniencia: precio final, distancia y descuento combinados."""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.constants import DISCOUNTS, RANK_WEIGHTS
from utils.geo import haversine_km


def apply_discounts(df: pd.DataFrame, enabled_brands: set[str]) -> pd.DataFrame:
    """Calcula precio_final segun las marcas de descuento habilitadas.

    El descuento solo se aplica si la estacion es elegible Y el usuario activo
    esa marca. El precio final nunca baja de cero.
    """
    out = df.copy()
    brand = out["discount_brand"].fillna("")
    eligible = brand.isin(enabled_brands)

    amount = brand.map(DISCOUNTS).fillna(0.0).astype(float)
    out["descuento_aplicado"] = np.where(eligible, amount, 0.0)
    out["tiene_descuento"] = eligible
    out["precio_final"] = (out["precio_base"] - out["descuento_aplicado"]).clip(lower=0.0)
    return out


def add_distance(df: pd.DataFrame, lat: float, lon: float) -> pd.DataFrame:
    """Agrega distancia en km desde la ubicacion del usuario."""
    out = df.copy()
    out["distancia_km"] = haversine_km(lat, lon, out["lat"].values, out["lon"].values)
    return out


def filter_radius(df: pd.DataFrame, radius_km: float) -> pd.DataFrame:
    return df[df["distancia_km"] <= radius_km].copy()


def _min_max_norm(series: pd.Series, invert: bool = True) -> pd.Series:
    """Escala a 0..1. Con invert=True, menor valor -> mejor puntaje."""
    lo, hi = series.min(), series.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return pd.Series(np.ones(len(series)), index=series.index)
    scaled = (series - lo) / (hi - lo)
    return 1.0 - scaled if invert else scaled


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Puntaje de conveniencia 0..1 (mas alto es mejor).

    Combina precio final y distancia normalizados dentro del conjunto visible,
    mas un bono por descuento. Los pesos viven en RANK_WEIGHTS y se ajustan ahi;
    deliberadamente no se ordena solo por precio ni solo por cercania.
    """
    out = df.copy()
    if out.empty:
        out["score"] = []
        return out

    price_score = _min_max_norm(out["precio_final"])
    dist_score = _min_max_norm(out["distancia_km"])
    disc_score = out["tiene_descuento"].astype(float)

    out["score"] = (
        RANK_WEIGHTS["price"] * price_score
        + RANK_WEIGHTS["distance"] * dist_score
        + RANK_WEIGHTS["discount"] * disc_score
    )
    return out.sort_values(["score", "precio_final", "distancia_km"],
                           ascending=[False, True, True])


def rank_stations(
    df: pd.DataFrame, lat: float, lon: float, radius_km: float, enabled_brands: set[str]
) -> pd.DataFrame:
    """Pipeline completo: distancia -> radio -> descuentos -> puntaje."""
    ranked = add_distance(df, lat, lon)
    ranked = filter_radius(ranked, radius_km)
    ranked = apply_discounts(ranked, enabled_brands)
    return score(ranked)


def split_results(
    ranked: pd.DataFrame, top_discount: int, top_others: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa el ranking en bloque con descuento y bloque de otros grifos."""
    with_disc = ranked[ranked["tiene_descuento"]].head(top_discount)
    others = ranked[~ranked["tiene_descuento"]].head(top_others)
    return with_disc, others
