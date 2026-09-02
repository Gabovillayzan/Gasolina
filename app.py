"""GasolinApp - en que grifo te conviene cargar combustible cerca de ti."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from utils.constants import (
    ABOUT_TEXT,
    APP_ICON,
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
    MAP_MAX_PINS,
    RADIUS_OPTIONS_KM,
    TANK_GALLONS,
    TOP_NO_DISCOUNT,
    TOP_OTHERS,
    TOP_WITH_DISCOUNT,
)
from utils.data_loader import build_dataset
from utils.geo import (
    load_district_centroids,
    request_browser_location,
    resolve_admin_from_point,
    search_locations,
)
from utils.mapview import build_deck
from utils.ranking import rank_stations, split_results
from utils.savings import compute_savings
from utils.ui import CSS, ICON_LOGO, ICON_PIN, render_card, render_hero, station_title

st.set_page_config(
    page_title=APP_NAME,
    page_icon=str(APP_ICON) if APP_ICON.exists() else "⛽",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Datos (una construccion por dia, compartida por todas las sesiones)
# --------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_data():
    return build_dataset()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_centroids():
    return load_district_centroids()


@st.cache_data(ttl=600, show_spinner=False)
def compute_results(dataset, fuel, lat, lon, radius, brands):
    """Ranking cacheado por combinacion de filtros: no recalcula al repintar."""
    fuel_data = dataset[dataset["fuel"] == fuel]
    return fuel_data, rank_stations(fuel_data, lat, lon, radius, set(brands))


# --------------------------------------------------------------------------
# Estado
# --------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "use_repsol": False,
        "use_primax": False,
        "location": None,   # dict lat/lon/label, o None mientras no haya
        "geo_attempt": 0,   # sube al reintentar; fuerza un componente nuevo
        "geo_status": "",   # denied | unavailable | unsupported
        "manual_query": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def active_brands() -> tuple[str, ...]:
    brands = []
    if st.session_state["use_repsol"]:
        brands.append("REPSOL")
    if st.session_state["use_primax"]:
        brands.append("PRIMAX")
    return tuple(brands)


def current_location() -> dict:
    return st.session_state["location"] or {**DEFAULT_LOCATION, "is_default": True}


def theme_mode() -> str:
    """Modo activo del dispositivo, para pintar el mapa a juego."""
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


# --------------------------------------------------------------------------
# Ubicacion
# --------------------------------------------------------------------------
def resolve_location() -> None:
    """Pide la ubicacion al navegador en el primer render.

    Se monta antes de dibujar nada pesado para que el permiso salga de
    inmediato y el GPS corra en paralelo con la carga de datos.
    """
    if st.session_state["location"] is not None:
        return
    if st.session_state["geo_status"] in ("denied", "unsupported"):
        return

    result = request_browser_location(st.session_state["geo_attempt"])
    if result is None:
        return  # el navegador aun no responde
    if "error" in result:
        st.session_state["geo_status"] = result["error"]
        return
    st.session_state["location"] = {
        "lat": result["lat"], "lon": result["lon"], "label": "Tu ubicación actual",
    }
    st.session_state["geo_status"] = ""


def render_location_bar() -> None:
    location = current_location()
    is_default = location.get("is_default", False)
    label = location.get("label") or f"{location['lat']:.4f}, {location['lon']:.4f}"
    state = "ga-loc-default" if is_default else ""
    st.markdown(
        f'<div class="ga-loc {state}">{ICON_PIN}<span>{label}</span></div>',
        unsafe_allow_html=True,
    )

    status = st.session_state["geo_status"]
    if status == "denied":
        st.caption("Bloqueaste la ubicación. Elige tu zona abajo, o actívala y reintenta.")
    elif status == "unavailable":
        st.caption("No pudimos leer el GPS. Reintenta o elige tu zona abajo.")
    elif is_default and not status:
        st.caption("Buscando tu ubicación…")


def render_location_controls() -> None:
    """Reintento de GPS y busqueda manual, fuera del camino principal."""
    if st.button("Actualizar ubicación", use_container_width=True):
        st.session_state["geo_attempt"] += 1
        st.session_state["geo_status"] = ""
        st.session_state["location"] = None
        st.rerun()

    query = st.text_input(
        "Buscar zona",
        key="manual_query",
        placeholder="Miraflores, Trujillo, Surco…",
        label_visibility="collapsed",
    )
    if not query or len(query.strip()) < 3:
        return

    hits = search_locations(query, load_centroids())
    if hits.empty:
        st.caption("Sin coincidencias. Prueba con el nombre del distrito.")
        return

    choice = st.selectbox("Elige tu zona", hits["label"].tolist(), label_visibility="collapsed")
    if st.button("Usar esta zona", use_container_width=True):
        row = hits[hits["label"] == choice].iloc[0]
        st.session_state["location"] = {
            "lat": float(row["lat"]), "lon": float(row["lon"]), "label": choice.title(),
        }
        st.session_state["geo_status"] = ""
        st.rerun()


# --------------------------------------------------------------------------
# Filtros y resultados
# --------------------------------------------------------------------------
def render_filters() -> tuple[str, int, tuple[str, ...]]:
    """Dibuja los filtros y devuelve la seleccion vigente.

    `required=True` impide quedarse sin combustible o sin radio: deseleccionar
    no significa nada aqui y dejaria la pantalla vacia.
    """
    fuel = st.segmented_control(
        "Combustible", list(FUEL_FAMILIES), key="fuel",
        default=DEFAULT_FUEL, required=True,
        selection_mode="single", width="stretch",
    )
    radius = st.segmented_control(
        "Radio", RADIUS_OPTIONS_KM, key="radius",
        default=DEFAULT_RADIUS_KM, required=True,
        selection_mode="single", width="stretch",
        format_func=lambda km: f"{km} km",
    )
    col_repsol, col_primax = st.columns(2)
    with col_repsol:
        st.checkbox("Descuento Repsol", key="use_repsol")
    with col_primax:
        st.checkbox("Descuento Primax", key="use_primax")
    return fuel or DEFAULT_FUEL, radius or DEFAULT_RADIUS_KM, active_brands()


def savings_text(fuel_data, ranked, best_row, fuel, admin) -> str:
    savings = compute_savings(fuel_data, ranked, best_row, fuel, admin)
    if savings is None or not savings.is_positive:
        return ""
    return (
        f"Ahorras S/ {savings.amount:,.2f} por tanque lleno "
        f"({TANK_GALLONS} gal) frente al promedio de {savings.scope_label}."
    )


def numbered(frame: pd.DataFrame, start: int) -> pd.DataFrame:
    """Asigna a cada fila el numero que compartiran tarjeta y mapa."""
    out = frame.copy()
    out["rank"] = range(start, start + len(out))
    out["label"] = out.apply(station_title, axis=1)
    return out


def render_results(ranked: pd.DataFrame, brands: tuple[str, ...]) -> pd.DataFrame:
    """Dibuja los bloques y devuelve lo que va al mapa, ya numerado.

    La primera fila no se repite como tarjeta: ya esta arriba como mejor opcion.
    """
    if brands:
        with_discount, others = split_results(ranked, TOP_WITH_DISCOUNT, TOP_OTHERS)
        with_discount = numbered(with_discount, 1)
        others = numbered(others, len(with_discount) + 1)

        if not with_discount.empty:
            st.markdown('<p class="ga-h3">Con tu descuento</p>', unsafe_allow_html=True)
            for _, row in with_discount.iloc[1:].iterrows():
                render_card(row, int(row["rank"]))
        else:
            names = " y ".join(BRAND_LABELS[b] for b in sorted(brands))
            st.info(f"No hay grifos {names} con descuento en este radio.")

        if not others.empty:
            st.markdown('<p class="ga-h3">Otros grifos cerca</p>', unsafe_allow_html=True)
            for _, row in others.iterrows():
                render_card(row, int(row["rank"]))
        return pd.concat([with_discount, others], ignore_index=True)

    shown = numbered(ranked.head(TOP_NO_DISCOUNT), 1)
    st.markdown('<p class="ga-h3">Mejores grifos cerca</p>', unsafe_allow_html=True)
    for _, row in shown.iloc[1:].iterrows():
        render_card(row, int(row["rank"]), show_badge=False)
    return shown


@st.fragment
def results_fragment(dataset, location, admin) -> None:
    """Filtros, resultados y mapa aislados en un fragmento.

    Tocar un filtro solo reejecuta este bloque: no recarga el dataset ni vuelve
    a resolver la ubicacion.
    """
    fuel, radius, brands = render_filters()

    fuel_data, ranked = compute_results(
        dataset, fuel, location["lat"], location["lon"], radius, brands,
    )
    if ranked.empty:
        st.warning(
            f"No encontramos estaciones con {fuel} a menos de {radius} km. "
            "Amplía el radio para ver más opciones."
        )
        return

    best = ranked.iloc[0]
    render_hero(best, savings_text(fuel_data, ranked, best, fuel, admin))
    shown = render_results(ranked, brands)

    with st.expander("Ver en el mapa"):
        st.pydeck_chart(
            build_deck(shown.head(MAP_MAX_PINS), location, radius, theme_mode()),
            use_container_width=True,
        )
        st.caption("El punto azul eres tú. Cada número es el mismo de su tarjeta.")


def render_footer(meta) -> None:
    published = meta.published_at or meta.last_price_at
    stamp = (
        published.astimezone().strftime("%d/%m/%Y %H:%M")
        if isinstance(published, dt.datetime) else "fecha no disponible"
    )
    st.markdown(
        f'<div class="ga-footer">'
        f'<p>Datos de <a href="{EVPC_SOURCE_PAGE}" target="_blank">Osinergmin (EVPC)</a> '
        f'del <strong>{stamp}</strong> · {meta.stations:,} grifos.</p>'
        f'<p>{ABOUT_TEXT}</p>'
        f'<p>Hecho por <a href="{AUTHOR_LINKEDIN}" target="_blank">{AUTHOR_NAME}</a></p>'
        f'<p class="ga-disclaimer">Precios referenciales reportados por cada grifo. '
        f'Los descuentos dependen de las condiciones vigentes de cada marca.</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
def main() -> None:
    init_state()
    # Lo primero: el permiso de ubicacion corre mientras el dataset carga.
    resolve_location()

    st.markdown(
        f'<div class="ga-head">{ICON_LOGO}<h1>{APP_NAME}</h1></div>'
        f'<p class="ga-sub">El grifo que más te conviene cerca de ti.</p>',
        unsafe_allow_html=True,
    )

    try:
        dataset, meta = load_data()
    except RuntimeError as error:
        st.error(f"No se pudo cargar la información de precios. {error}")
        st.stop()

    if meta.stale:
        st.warning(
            "No pudimos actualizar hoy con Osinergmin. "
            "Ves la última información disponible."
        )

    render_location_bar()
    location = current_location()
    admin = resolve_admin_from_point(location["lat"], location["lon"], load_centroids())

    results_fragment(dataset, location, admin)

    with st.expander("Cambiar ubicación"):
        render_location_controls()
        st.caption(
            "Las estaciones sin coordenada exacta se ubican en el centro de su "
            "distrito y aparecen marcadas como aproximadas."
        )

    render_footer(meta)


if __name__ == "__main__":
    main()
