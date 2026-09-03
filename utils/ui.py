"""Capa visual: tema Ruta, iconos y tarjetas. Mantiene el HTML fuera de app.py.

El tema vive en variables CSS y cambia solo con `prefers-color-scheme`, asi que
seguir al dispositivo no cuesta ningun rerun. `[theme]` y `[theme.dark]` del
config.toml pintan los widgets nativos con los mismos valores.

El acento ambar es de senalizacion vial y se usa solo para accion, seleccion y
estado. El lenguaje es algo brutalista: aristas de 3 px, bordes de 2 px, sombra
solida sin difuminar y numeracion en bloque.
"""
from __future__ import annotations

import html

import pandas as pd

from utils.constants import BRAND_LABELS, FONT_CSS_URL, THEME
from utils.links import google_maps_url, waze_url


def _vars(mode: str) -> str:
    t = THEME[mode]
    return "".join(f"--{k.replace('_','-')}:{v};" for k, v in t.items())


CSS = f"""
<style>
  @import url('{FONT_CSS_URL}');

  :root {{ {_vars("light")} }}
  @media (prefers-color-scheme: dark) {{ :root {{ {_vars("dark")} }} }}

  :root {{
    --radius: 3px;
    --border: 2px solid var(--line);
    --hard: 3px 3px 0 var(--line);
  }}

  /* Quitar cromo de Streamlit */
  #MainMenu, footer, header {{ display: none; }}
  .stDeployButton, .stAppHeader {{ display: none; }}

  /* Dos elementos invisibles abrian ~58 px muertos arriba: el bloque que solo
     contiene este <style>, y el iframe del componente de geolocalizacion.
     Cada uno sumaba ademas un gap de 16 px del bloque vertical. */
  [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) {{
    display: none;
  }}
  /* El iframe se saca del flujo en vez de ocultarlo: tiene que seguir
     ejecutandose para poder leer el GPS. */
  [data-testid="stElementContainer"]:has(iframe[title^="streamlit_js_eval"]) {{
    position: absolute; width: 1px; height: 1px;
    overflow: hidden; opacity: 0; pointer-events: none;
  }}

  .stApp {{ background: var(--canvas); }}
  .block-container {{ padding: .8rem .85rem 3rem; max-width: 660px; }}
  html, body, [class*="css"] {{
    color: var(--ink);
    font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  }}

  /* ---------- Cabecera ---------- */
  .ga-head {{ display:flex; align-items:center; gap:.55rem; margin-bottom:.15rem; }}
  .ga-head svg {{ width:26px; height:26px; flex:none; }}
  .ga-head h1 {{
    font-size:1.5rem; font-weight:800; letter-spacing:-.035em; margin:0; line-height:1;
  }}
  .ga-sub {{
    color:var(--ink-2); font-size:.85rem; margin:.15rem 0 .85rem;
  }}

  /* ---------- Ubicacion ---------- */
  /* La caja de busqueda ES el indicador de ubicacion: su placeholder muestra
     donde estas, y escribir encima la cambia. Un solo control, arriba. */
  [data-testid="stTextInput"] input {{
    min-height:44px; font-weight:600; font-size:.88rem;
    border-radius:var(--radius) !important;
  }}
  [data-testid="stTextInput"] input::placeholder {{
    color:var(--ink); opacity:.72; font-weight:600;
  }}
  .ga-locnote {{
    display:flex; align-items:center; gap:.35rem;
    font-size:.75rem; color:var(--ink-2); margin:-.15rem 0 .5rem .1rem;
  }}
  .ga-locnote svg {{ width:12px; height:12px; flex:none; color:var(--accent); }}

  /* Sugerencias de direccion: full width, un toque */
  .ga-sugg {{ margin-bottom:.5rem; }}
  .ga-sugg .stButton button {{
    justify-content:flex-start; text-align:left; font-weight:600;
    font-size:.83rem; min-height:42px;
  }}

  /* Aviso accionable (GPS apagado, permiso denegado) */
  .ga-alert {{
    border:var(--border); border-left:3px solid var(--accent);
    background:var(--surface); border-radius:var(--radius);
    padding:.6rem .7rem; margin-bottom:.5rem; font-size:.81rem;
    color:var(--ink); line-height:1.45;
  }}
  .ga-alert b {{ display:block; margin-bottom:.15rem; font-weight:800; }}
  .ga-alert span {{ color:var(--ink-2); }}

  /* ---------- Titulos de bloque ---------- */
  .ga-h3 {{
    font-size:.72rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase;
    color:var(--ink-2); margin:1.25rem 0 .5rem;
    border-bottom:var(--border); padding-bottom:.32rem;
  }}

  /* ---------- Mejor opcion ---------- */
  .ga-hero {{
    background:var(--surface); border:2px solid var(--accent);
    border-radius:var(--radius); padding:.9rem .95rem; margin-bottom:.7rem;
    box-shadow:3px 3px 0 var(--accent);
  }}
  .ga-hero-tag {{
    display:inline-block; font-size:.63rem; font-weight:800; letter-spacing:.13em;
    text-transform:uppercase; background:var(--accent); color:var(--on-accent);
    padding:.2rem .45rem; border-radius:2px; margin-bottom:.5rem;
  }}
  .ga-hero-name {{ font-size:1.08rem; font-weight:800; letter-spacing:-.02em; margin:0 0 .15rem; }}
  .ga-hero-price {{
    font-size:2.15rem; font-weight:800; letter-spacing:-.045em; line-height:1;
    font-variant-numeric:tabular-nums; margin:.45rem 0 .1rem;
  }}
  .ga-hero-unit {{
    font-size:.63rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase;
    color:var(--ink-2);
  }}
  .ga-save {{
    background:var(--ok-bg); border-left:3px solid var(--ok); color:var(--ok);
    padding:.5rem .6rem; margin-top:.6rem; font-size:.82rem; font-weight:600;
    border-radius:0 var(--radius) var(--radius) 0;
  }}

  /* ---------- Tarjetas ---------- */
  .ga-card {{
    background:var(--surface); border:var(--border); border-radius:var(--radius);
    padding:.7rem .75rem; margin-bottom:.5rem;
  }}
  .ga-card-top {{ display:flex; gap:.6rem; align-items:flex-start; }}
  .ga-rank {{
    flex:none; width:23px; height:23px; border-radius:2px;
    display:grid; place-items:center; margin-top:1px;
    background:var(--accent); color:var(--on-accent);
    font-size:.78rem; font-weight:800; font-variant-numeric:tabular-nums;
  }}
  .ga-body {{ min-width:0; flex:1; }}
  .ga-name {{ font-weight:700; font-size:.93rem; line-height:1.25; margin:0 0 .12rem; }}
  .ga-addr {{ color:var(--ink-2); font-size:.77rem; line-height:1.3; margin:0; }}
  .ga-meta {{ display:flex; align-items:center; gap:.32rem; flex-wrap:wrap; margin-top:.35rem; }}
  .ga-chip {{
    font-size:.72rem; font-weight:700; border-radius:2px; padding:.1rem .35rem;
    background:var(--chip); color:var(--chip-ink); font-variant-numeric:tabular-nums;
  }}
  .ga-badge {{
    font-size:.68rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase;
    border-radius:2px; padding:.1rem .35rem; background:var(--ok-bg); color:var(--ok);
  }}
  .ga-approx {{ font-size:.7rem; color:var(--ink-2); }}
  .ga-price {{ text-align:right; white-space:nowrap; margin-left:auto; }}
  .ga-price b {{
    display:block; font-size:1.28rem; font-weight:800; letter-spacing:-.035em;
    line-height:1.05; font-variant-numeric:tabular-nums;
  }}
  .ga-price span {{
    display:block; font-size:.6rem; font-weight:800; letter-spacing:.12em;
    text-transform:uppercase; color:var(--ink-2); margin-top:.15rem;
  }}

  /* ---------- Acciones ---------- */
  .ga-actions {{ display:flex; gap:.4rem; margin-top:.55rem; }}
  .ga-actions a {{
    flex:1; display:flex; align-items:center; justify-content:center; gap:.3rem;
    min-height:38px; text-decoration:none; border-radius:var(--radius);
    font-size:.79rem; font-weight:700; border:var(--border);
    color:var(--ink); background:var(--canvas);
    transition:border-color .15s, color .15s;
  }}
  .ga-actions a:hover {{ border-color:var(--accent); color:var(--accent); }}
  .ga-actions svg {{ width:13px; height:13px; }}

  /* ---------- Pie ---------- */
  .ga-footer {{
    margin-top:2rem; padding-top:.9rem; border-top:var(--border);
    color:var(--ink-2); font-size:.75rem; line-height:1.55;
  }}
  .ga-footer p {{ margin:0 0 .3rem; }}
  .ga-footer a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
  .ga-disclaimer {{ font-size:.7rem; opacity:.85; }}

  /* ---------- Controles nativos, mas tactiles ---------- */
  .stButton button {{ font-weight:700; font-size:.85rem; min-height:42px; }}

  /* Streamlit pinta el segmento activo con el acento al 10%: se lee lavado.
     Aqui va solido, que es lo que hace obvio cual esta elegido en el movil. */
  [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {{
    min-height:44px; font-weight:700; font-size:.87rem;
  }}
  [data-testid="stButtonGroup"] button[data-selected="true"] {{
    background:var(--accent) !important;
    color:var(--on-accent) !important;
    border-color:var(--accent) !important;
  }}
  @media (max-width:480px) {{
    .block-container {{ padding:.7rem .6rem 2.5rem; }}
  }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>
"""

# --- Iconos: trazo grueso, remates rectos, sin curvas suaves ---------------
ICON_LOGO = (
    '<svg viewBox="0 0 64 64" fill="none" aria-hidden="true">'
    '<rect width="64" height="64" fill="var(--accent)"/>'
    '<path d="M32 5 52 33v12l-8 10H20l-8-10V33Z" fill="var(--on-accent)"/>'
    '<rect x="19" y="41" width="26" height="6" fill="var(--accent)"/></svg>'
)
ICON_PIN = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
    'stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">'
    '<path d="M12 2 20 11v5l-4 6H8l-4-6v-5Z"/><path d="M9 12h6"/></svg>'
)
ICON_MAPS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
    'stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">'
    '<path d="M3 6 9 3l6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/></svg>'
)
ICON_WAZE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
    'stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">'
    '<path d="M3 12 21 4l-8 18-2-8Z"/></svg>'
)


def station_title(row: pd.Series) -> str:
    """Marca si es Repsol o Primax; si no, la razon social."""
    brand = row.get("discount_brand") or row.get("brand_razon")
    if brand in BRAND_LABELS:
        district = row.get("distrito") or ""
        return f"{BRAND_LABELS[brand]} {district}".strip()
    return row.get("razon_display") or "Grifo"


def short_address(address: str, limit: int = 62) -> str:
    """Direccion resumida: corta en el primer separador util."""
    text = (address or "").strip()
    for sep in (" ESQUINA", " ESQ.", ", ESQ", " (", " MZ", " URB."):
        index = text.find(sep)
        if 18 < index < limit:
            text = text[:index]
            break
    if len(text) > limit:
        text = text[: limit - 1].rstrip(" ,.-") + "…"
    return text


def _actions(lat: float, lon: float) -> str:
    return (
        '<div class="ga-actions">'
        f'<a href="{google_maps_url(lat, lon)}" target="_blank" rel="noopener">'
        f'{ICON_MAPS}Google Maps</a>'
        f'<a href="{waze_url(lat, lon)}" target="_blank" rel="noopener">'
        f'{ICON_WAZE}Waze</a></div>'
    )


def render_hero(row: pd.Series, savings_text: str = "") -> None:
    """Respuesta directa a la pregunta de la app: la mejor opcion cerca."""
    import streamlit as st

    name = html.escape(station_title(row))
    address = html.escape(short_address(row.get("direccion_display", "")))
    district = html.escape(str(row.get("distrito") or ""))
    badge = (
        '<span class="ga-badge">Con descuento</span>'
        if bool(row.get("tiene_descuento")) else ""
    )
    approx = (
        '<span class="ga-approx">Ubicación aproximada</span>'
        if row.get("coord_source") != "exacta" else ""
    )
    save = f'<div class="ga-save">{html.escape(savings_text)}</div>' if savings_text else ""

    st.markdown(
        f'<div class="ga-hero">'
        f'<span class="ga-hero-tag">Mejor opción cerca de ti</span>'
        f'<p class="ga-hero-name">{name}</p>'
        f'<p class="ga-addr">{address}{" · " + district if district else ""}</p>'
        f'<div class="ga-hero-price">S/ {float(row["precio_final"]):.2f}</div>'
        f'<div class="ga-hero-unit">por galón</div>'
        f'<div class="ga-meta"><span class="ga-chip">{float(row["distancia_km"]):.1f} km</span>'
        f'{badge}{approx}</div>'
        f'{_actions(float(row["lat"]), float(row["lon"]))}'
        f'{save}</div>',
        unsafe_allow_html=True,
    )


def render_card(row: pd.Series, rank: int, show_badge: bool = True) -> None:
    """Tarjeta de un grifo. El numero es el mismo que lleva en el mapa."""
    import streamlit as st

    name = html.escape(station_title(row))
    address = html.escape(short_address(row.get("direccion_display", "")))
    district = html.escape(str(row.get("distrito") or ""))
    badge = (
        '<span class="ga-badge">Con descuento</span>'
        if show_badge and bool(row.get("tiene_descuento")) else ""
    )
    approx = (
        '<span class="ga-approx">Ubicación aprox.</span>'
        if row.get("coord_source") != "exacta" else ""
    )

    st.markdown(
        f'<div class="ga-card"><div class="ga-card-top">'
        f'<span class="ga-rank">{rank}</span>'
        f'<div class="ga-body">'
        f'<p class="ga-name">{name}</p>'
        f'<p class="ga-addr">{address}{" · " + district if district else ""}</p>'
        f'<div class="ga-meta">'
        f'<span class="ga-chip">{float(row["distancia_km"]):.1f} km</span>{badge}{approx}'
        f'</div></div>'
        f'<div class="ga-price"><b>S/ {float(row["precio_final"]):.2f}</b>'
        f'<span>galón</span></div>'
        f'</div>{_actions(float(row["lat"]), float(row["lon"]))}</div>',
        unsafe_allow_html=True,
    )
