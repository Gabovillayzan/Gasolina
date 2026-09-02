"""Estilos y tarjetas de resultado. Mantiene el HTML fuera de app.py."""
from __future__ import annotations

import html

import pandas as pd

from utils.constants import BRAND_LABELS, COLORS
from utils.links import google_maps_url, waze_url

CARD_CSS = f"""
<style>
  /* Ocultar cromo de Streamlit para que se vea como app propia */
  #MainMenu, footer, header {{ visibility: hidden; }}
  .stDeployButton {{ display: none; }}

  .stApp {{ background: {COLORS['bg']}; }}
  .block-container {{
      padding: 1.1rem 1rem 3rem;
      max-width: 640px;
  }}
  html, body, [class*="css"] {{ color: {COLORS['text']}; }}

  .ga-head h1 {{
      font-size: 1.6rem; font-weight: 700; margin: 0 0 .15rem;
      letter-spacing: -.02em;
  }}
  .ga-head p {{ margin: 0 0 .9rem; color: {COLORS['muted']}; font-size: .92rem; }}

  .ga-loc {{
      display: flex; align-items: center; gap: .45rem;
      font-size: .9rem; padding: .5rem .7rem; margin-bottom: .6rem;
      border-radius: 10px; border: 1px solid {COLORS['border']};
      background: {COLORS['card']};
  }}
  .ga-loc-ok span {{ color: {COLORS['text']}; font-weight: 600; }}
  .ga-loc-default span {{ color: {COLORS['muted']}; }}

  .ga-h3 {{
      font-size: 1rem; font-weight: 700; margin: 1.3rem 0 .55rem;
      letter-spacing: -.01em;
  }}

  .ga-savings {{
      background: rgba(16,185,129,.09);
      border: 1px solid rgba(16,185,129,.28);
      color: #065F46;
      border-radius: 12px; padding: .7rem .85rem;
      font-size: .9rem; margin: .9rem 0 .2rem;
  }}

  .ga-card {{
      background: {COLORS['card']};
      border: 1px solid {COLORS['border']};
      border-radius: 14px;
      padding: .85rem .9rem;
      margin-bottom: .6rem;
      box-shadow: 0 1px 3px rgba(17,17,17,.05);
  }}
  .ga-card-top {{
      display: flex; justify-content: space-between;
      align-items: flex-start; gap: .8rem;
  }}
  .ga-name {{
      font-weight: 700; font-size: .97rem; line-height: 1.25;
      margin: 0 0 .18rem;
  }}
  .ga-addr {{
      color: {COLORS['muted']}; font-size: .81rem; line-height: 1.35;
      margin: 0 0 .3rem;
  }}
  .ga-price {{
      text-align: right; white-space: nowrap;
      font-size: 1.32rem; font-weight: 800; letter-spacing: -.03em;
      color: {COLORS['text']}; line-height: 1.1;
  }}
  .ga-price small {{
      display: block; font-size: .66rem; font-weight: 600;
      color: {COLORS['muted']}; letter-spacing: .02em;
  }}
  .ga-meta {{
      display: flex; align-items: center; gap: .4rem;
      flex-wrap: wrap; margin-top: .15rem;
  }}
  .ga-dist {{
      font-size: .8rem; font-weight: 600; color: {COLORS['text']};
      background: #F3F4F6; border-radius: 999px; padding: .12rem .5rem;
  }}
  .ga-badge {{
      font-size: .72rem; font-weight: 700; letter-spacing: .01em;
      color: #065F46; background: rgba(16,185,129,.13);
      border: 1px solid rgba(16,185,129,.3);
      border-radius: 999px; padding: .12rem .5rem;
  }}
  .ga-approx {{ font-size: .72rem; color: {COLORS['muted']}; }}

  .ga-actions {{ display: flex; gap: .45rem; margin-top: .6rem; }}
  .ga-actions a {{
      flex: 1; text-align: center; text-decoration: none;
      font-size: .82rem; font-weight: 600;
      padding: .42rem .5rem; border-radius: 9px;
      border: 1px solid {COLORS['border']};
      color: {COLORS['text']}; background: #FCFCFC;
  }}
  .ga-actions a:hover {{ border-color: {COLORS['accent']}; color: {COLORS['accent']}; }}

  .ga-footer {{
      margin-top: 2.2rem; padding-top: 1rem;
      border-top: 1px solid {COLORS['border']};
      color: {COLORS['muted']}; font-size: .78rem; line-height: 1.5;
  }}
  .ga-footer p {{ margin: 0 0 .35rem; }}
  .ga-footer a {{ color: {COLORS['accent']}; text-decoration: none; }}
  .ga-disclaimer {{ font-size: .72rem; opacity: .8; }}

  /* Controles mas comodos en movil */
  .stButton button {{
      border-radius: 10px; font-weight: 600; font-size: .87rem;
      border: 1px solid {COLORS['border']};
  }}
  @media (max-width: 480px) {{
      .block-container {{ padding: .9rem .7rem 2.5rem; }}
      .ga-price {{ font-size: 1.22rem; }}
  }}
</style>
"""


def station_title(row: pd.Series) -> str:
    """Marca si es Repsol o Primax; si no, la razon social."""
    brand = row.get("discount_brand") or row.get("brand_razon")
    if brand in BRAND_LABELS:
        district = row.get("distrito") or ""
        return f"{BRAND_LABELS[brand]} {district}".strip()
    return row.get("razon_display") or "Grifo"


def short_address(address: str, limit: int = 68) -> str:
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


def render_card(row: pd.Series, show_badge: bool = True) -> None:
    """Tarjeta de un grifo: nombre, direccion, distancia y precio final."""
    import streamlit as st

    name = html.escape(station_title(row))
    address = html.escape(short_address(row.get("direccion_display", "")))
    district = html.escape(str(row.get("distrito") or ""))
    distance = float(row["distancia_km"])
    price = float(row["precio_final"])
    lat, lon = float(row["lat"]), float(row["lon"])

    badge = ""
    if show_badge and bool(row.get("tiene_descuento")):
        badge = "<span class='ga-badge'>Con descuento</span>"

    # La coordenada aproximada se avisa: viene del centroide del distrito.
    approx = ""
    if row.get("coord_source") != "exacta":
        approx = "<span class='ga-approx'>ubicacion aprox.</span>"

    location_line = f"{address}" + (f" · {district}" if district else "")

    st.markdown(
        f"""
        <div class="ga-card">
          <div class="ga-card-top">
            <div>
              <p class="ga-name">{name}</p>
              <p class="ga-addr">{location_line}</p>
              <div class="ga-meta">
                <span class="ga-dist">{distance:.1f} km</span>{badge}{approx}
              </div>
            </div>
            <div class="ga-price">S/ {price:.2f}<small>POR GALON</small></div>
          </div>
          <div class="ga-actions">
            <a href="{google_maps_url(lat, lon)}" target="_blank" rel="noopener">Google Maps</a>
            <a href="{waze_url(lat, lon)}" target="_blank" rel="noopener">Waze</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
