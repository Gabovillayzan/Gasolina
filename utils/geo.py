"""Distancias, centroides distritales y geolocalizacion del navegador."""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.cleaners import norm_admin, norm_key
from utils.constants import DISTRICTS_CSV

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2, lon2):
    """Distancia Haversine en km. Vectorizado: lat2/lon2 pueden ser arrays."""
    lat1r, lon1r = np.radians(lat1), np.radians(lon1)
    lat2r, lon2r = np.radians(lat2), np.radians(lon2)
    dlat, dlon = lat2r - lat1r, lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def load_district_centroids() -> pd.DataFrame:
    """Maestro de distritos del Peru con lat/lon (claves ya normalizadas)."""
    df = pd.read_csv(DISTRICTS_CSV)
    df["dep_norm"] = df["departamento"].map(norm_admin)
    df["prov_norm"] = df["provincia"].map(norm_admin)
    df["dist_norm"] = df["distrito"].map(norm_key)
    return df


def _centroid_lookups(centroids: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Tres niveles de respaldo: distrito exacto, dep+distrito, provincia."""
    exact = {
        (r.dep_norm, r.prov_norm, r.dist_norm): (r.lat, r.lon)
        for r in centroids.itertuples()
    }
    dep_dist = {
        (r.dep_norm, r.dist_norm): (r.lat, r.lon) for r in centroids.itertuples()
    }
    prov = (
        centroids.groupby(["dep_norm", "prov_norm"])[["lat", "lon"]]
        .mean()
        .apply(tuple, axis=1)
        .to_dict()
    )
    return exact, dep_dist, prov


def attach_centroids(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna lat/lon aproximada por distrito a estaciones sin coordenada real.

    El maestro EVPC no trae coordenadas, por eso este paso es obligatorio para
    que toda estacion pueda entrar al calculo de distancia. Marca el origen en
    `coord_source` para poder distinguir precision en la UI.
    """
    exact, dep_dist, prov = _centroid_lookups(load_district_centroids())
    out = df.copy()

    lats: list[float] = []
    lons: list[float] = []
    sources: list[str] = []
    for row in out.itertuples():
        lat, lon = getattr(row, "lat", np.nan), getattr(row, "lon", np.nan)
        if pd.notna(lat) and pd.notna(lon):
            lats.append(float(lat)); lons.append(float(lon)); sources.append("exacta")
            continue
        key3 = (row.dep_norm, row.prov_norm, row.dist_norm)
        hit = exact.get(key3) or dep_dist.get((row.dep_norm, row.dist_norm)) \
            or prov.get((row.dep_norm, row.prov_norm))
        if hit:
            lats.append(hit[0]); lons.append(hit[1]); sources.append("distrito")
        else:
            lats.append(np.nan); lons.append(np.nan); sources.append("sin_dato")

    out["lat"], out["lon"], out["coord_source"] = lats, lons, sources
    return out


def search_locations(query: str, centroids: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    """Busqueda manual de ubicacion por distrito/provincia (fallback sin GPS)."""
    q = norm_key(query)
    if len(q) < 3:
        return centroids.head(0)
    mask = (
        centroids["dist_norm"].str.contains(q, regex=False)
        | centroids["prov_norm"].str.contains(q, regex=False)
    )
    hits = centroids[mask].copy()
    # Coincidencia exacta de distrito primero, luego alfabetico.
    hits["_rank"] = np.where(hits["dist_norm"] == q, 0, 1)
    hits = hits.sort_values(["_rank", "distrito"]).head(limit)
    hits["label"] = hits["distrito"] + ", " + hits["provincia"] + " - " + hits["departamento"]
    return hits[["label", "lat", "lon", "dep_norm", "prov_norm", "dist_norm"]]


def get_browser_location() -> dict | None:
    """Pide la ubicacion real via navigator.geolocation del navegador.

    Nunca usa IP del servidor. Devuelve None si el usuario no da permiso,
    la libreria no esta disponible o el navegador aun no responde.
    """
    try:
        from streamlit_js_eval import get_geolocation
    except ImportError:
        return None
    try:
        pos = get_geolocation()
    except Exception:
        return None
    if not pos or "coords" not in pos:
        return None
    coords = pos["coords"]
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if lat is None or lon is None:
        return None
    return {"lat": float(lat), "lon": float(lon), "accuracy": coords.get("accuracy")}


def resolve_admin_from_point(lat: float, lon: float, centroids: pd.DataFrame) -> dict:
    """Distrito/provincia mas cercano a un punto (para el calculo de ahorro)."""
    d = haversine_km(lat, lon, centroids["lat"].values, centroids["lon"].values)
    row = centroids.iloc[int(np.argmin(d))]
    return {
        "dep_norm": row["dep_norm"],
        "prov_norm": row["prov_norm"],
        "dist_norm": row["dist_norm"],
        "label": f"{row['distrito']}, {row['provincia']}",
    }
