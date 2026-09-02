"""GasolinApp - en que grifo te conviene cargar combustible cerca de ti."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from utils.constants import (
    ABOUT_TEXT,
    APP_NAME,
    AUTHOR_LINKEDIN,
    AUTHOR_NAME,
    BRAND_LABELS,
    CACHE_TTL_SECONDS,
    DEFAULT_FUEL,
    DEFAULT_LOCATION,
    DEFAULT_RADIUS_KM,
    EVPC_SOURCE_PAGE,
    FUEL_FAMILIES,
    RADIUS_OPTIONS_KM,
    TANK_GALLONS,
    TOP_NO_DISCOUNT,
    TOP_OTHERS,
    TOP_WITH_DISCOUNT,
)
from utils.data_loader import build_dataset
from utils.geo import (
    get_browser_location,
    load_district_centroids,
    resolve_admin_from_point,
    search_locations,
)
from utils.ranking import rank_stations, split_results
from utils.savings import compute_savings
from utils.ui import CARD_CSS, render_card

st.set_page_config(
    page_title=APP_NAME,
    page_icon="⛽",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(CARD_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Datos (una sola construccion por dia, compartida por todas las sesiones)
# --------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_data():
    return build_dataset()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_centroids():
    return load_district_centroids()


# --------------------------------------------------------------------------
# Estado
# --------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "fuel": DEFAULT_FUEL,
        "radius": DEFAULT_RADIUS_KM,
        "use_repsol": False,
        "use_primax": False,
        "location": None,       # dict lat/lon/label o None
        "geo_requested": False, # el usuario pidio ubicacion del navegador
        "manual_query": "",
        "show_manual": True,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def active_brands() -> set[str]:
    brands = set()
    if st.session_state["use_repsol"]:
        brands.add("REPSOL")
    if st.session_state["use_primax"]:
        brands.add("PRIMAX")
    return brands


def current_location() -> dict:
    return st.session_state["location"] or {
        **DEFAULT_LOCATION,
        "is_default": True,
    }


# --------------------------------------------------------------------------
# Bloques de interfaz
# --------------------------------------------------------------------------
def render_header(meta) -> None:
    st.markdown(
        f"<div class='ga-head'><h1>⛽ {APP_NAME}</h1>"
        "<p>El grifo que mas te conviene cerca de ti.</p></div>",
        unsafe_allow_html=True,
    )
    if meta.stale:
        st.warning(
            "No se pudo actualizar hoy con Osinergmin. Estas viendo la ultima "
            "informacion disponible.",
            icon="⚠️",
        )


def render_location_controls() -> None:
    """Ubicacion real del navegador, con busqueda manual como alternativa."""
    location = current_location()
    is_default = location.get("is_default", False)

    label = location.get("label") or f"{location['lat']:.4f}, {location['lon']:.4f}"
    state = "ga-loc-default" if is_default else "ga-loc-ok"
    icon = "📍" if not is_default else "🧭"
    st.markdown(
        f"<div class='ga-loc {state}'>{icon} <span>{label}</span></div>",
        unsafe_allow_html=True,
    )

    col_gps, col_manual = st.columns([1, 1])
    with col_gps:
        if st.button("📍 Usar mi ubicacion", use_container_width=True):
            st.session_state["geo_requested"] = True
            st.rerun()
    with col_manual:
        # Con key propia para que el toggle no se reinicie en cada rerun.
        st.session_state.setdefault("show_manual", is_default)
        show_manual = st.toggle("Buscar zona", key="show_manual")

    if st.session_state["geo_requested"]:
        position = get_browser_location()
        if position:
            st.session_state["location"] = {
                "lat": position["lat"],
                "lon": position["lon"],
                "label": "Tu ubicacion actual",
            }
            st.session_state["geo_requested"] = False
            st.rerun()
        else:
            st.caption(
                "Esperando permiso de ubicacion en el navegador. "
                "Si lo rechazaste, usa la busqueda por zona."
            )

    if show_manual:
        render_manual_search()


def render_manual_search() -> None:
    query = st.text_input(
        "Distrito, provincia o referencia",
        key="manual_query",
        placeholder="Ej. Miraflores, Trujillo, Surco...",
        label_visibility="collapsed",
    )
    if not query or len(query.strip()) < 3:
        return

    hits = search_locations(query, load_centroids())
    if hits.empty:
        st.caption("Sin coincidencias. Prueba con el nombre del distrito.")
        return

    choice = st.selectbox(
        "Elige tu zona", hits["label"].tolist(), label_visibility="collapsed",
    )
    if st.button("Usar esta zona", use_container_width=True):
        row = hits[hits["label"] == choice].iloc[0]
        st.session_state["location"] = {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "label": choice.title(),
        }
        st.rerun()


def render_filters() -> None:
    fuels = list(FUEL_FAMILIES.keys())
    st.radio(
        "Combustible", fuels, key="fuel", horizontal=True,
    )
    st.select_slider(
        "Radio de busqueda", options=RADIUS_OPTIONS_KM, key="radius",
        format_func=lambda km: f"{km} km",
    )
    col_repsol, col_primax = st.columns(2)
    with col_repsol:
        st.checkbox("Descuento Repsol", key="use_repsol")
    with col_primax:
        st.checkbox("Descuento Primax", key="use_primax")


def render_savings(dataset, visible, best_row, fuel, admin) -> None:
    savings = compute_savings(dataset, visible, best_row, fuel, admin)
    if savings is None or not savings.is_positive:
        return
    st.markdown(
        f"<div class='ga-savings'>Podrias ahorrar "
        f"<strong>S/ {savings.amount:,.2f}</strong> por tanque lleno "
        f"({TANK_GALLONS} gal) frente al promedio de {savings.scope_label}.</div>",
        unsafe_allow_html=True,
    )


def render_results(ranked: pd.DataFrame, brands: set[str]) -> None:
    if brands:
        with_discount, others = split_results(ranked, TOP_WITH_DISCOUNT, TOP_OTHERS)

        if not with_discount.empty:
            st.markdown("<h3 class='ga-h3'>Con tu descuento</h3>", unsafe_allow_html=True)
            for _, row in with_discount.iterrows():
                render_card(row)
        else:
            names = " y ".join(BRAND_LABELS[b] for b in sorted(brands))
            st.info(f"No hay grifos {names} con descuento en este radio.", icon="ℹ️")

        if not others.empty:
            st.markdown("<h3 class='ga-h3'>Otros grifos cerca</h3>", unsafe_allow_html=True)
            for _, row in others.iterrows():
                render_card(row)
    else:
        st.markdown("<h3 class='ga-h3'>Mejores grifos cerca</h3>", unsafe_allow_html=True)
        for _, row in ranked.head(TOP_NO_DISCOUNT).iterrows():
            render_card(row, show_badge=False)


def render_map(ranked: pd.DataFrame, location: dict, limit: int) -> None:
    points = ranked.head(limit)[["lat", "lon"]].copy()
    points["size"] = 60
    user = pd.DataFrame([{"lat": location["lat"], "lon": location["lon"], "size": 110}])
    with st.expander("Ver en el mapa", expanded=False):
        st.map(pd.concat([points, user], ignore_index=True), size="size", zoom=12)


def render_footer(meta) -> None:
    published = meta.published_at or meta.last_price_at
    stamp = (
        published.astimezone().strftime("%d/%m/%Y %H:%M")
        if isinstance(published, dt.datetime) else "fecha no disponible"
    )
    st.markdown(
        f"""
        <div class='ga-footer'>
          <p>Datos de <a href="{EVPC_SOURCE_PAGE}" target="_blank">Osinergmin (EVPC)</a>
             cargados el <strong>{stamp}</strong> · {meta.stations:,} grifos.</p>
          <p>{ABOUT_TEXT}</p>
          <p>Hecho por <a href="{AUTHOR_LINKEDIN}" target="_blank">{AUTHOR_NAME}</a> 💼</p>
          <p class='ga-disclaimer'>Precios referenciales reportados por cada grifo.
             Los descuentos dependen de las condiciones vigentes de cada marca.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Aplicacion
# --------------------------------------------------------------------------
def main() -> None:
    init_state()

    try:
        dataset, meta = load_data()
    except RuntimeError as error:
        st.error(f"No se pudo cargar la informacion de precios. {error}")
        st.stop()

    render_header(meta)
    render_location_controls()
    render_filters()

    location = current_location()
    fuel = st.session_state["fuel"]
    brands = active_brands()

    fuel_data = dataset[dataset["fuel"] == fuel]
    ranked = rank_stations(
        fuel_data, location["lat"], location["lon"], st.session_state["radius"], brands,
    )

    if ranked.empty:
        st.warning(
            f"No encontramos grifos con {fuel} a menos de "
            f"{st.session_state['radius']} km. Prueba ampliando el radio.",
            icon="🔍",
        )
        render_footer(meta)
        return

    admin = resolve_admin_from_point(location["lat"], location["lon"], load_centroids())
    render_savings(fuel_data, ranked, ranked.iloc[0], fuel, admin)
    render_results(ranked, brands)
    render_map(ranked, location, TOP_WITH_DISCOUNT + TOP_OTHERS)
    render_footer(meta)


if __name__ == "__main__":
    main()
