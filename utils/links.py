"""Deep links de navegacion por coordenadas."""
from __future__ import annotations

from urllib.parse import quote_plus


def google_maps_url(lat: float, lon: float, label: str = "") -> str:
    if label:
        return (
            "https://www.google.com/maps/search/?api=1"
            f"&query={lat},{lon}&query_place_id=&z=17#{quote_plus(label)}"
        )
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def waze_url(lat: float, lon: float) -> str:
    return f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"
