"""Descarga, procesamiento y cache del maestro de precios EVPC (Osinergmin).

Flujo de datos en servidor (no se reprocesa por usuario ni por sesion):

    1. Descarga del Excel EVPC una vez al dia          -> cache/evpc_raw_YYYYMMDD.xlsx
    2. Limpieza + normalizacion una sola vez           -> cache/evpc_processed_YYYYMMDD.parquet
    3. Cruce con descuentos, ya integrado              -> cache/joined_dataset_YYYYMMDD.parquet
    4. Todos los usuarios consumen el parquet final

Si la descarga del dia falla se reutiliza la ultima version valida en disco y se
informa por `DatasetMeta.stale`.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests

from utils.cleaners import clean_display, norm_address, norm_admin, norm_key
from utils.constants import (
    CACHE_DIR,
    EVPC_SEED,
    EVPC_URL,
    EVPC_URL_FALLBACKS,
    FUEL_FAMILIES,
    HTTP_HEADERS,
    HTTP_TIMEOUT,
)
from utils.geo import attach_centroids
from utils.matcher import attach_discounts

REQUIRED_COLUMNS = [
    "NRO_REGISTRO", "RAZON", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
    "DIRECCION", "FCHA_REGISTRO", "PRODUCTO", "PRECIO_VENTA", "CODIGO_OSINERG",
]

# Familias tecnicas -> etiqueta visible en la UI.
PRODUCT_TO_FAMILY = {
    product: family for family, products in FUEL_FAMILIES.items() for product in products
}

BRAND_PATTERNS = [
    ("REPSOL", re.compile(r"\bREPSOL\b")),
    ("PRIMAX", re.compile(r"\bPRIMAX\b|\bCOESTI\b")),
]


@dataclass
class DatasetMeta:
    """Procedencia del dataset servido, para mostrarla en la UI."""
    source_date: dt.date
    published_at: dt.datetime | None   # Last-Modified del archivo en Osinergmin
    last_price_at: dt.datetime | None  # FCHA_REGISTRO mas reciente del dataset
    stale: bool                        # True si se sirvio una version anterior
    origin: str                        # descarga | cache | semilla
    rows: int
    stations: int


def _today() -> dt.date:
    return dt.date.today()


def _raw_path(day: dt.date) -> Path:
    return CACHE_DIR / f"evpc_raw_{day:%Y%m%d}.xlsx"


def _processed_path(day: dt.date) -> Path:
    return CACHE_DIR / f"evpc_processed_{day:%Y%m%d}.parquet"


def _joined_path(day: dt.date) -> Path:
    return CACHE_DIR / f"joined_dataset_{day:%Y%m%d}.parquet"


def _meta_path(day: dt.date) -> Path:
    return CACHE_DIR / f"meta_{day:%Y%m%d}.json"


def _latest_existing(pattern: str) -> Path | None:
    """Archivo de cache mas reciente que exista (respaldo cuando falla el dia)."""
    hits = sorted(CACHE_DIR.glob(pattern))
    return hits[-1] if hits else None


def _candidate_urls() -> list[str]:
    year = _today().year
    urls = [EVPC_URL]
    for template in EVPC_URL_FALLBACKS:
        for candidate_year in (year, year - 1):
            url = template.format(year=candidate_year)
            if url not in urls:
                urls.append(url)
    return urls


def download_raw(day: dt.date | None = None) -> tuple[Path | None, dt.datetime | None]:
    """Descarga el Excel del dia si aun no esta en cache.

    Osinergmin responde 403 sin User-Agent de navegador, por eso van headers.
    Devuelve (ruta, fecha_de_publicacion) o (None, None) si ninguna URL sirvio.
    """
    day = day or _today()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = _raw_path(day)
    if target.exists() and target.stat().st_size > 0:
        return target, _read_published_at(day)

    for url in _candidate_urls():
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            if not resp.content or len(resp.content) < 10_000:
                continue
            target.write_bytes(resp.content)
            published = None
            if "Last-Modified" in resp.headers:
                try:
                    published = parsedate_to_datetime(resp.headers["Last-Modified"])
                except (TypeError, ValueError):
                    published = None
            _write_published_at(day, published)
            return target, published
        except (requests.RequestException, OSError):
            continue
    return None, None


def _write_published_at(day: dt.date, published: dt.datetime | None) -> None:
    import json
    payload = {"published_at": published.isoformat() if published else None}
    _meta_path(day).write_text(json.dumps(payload), encoding="utf-8")


def _read_published_at(day: dt.date) -> dt.datetime | None:
    import json
    path = _meta_path(day)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("published_at")
        return dt.datetime.fromisoformat(raw) if raw else None
    except (ValueError, OSError):
        return None


def validate_columns(df: pd.DataFrame) -> None:
    """Falla temprano y con mensaje claro si Osinergmin cambia el esquema."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"El Excel EVPC no trae las columnas esperadas: {missing}. "
            "Revisar el formato de la fuente en Osinergmin."
        )


def _detect_brand(razon_norm: str) -> str:
    for brand, pattern in BRAND_PATTERNS:
        if pattern.search(razon_norm):
            return brand
    return "OTRO"


def process_raw(path: Path) -> pd.DataFrame:
    """Excel crudo -> dataset limpio, una fila por estacion y familia de combustible.

    Una estacion puede vender GASOHOL y GASOLINA de la misma familia; se conserva
    el precio mas bajo, que es la opcion que le conviene al usuario.
    """
    raw = pd.read_excel(path)
    validate_columns(raw)

    df = raw[raw["PRODUCTO"].isin(PRODUCT_TO_FAMILY)].copy()
    df["fuel"] = df["PRODUCTO"].map(PRODUCT_TO_FAMILY)
    df["precio_base"] = pd.to_numeric(df["PRECIO_VENTA"], errors="coerce")
    df = df[df["precio_base"] > 0]

    # Solo productos vigentes con precio real reportado.
    if "PRODUCTO_ACTIVO" in df.columns:
        df = df[df["PRODUCTO_ACTIVO"].astype(str).str.upper().str.strip() != "NO"]
    if "ULT_PRECIO_DIF_CERO" in df.columns:
        df = df[df["ULT_PRECIO_DIF_CERO"].astype(str).str.upper().str.strip() != "NO"]

    df["codigo_osinerg"] = pd.to_numeric(df["CODIGO_OSINERG"], errors="coerce").astype("Int64").astype(str)
    df["nro_registro"] = df["NRO_REGISTRO"].map(norm_key)
    df["razon_display"] = df["RAZON"].map(clean_display)
    df["razon_norm"] = df["RAZON"].map(norm_key)
    df["direccion_display"] = df["DIRECCION"].map(clean_display)
    df["direccion_norm"] = df["DIRECCION"].map(norm_address)
    df["departamento"] = df["DEPARTAMENTO"].map(clean_display)
    df["provincia"] = df["PROVINCIA"].map(clean_display)
    df["distrito"] = df["DISTRITO"].map(clean_display)
    df["dep_norm"] = df["DEPARTAMENTO"].map(norm_admin)
    df["prov_norm"] = df["PROVINCIA"].map(norm_admin)
    df["dist_norm"] = df["DISTRITO"].map(norm_key)
    df["fecha_precio"] = pd.to_datetime(df["FCHA_REGISTRO"], errors="coerce")
    df["brand_razon"] = df["razon_norm"].map(_detect_brand)

    keep = [
        "codigo_osinerg", "nro_registro", "razon_display", "razon_norm",
        "direccion_display", "direccion_norm", "departamento", "provincia",
        "distrito", "dep_norm", "prov_norm", "dist_norm", "fuel",
        "precio_base", "fecha_precio", "brand_razon",
    ]
    df = df.sort_values("precio_base").drop_duplicates(
        subset=["codigo_osinerg", "fuel"], keep="first"
    )
    return df[keep].reset_index(drop=True)


def build_joined(processed: pd.DataFrame) -> pd.DataFrame:
    """Agrega coordenadas y elegibilidad de descuento al dataset limpio."""
    stations = processed.drop_duplicates("codigo_osinerg")[
        ["codigo_osinerg", "nro_registro", "direccion_norm", "brand_razon",
         "dep_norm", "prov_norm", "dist_norm"]
    ].copy()
    stations["lat"] = pd.NA
    stations["lon"] = pd.NA

    stations = attach_centroids(stations)
    stations = attach_discounts(stations)

    cols = ["codigo_osinerg", "lat", "lon", "coord_source",
            "discount_brand", "match_method", "match_confidence"]
    joined = processed.merge(stations[cols], on="codigo_osinerg", how="left")
    joined = joined.dropna(subset=["lat", "lon"])

    # Marca visible: la lista de beneficios manda; si no, lo que diga la razon social.
    joined["brand"] = joined["discount_brand"].fillna(joined["brand_razon"])
    return joined.reset_index(drop=True)


def _meta_from_frame(
    df: pd.DataFrame, day: dt.date, published: dt.datetime | None,
    stale: bool, origin: str,
) -> DatasetMeta:
    last_price = df["fecha_precio"].max() if "fecha_precio" in df.columns else None
    if pd.isna(last_price):
        last_price = None
    return DatasetMeta(
        source_date=day,
        published_at=published,
        last_price_at=last_price.to_pydatetime() if hasattr(last_price, "to_pydatetime") else last_price,
        stale=stale,
        origin=origin,
        rows=len(df),
        stations=int(df["codigo_osinerg"].nunique()) if len(df) else 0,
    )


def build_dataset(day: dt.date | None = None) -> tuple[pd.DataFrame, DatasetMeta]:
    """Devuelve el dataset final del dia, construyendolo solo si hace falta.

    Orden de preferencia:
        1. joined parquet del dia (ya construido por otra sesion)
        2. descarga + procesamiento del dia
        3. ultimo joined parquet valido en disco (se marca stale)
        4. Excel semilla incluido en el repo
    """
    day = day or _today()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    joined_today = _joined_path(day)
    if joined_today.exists():
        df = pd.read_parquet(joined_today)
        return df, _meta_from_frame(df, day, _read_published_at(day), False, "cache")

    raw_path, published = download_raw(day)
    if raw_path is not None:
        try:
            processed = process_raw(raw_path)
            processed.to_parquet(_processed_path(day), index=False)
            joined = build_joined(processed)
            joined.to_parquet(joined_today, index=False)
            return joined, _meta_from_frame(joined, day, published, False, "descarga")
        except (ValueError, OSError):
            pass  # esquema cambiado o disco lleno: caemos al respaldo

    previous = _latest_existing("joined_dataset_*.parquet")
    if previous is not None:
        df = pd.read_parquet(previous)
        prev_day = dt.datetime.strptime(previous.stem.split("_")[-1], "%Y%m%d").date()
        return df, _meta_from_frame(df, prev_day, _read_published_at(prev_day), True, "cache")

    if EVPC_SEED.exists():
        processed = process_raw(EVPC_SEED)
        joined = build_joined(processed)
        joined.to_parquet(joined_today, index=False)
        return joined, _meta_from_frame(joined, day, None, True, "semilla")

    raise RuntimeError(
        "No se pudo obtener el maestro EVPC: fallo la descarga y no hay cache ni semilla."
    )


def warm_cache() -> DatasetMeta:
    """Precalienta la cache del dia. Util para un cron o un primer arranque."""
    _, meta = build_dataset()
    return meta


def purge_old_cache(keep_days: int = 5) -> int:
    """Borra caches antiguas para que el disco del servidor no crezca sin limite."""
    removed = 0
    for pattern in ("evpc_raw_*.xlsx", "evpc_processed_*.parquet",
                    "joined_dataset_*.parquet", "meta_*.json"):
        files = sorted(CACHE_DIR.glob(pattern))
        for path in files[:-keep_days] if len(files) > keep_days else []:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def reset_cache() -> None:
    """Vacia la cache por completo (solo para desarrollo)."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
