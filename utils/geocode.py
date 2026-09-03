"""Geocodificacion con Photon (OpenStreetMap).

Photon esta pensado para busqueda mientras se escribe y resuelve bien como
habla la gente aqui: "Larco con Benavides" cae en la esquina correcta de
Miraflores, cosa que Nominatim no logra. Se usa para los dos sentidos:

    search_places()  texto  -> puntos candidatos
    reverse_place()  punto  -> direccion legible

Es un servicio publico y gratuito, asi que se le pide poco: resultados
cacheados por el llamador, limite bajo y sesgo por cercania. Si falla o tarda,
las funciones devuelven vacio y la app sigue con el flujo normal: la
geocodificacion es una comodidad, nunca un requisito.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from utils.cleaners import clean_display

PHOTON_SEARCH = "https://photon.komoot.io/api/"
PHOTON_REVERSE = "https://photon.komoot.io/reverse"
TIMEOUT = 6
COUNTRY = "PE"

HEADERS = {
    "User-Agent": "GasolinApp/1.0 (+https://github.com/Gabovillayzan/Gasolina)",
}


@dataclass(frozen=True)
class Place:
    """Un resultado de busqueda listo para mostrar y usar."""
    label: str
    lat: float
    lon: float


def _street_line(props: dict) -> str:
    """Primera linea: calle con numero, o el nombre del lugar."""
    street = props.get("street")
    number = props.get("housenumber")
    name = props.get("name")

    if street and number:
        head = f"{street} {number}"
    elif street and name and name.lower() not in street.lower():
        # Caso tipico de una esquina: name es una via y street la otra.
        head = f"{street} con {name}"
    else:
        head = name or street or ""
    return clean_display(head)


def _area_line(props: dict) -> str:
    district = props.get("district")
    city = props.get("city") or props.get("county")
    parts = [p for p in (district, city) if p]
    # No repetir "Miraflores, Miraflores".
    if len(parts) == 2 and parts[0].lower() == parts[1].lower():
        parts = parts[:1]
    return clean_display(", ".join(parts))


def _label(props: dict) -> str:
    head, area = _street_line(props), _area_line(props)
    # Evita "Trujillo · Trujillo" cuando el lugar se llama igual que su zona.
    if head and area and head.lower() not in area.lower():
        return f"{head} · {area}"
    return head or area or ""


def _feature_to_place(feature: dict) -> Place | None:
    props = feature.get("properties", {})
    if props.get("countrycode") and props["countrycode"].upper() != COUNTRY:
        return None
    coords = feature.get("geometry", {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    label = _label(props)
    if not label:
        return None
    return Place(label=label, lat=float(coords[1]), lon=float(coords[0]))


def search_places(query: str, near: tuple[float, float] | None = None,
                  limit: int = 5) -> list[Place]:
    """Busca direcciones, cruces o referencias. Lista vacia si no hay red."""
    query = (query or "").strip()
    if len(query) < 3:
        return []

    params: dict[str, object] = {"q": query, "limit": limit * 2, "lang": "default"}
    if near:
        params["lat"], params["lon"] = near[0], near[1]

    try:
        response = requests.get(PHOTON_SEARCH, params=params,
                                headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        features = response.json().get("features", [])
    except (requests.RequestException, ValueError):
        return []

    places: list[Place] = []
    seen: set[str] = set()
    for feature in features:
        place = _feature_to_place(feature)
        if place and place.label not in seen:
            seen.add(place.label)
            places.append(place)
        if len(places) >= limit:
            break
    return places


def reverse_place(lat: float, lon: float) -> str:
    """Direccion legible de un punto. Cadena vacia si no se pudo resolver."""
    try:
        response = requests.get(
            PHOTON_REVERSE, params={"lat": lat, "lon": lon, "lang": "default"},
            headers=HEADERS, timeout=TIMEOUT,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
    except (requests.RequestException, ValueError):
        return ""
    if not features:
        return ""
    return _label(features[0].get("properties", {}))
