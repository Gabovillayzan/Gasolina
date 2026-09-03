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


# JS propio: el helper de la libreria llama a getCurrentPosition() SIN opciones,
# asi que enableHighAccuracy queda en false y devuelve posicion por WiFi/antena.
# Con estas opciones se pide GPS real. El componente resuelve promesas.
_GEO_JS = """new Promise(async (res) => {
  if (!navigator.geolocation) { res({error: 'unsupported'}); return; }
  let perm = 'unknown';
  try {
    if (navigator.permissions) {
      perm = (await navigator.permissions.query({name: 'geolocation'})).state;
    }
  } catch (e) {}
  navigator.geolocation.getCurrentPosition(
    (p) => res({lat: p.coords.latitude, lon: p.coords.longitude,
                acc: p.coords.accuracy, perm: perm}),
    (e) => res({error: e.code === 1 ? 'denied'
                     : e.code === 3 ? 'timeout' : 'unavailable', perm: perm}),
    {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000}
  );
})"""


def request_browser_location(attempt: int = 0) -> dict | None:
    """Pide la ubicacion real al navegador y devuelve el resultado crudo.

    Se monta en el primer render, no detras de un boton: asi el permiso aparece
    mientras los datos cargan, en vez de encadenar un rerun antes de preguntar.
    Nunca usa la IP del servidor.

    Devuelve None mientras el navegador aun no responde, o un dict con lat/lon
    o con `error` en ('denied', 'unavailable', 'timeout', 'unsupported').

    Tambien devuelve `perm`, el estado del permiso del navegador. Sirve para
    separar dos fallos que se sienten iguales pero se arreglan distinto: el
    permiso denegado en el navegador, y el permiso concedido pero con la
    ubicacion del telefono apagada.
    """
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return {"error": "unsupported"}
    try:
        result = streamlit_js_eval(js_expressions=_GEO_JS, key=f"geo_{attempt}")
    except Exception:
        return {"error": "unavailable"}
    if not isinstance(result, dict):
        return None
    if "error" in result:
        return {"error": result["error"], "perm": result.get("perm", "unknown")}
    if result.get("lat") is None or result.get("lon") is None:
        return None
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "accuracy": result.get("acc"),
        "perm": result.get("perm", "unknown"),
    }


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
