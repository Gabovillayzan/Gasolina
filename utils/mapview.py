"""Mapa de resultados con pydeck.

`st.map` no permite marcadores distintos ni etiquetas, asi que se usa pydeck
(ya viene con Streamlit, sin dependencia nueva) con tres capas:

    1. grifos            -> cuadrado ambar
    2. numero del grifo  -> el mismo que lleva la tarjeta
    3. tu ubicacion      -> punto azul con halo, la convencion habitual

Las estaciones sin coordenada exacta comparten el centroide de su distrito. Si
se dibujaran tal cual, varios numeros caerian encima. `_fan_out` las separa en
abanico de forma determinista, con un radio de unos 25 m, para que se lean sin
falsear la posicion mas alla de la precision que ya tienen.
"""
from __future__ import annotations

import math

import pandas as pd
import pydeck as pdk

from utils.constants import MAP_JITTER_DEG, THEME

USER_COLOR = [44, 127, 245]
HALO_COLOR = [44, 127, 245, 60]


def _hex_to_rgb(value: str) -> list[int]:
    value = value.lstrip("#")
    return [int(value[i : i + 2], 16) for i in (0, 2, 4)]


def _fan_out(points: pd.DataFrame) -> pd.DataFrame:
    """Separa en abanico los puntos que comparten exactamente la coordenada."""
    out = points.copy()
    grouped = out.groupby(["lat", "lon"]).cumcount()
    sizes = out.groupby(["lat", "lon"])["lat"].transform("size")

    angles = (grouped / sizes.clip(lower=1)) * 2 * math.pi
    spread = (sizes > 1).astype(float) * MAP_JITTER_DEG
    # La correccion por coseno evita que el abanico se aplaste cerca del ecuador.
    out["lat"] = out["lat"] + spread * angles.map(math.sin)
    cos_lat = out["lat"].map(lambda v: max(math.cos(math.radians(v)), 0.2))
    out["lon"] = out["lon"] + spread * angles.map(math.cos) / cos_lat
    return out


def _zoom_for(radius_km: float) -> float:
    return {5: 12.4, 10: 11.5, 20: 10.5}.get(int(radius_km), 12.0)


def build_deck(results: pd.DataFrame, location: dict, radius_km: float,
               mode: str = "light") -> pdk.Deck:
    """Arma el mapa con los resultados ya rankeados y numerados."""
    palette = THEME.get(mode, THEME["light"])
    accent = _hex_to_rgb(palette["accent"])
    # El numero va sobre el ambar, asi que su contraste lo fija on_accent,
    # no el color de texto general del tema.
    label_ink = _hex_to_rgb(palette["on_accent"])

    points = results[["lat", "lon", "rank", "label"]].copy()
    points = _fan_out(points)
    # TextLayer no dibuja enteros: necesita el numero ya como cadena.
    points["rank_text"] = points["rank"].astype(str)

    user = pd.DataFrame([{"lat": location["lat"], "lon": location["lon"]}])

    layers = [
        # Halo de la posicion del usuario.
        pdk.Layer(
            "ScatterplotLayer", data=user,
            get_position="[lon, lat]", get_fill_color=HALO_COLOR,
            get_radius=220, radius_min_pixels=14, radius_max_pixels=40, pickable=False,
        ),
        pdk.Layer(
            "ScatterplotLayer", data=user,
            get_position="[lon, lat]", get_fill_color=USER_COLOR,
            get_line_color=[255, 255, 255], line_width_min_pixels=2, stroked=True,
            get_radius=70, radius_min_pixels=6, radius_max_pixels=11, pickable=False,
        ),
        # Grifos: cuadrado, coherente con el lenguaje de la interfaz.
        pdk.Layer(
            "ScatterplotLayer", data=points,
            get_position="[lon, lat]", get_fill_color=[*accent, 235],
            get_line_color=[255, 255, 255], line_width_min_pixels=2, stroked=True,
            get_radius=130, radius_min_pixels=11, radius_max_pixels=18,
            pickable=True,
        ),
        # Ojo: pydeck convierte los valores de texto en accesores de datos
        # ("@@=Inter, sans-serif"), lo que rompe la capa. Por eso aqui solo van
        # constantes no textuales, y los literales se citan dos veces.
        pdk.Layer(
            "TextLayer", data=points,
            get_position="[lon, lat]", get_text="rank_text",
            get_size=15, get_color=[*label_ink, 255],
            get_text_anchor="'middle'", get_alignment_baseline="'center'",
            pickable=False,
        ),
    ]

    view = pdk.ViewState(
        latitude=location["lat"], longitude=location["lon"],
        zoom=_zoom_for(radius_km), pitch=0, bearing=0,
    )
    return pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style="dark" if mode == "dark" else "road",
        tooltip={"text": "{rank}. {label}"},
    )
