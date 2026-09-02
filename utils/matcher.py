"""Cruce entre el maestro Osinergmin y las listas de descuento (Primax/Repsol).

HALLAZGO SOBRE LOS DATOS
------------------------
CODIGO_OSINERG se intenta primero, pero en la practica casi no cruza: las listas
de beneficios y el maestro EVPC usan numeraciones distintas. Ejemplo verificado,
la misma estacion fisica (Repsol, Av. Primavera 1095, San Borja):

    lista de descuentos -> CODIGO_OSINERG 14662
    maestro EVPC        -> CODIGO_OSINERG 18871

De 290 codigos en las listas solo 12 existen en el maestro. NRO_REGISTRO tampoco
cruza (interseccion 0). Por eso la llave real de trabajo es geografico-textual y
va SIEMPRE restringida por marca.

ESTRATEGIA
----------
El maestro identifica la marca en RAZON (COESTI/PRIMAX, REPSOL): 112 estaciones
Repsol y 239 Primax, cifras consistentes con las 352 filas de las listas. Acotar
los candidatos a la misma marca y el mismo distrito reduce el espacio de decision
a unas pocas estaciones y hace confiable el match textual.

Cadena de resolucion, de mayor a menor confianza:

    1. CODIGO_OSINERG identico                          1.00
    2. misma marca + distrito + direccion normalizada    0.95
    3. misma marca + distrito + par unico                0.90
    4. misma marca + distrito + direccion fuzzy          0.80

Nota: las coordenadas NO sirven como llave. El maestro no trae coordenadas
propias (se le asignan centroides distritales), asi que cruzar por cercania
matchearia con cualquier estacion del mismo distrito. Se usan en sentido
inverso: para MEJORAR la coordenada de la estacion ya matcheada.

Todo match por debajo de MATCH_MIN_CONFIDENCE se descarta sin aplicar descuento:
preferimos exactitud antes que cobertura artificial.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from utils.cleaners import clean_display, norm_address, norm_admin, norm_key
from utils.constants import (
    FUZZY_MIN_SCORE,
    MATCH_MIN_CONFIDENCE,
    PRIMAX_XLSX,
    REPSOL_XLSX,
)

CONFIDENCE = {
    "codigo_osinerg": 1.00,
    "marca_direccion": 0.95,
    "marca_par_unico": 0.90,
    "marca_fuzzy_alto": 0.85,
    "marca_fuzzy": 0.80,
}

# Ruido de direccion que difiere entre fuentes y no ayuda a identificar la estacion.
_NOISE_RE = re.compile(
    r"(MZ|MZA|LOTE|LT|URB|ESQ|ESQUINA|CON|SECTOR|PROGRAMA|CDRA|CUADRA"
    r"|NRO|SN|PJ|ASOC|ASOCIACION|ETAPA|SUB|PARCELA|KM)"
)
_NUMBER_RE = re.compile(r"\d{2,5}")
_SPACES_RE = re.compile(r"\s+")

NUMBER_BONUS = 12    # misma numeracion municipal: fuerte senal de identidad
NUMBER_PENALTY = -8  # numeraciones distintas en la misma calle: sospechoso

DISCOUNT_COLUMNS = [
    "brand", "codigo_osinerg", "nro_registro", "direccion_norm",
    "dep_norm", "prov_norm", "dist_norm", "lat", "lon", "nombre",
]

_MATCH_OUTPUT = ["codigo_osinerg", "brand", "match_method", "lat_disc", "lon_disc"]


def _pick(df: pd.DataFrame, *candidates: str) -> pd.Series:
    """Primera columna existente, tolerando guiones bajos y mayusculas.

    Las fuentes alternan entre CODIGOOSINERG y CODIGO_OSINERG, DISTRITOFINAL y
    DISTRITO_FINAL, etc.
    """
    normalized = {c.upper().replace("_", "").replace(" ", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.upper().replace("_", "").replace(" ", "")
        if key in normalized:
            return df[normalized[key]]
    return pd.Series([np.nan] * len(df), index=df.index)


def _to_code(series: pd.Series) -> pd.Series:
    """CODIGO_OSINERG a string canonico (llega como float con .0)."""
    num = pd.to_numeric(series, errors="coerce")
    return num.astype("Int64").astype(str).replace("<NA>", "")


def _normalize_discount_frame(df: pd.DataFrame, brand: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["brand"] = brand
    out["codigo_osinerg"] = _to_code(_pick(df, "CODIGO_OSINERG", "CODIGOOSINERG"))
    out["nro_registro"] = _pick(df, "NRO_REGISTRO", "NROREGISTRO").map(norm_key)
    out["direccion_norm"] = _pick(
        df, "DIRECCION_OSINERG", "DIRECCIONOSINERG", "DIRECCION", "Direccion_Calle"
    ).map(norm_address)
    out["dep_norm"] = _pick(
        df, "DEPARTAMENTO_FINAL", "DEPARTAMENTOFINAL", "DEPARTAMENTO"
    ).map(norm_admin)
    out["prov_norm"] = _pick(
        df, "PROVINCIA_FINAL", "PROVINCIAFINAL", "PROVINCIA"
    ).map(norm_admin)
    out["dist_norm"] = _pick(df, "DISTRITO_FINAL", "DISTRITOFINAL", "DISTRITO").map(norm_key)
    out["lat"] = pd.to_numeric(_pick(df, "LATITUD", "Latitud", "latitude"), errors="coerce")
    out["lon"] = pd.to_numeric(_pick(df, "LONGITUD", "Longitud", "longitude"), errors="coerce")
    out["nombre"] = _pick(df, "Nombre", "name", "MARCA").map(clean_display)
    return out


def load_discount_lists() -> pd.DataFrame:
    """Carga y normaliza ambas listas de beneficios en un solo frame."""
    frames = []
    for path, brand in ((REPSOL_XLSX, "REPSOL"), (PRIMAX_XLSX, "PRIMAX")):
        if not path.exists():
            continue
        frames.append(_normalize_discount_frame(pd.read_excel(path), brand))
    if not frames:
        return pd.DataFrame(columns=DISCOUNT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _empty_matches() -> pd.DataFrame:
    return pd.DataFrame(columns=_MATCH_OUTPUT)


def _match_by_code(stations: pd.DataFrame, disc: pd.DataFrame) -> pd.DataFrame:
    """Nivel 1: CODIGO_OSINERG identico. Certero, aunque cubre poco."""
    coded = disc[disc["codigo_osinerg"] != ""].drop_duplicates("codigo_osinerg")
    if coded.empty:
        return _empty_matches()
    coded = coded[["codigo_osinerg", "brand", "lat", "lon"]].rename(
        columns={"lat": "lat_disc", "lon": "lon_disc"})
    hit = stations.merge(coded, on="codigo_osinerg", how="inner")
    if hit.empty:
        return _empty_matches()
    # Los codigos pertenecen a numeraciones distintas: si la marca del maestro
    # contradice la de la lista, el cruce es una colision casual, no un match.
    hit = hit[hit["brand"] == hit["brand_razon"]]
    if hit.empty:
        return _empty_matches()
    hit["match_method"] = "codigo_osinerg"
    return hit[_MATCH_OUTPUT]


def _match_by_address(stations: pd.DataFrame, disc: pd.DataFrame) -> pd.DataFrame:
    """Nivel 2: misma marca, mismo distrito y direccion normalizada identica."""
    keyed = disc[disc["direccion_norm"] != ""].drop_duplicates(
        subset=["brand", "dep_norm", "dist_norm", "direccion_norm"]
    )
    if keyed.empty:
        return _empty_matches()
    keyed = keyed[["brand", "dep_norm", "dist_norm", "direccion_norm", "lat", "lon"]].rename(
        columns={"lat": "lat_disc", "lon": "lon_disc"})
    hit = stations.merge(
        keyed,
        left_on=["brand_razon", "dep_norm", "dist_norm", "direccion_norm"],
        right_on=["brand", "dep_norm", "dist_norm", "direccion_norm"],
        how="inner",
    )
    if hit.empty:
        return _empty_matches()
    hit["match_method"] = "marca_direccion"
    return hit[_MATCH_OUTPUT]


def _match_unique_pair(stations: pd.DataFrame, disc: pd.DataFrame) -> pd.DataFrame:
    """Nivel 3: en el distrito hay exactamente una estacion de la marca y una
    entrada en la lista. La correspondencia es forzosa y por lo tanto segura."""
    if stations.empty or disc.empty:
        return _empty_matches()

    st_keys = ["brand_razon", "dep_norm", "dist_norm"]
    dc_keys = ["brand", "dep_norm", "dist_norm"]

    st_solo = stations[stations.groupby(st_keys)["codigo_osinerg"].transform("size") == 1]
    dc_solo = disc[disc.groupby(dc_keys)["brand"].transform("size") == 1]
    if st_solo.empty or dc_solo.empty:
        return _empty_matches()

    dc_solo = dc_solo[dc_keys + ["lat", "lon"]].rename(
        columns={"lat": "lat_disc", "lon": "lon_disc"})
    hit = st_solo.merge(dc_solo, left_on=st_keys, right_on=dc_keys, how="inner")
    if hit.empty:
        return _empty_matches()
    hit["match_method"] = "marca_par_unico"
    return hit[_MATCH_OUTPUT]


def _address_core(address: str) -> str:
    """Quita ruido de lote/manzana/urbanizacion y deja calle + numero."""
    return _SPACES_RE.sub(" ", _NOISE_RE.sub(" ", address)).strip()


def _house_numbers(address: str) -> set[str]:
    return set(_NUMBER_RE.findall(address))


def _address_similarity(left: str, right: str) -> float:
    """Similitud 0..100 entre dos direcciones de la misma zona.

    Las fuentes describen la misma estacion de formas distintas
    ('AV ROOSELVELT ... CDRA 6' vs 'AV ROOSEVELT ... CUADRA 6 SURCO'), asi que
    se compara el nucleo de la direccion y se premia o castiga la numeracion.
    """
    from rapidfuzz import fuzz

    core_left, core_right = _address_core(left), _address_core(right)
    score = max(
        fuzz.token_set_ratio(core_left, core_right),
        fuzz.partial_ratio(core_left, core_right),
    )
    nums_left, nums_right = _house_numbers(left), _house_numbers(right)
    if nums_left and nums_right:
        score += NUMBER_BONUS if nums_left & nums_right else NUMBER_PENALTY
    return float(min(score, 100.0))


def _assign_pool(pool_stations: pd.DataFrame, pool_entries: pd.DataFrame) -> list[tuple]:
    """Emparejamiento mutuo por mejor puntaje dentro de una marca y distrito.

    Ambos lados describen el mismo conjunto de estaciones fisicas, asi que se
    resuelve como asignacion: se toma el mejor par disponible y se consume de
    los dos lados. Eso evita que dos estaciones reclamen la misma entrada.
    """
    scored = []
    for i, station in enumerate(pool_stations.itertuples()):
        if not station.direccion_norm:
            continue
        for j, entry in enumerate(pool_entries.itertuples()):
            value = _address_similarity(station.direccion_norm, entry.direccion_norm)
            if value >= FUZZY_MIN_SCORE:
                scored.append((value, i, j))

    scored.sort(reverse=True)
    used_stations: set[int] = set()
    used_entries: set[int] = set()
    pairs = []
    for value, i, j in scored:
        if i in used_stations or j in used_entries:
            continue
        used_stations.add(i)
        used_entries.add(j)
        pairs.append((i, j, value))
    return pairs


def _match_fuzzy(stations: pd.DataFrame, disc: pd.DataFrame) -> pd.DataFrame:
    """Nivel 4: asignacion por direccion dentro de la misma marca y distrito."""
    if stations.empty or disc.empty:
        return _empty_matches()
    try:
        import rapidfuzz  # noqa: F401
    except ImportError:
        return _empty_matches()

    entries = disc[disc["direccion_norm"] != ""]
    rows = []
    for key, pool_stations in stations.groupby(["brand_razon", "dep_norm", "dist_norm"]):
        brand, dep, dist = key
        pool_entries = entries[
            (entries["brand"] == brand)
            & (entries["dep_norm"] == dep)
            & (entries["dist_norm"] == dist)
        ]
        if pool_entries.empty:
            continue
        for i, j, value in _assign_pool(pool_stations, pool_entries):
            entry = pool_entries.iloc[j]
            rows.append({
                "codigo_osinerg": pool_stations.iloc[i]["codigo_osinerg"],
                "brand": brand,
                "match_method": "marca_fuzzy_alto" if value >= 90 else "marca_fuzzy",
                "lat_disc": entry["lat"],
                "lon_disc": entry["lon"],
            })
    if not rows:
        return _empty_matches()
    return pd.DataFrame(rows, columns=_MATCH_OUTPUT)


def _run_cascade(stations: pd.DataFrame, disc: pd.DataFrame) -> pd.DataFrame:
    """Aplica los niveles en orden; cada uno solo ve lo que quedo pendiente."""
    branded = stations[stations["brand_razon"].isin(disc["brand"].unique())]
    collected: list[pd.DataFrame] = []
    resolved: set[str] = set()

    stages = [
        (_match_by_code, stations),
        (_match_by_address, branded),
        (_match_unique_pair, branded),
        (_match_fuzzy, branded),
    ]
    for matcher, pool in stages:
        pending = pool[~pool["codigo_osinerg"].isin(resolved)]
        if pending.empty:
            continue
        found = matcher(pending, disc)
        if found.empty:
            continue
        collected.append(found)
        resolved |= set(found["codigo_osinerg"])

    if not collected:
        return _empty_matches()
    return pd.concat(collected, ignore_index=True)


def _without_discounts(base: pd.DataFrame) -> pd.DataFrame:
    out = base.copy()
    out["discount_brand"] = pd.NA
    out["match_method"] = pd.NA
    out["match_confidence"] = 0.0
    return out


def attach_discounts(stations: pd.DataFrame) -> pd.DataFrame:
    """Marca elegibilidad de descuento sobre el maestro.

    Devuelve el maestro con discount_brand, match_method, match_confidence y
    coordenadas mejoradas donde la lista de beneficios aporta lat/lon real.
    """
    disc = load_discount_lists()
    base = stations.copy()
    if disc.empty:
        return _without_discounts(base)

    matched = _run_cascade(base, disc)
    if matched.empty:
        return _without_discounts(base)

    matched["match_confidence"] = matched["match_method"].map(CONFIDENCE).fillna(0.0)

    # Una estacion no puede quedar con dos marcas: gana la de mayor confianza.
    matched = matched.sort_values("match_confidence", ascending=False)
    matched = matched.drop_duplicates("codigo_osinerg", keep="first")

    # Descartar matches ambiguos antes de conceder cualquier beneficio.
    matched = matched[matched["match_confidence"] >= MATCH_MIN_CONFIDENCE]
    if matched.empty:
        return _without_discounts(base)

    out = base.merge(
        matched[["codigo_osinerg", "brand", "match_method",
                 "match_confidence", "lat_disc", "lon_disc"]],
        on="codigo_osinerg", how="left",
    ).rename(columns={"brand": "discount_brand"})

    # La coordenada real de la lista de beneficios reemplaza al centroide.
    upgrade = out["lat_disc"].notna() & out["lon_disc"].notna()
    out.loc[upgrade, "lat"] = out.loc[upgrade, "lat_disc"]
    out.loc[upgrade, "lon"] = out.loc[upgrade, "lon_disc"]
    out.loc[upgrade, "coord_source"] = "exacta"
    out = out.drop(columns=["lat_disc", "lon_disc"])

    out["match_confidence"] = out["match_confidence"].fillna(0.0)
    return out
