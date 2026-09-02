"""Configuracion central de GasolinApp. Editar aqui, no en los modulos."""
from pathlib import Path

# --- Rutas ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
PRIMAX_XLSX = DATA_DIR / "primax_con_descuento_completado.xlsx"
REPSOL_XLSX = DATA_DIR / "repsol_con_descuento_final.xlsx"
DISTRICTS_CSV = DATA_DIR / "peru_districts.csv"
EVPC_SEED = DATA_DIR / "evpc_seed.xlsx"  # respaldo si la descarga falla en frio

# --- Fuente Osinergmin EVPC ---
EVPC_URL = (
    "https://www.osinergmin.gob.pe/seccion/centro_documental/hidrocarburos/"
    "SCOP/SCOP-DOCS/2026/Registro-precios/Ultimos-Precios-Registrados-EVPC.xlsx"
)
EVPC_URL_FALLBACKS = [
    "https://www.osinergmin.gob.pe/seccion/centro_documental/hidrocarburos/"
    "SCOP/SCOP-DOCS/{year}/Registro-precios/Ultimos-Precios-Registrados-EVPC.xlsx",
]
EVPC_SOURCE_PAGE = "https://www.osinergmin.gob.pe/empresas/hidrocarburos/scop/documentos-scop"
# Osinergmin responde 403 sin User-Agent de navegador.
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
}
HTTP_TIMEOUT = 60

# --- Combustibles ---
# La UI solo muestra Regular / Premium; el mapeo tecnico vive aqui.
FUEL_FAMILIES = {
    "Regular": ["GASOHOL REGULAR", "GASOLINA REGULAR"],
    "Premium": ["GASOHOL PREMIUM", "GASOLINA PREMIUM"],
}
DEFAULT_FUEL = "Premium"

# --- Descuentos (S/ por galon) ---
DISCOUNTS = {"REPSOL": 2.5, "PRIMAX": 1.0}
BRAND_LABELS = {"REPSOL": "Repsol", "PRIMAX": "Primax"}

# --- Busqueda ---
RADIUS_OPTIONS_KM = [5, 10, 20]
DEFAULT_RADIUS_KM = 5
TOP_WITH_DISCOUNT = 4
TOP_OTHERS = 4
TOP_NO_DISCOUNT = 6

# --- Ahorro ---
TANK_GALLONS = 14

# --- Ranking: pesos normalizados (deben sumar ~1) ---
RANK_WEIGHTS = {"price": 0.60, "distance": 0.30, "discount": 0.10}

# --- Matching ---
MATCH_COORD_TOLERANCE_KM = 0.35   # radio para aceptar match por coordenadas
MATCH_MIN_CONFIDENCE = 0.70       # por debajo de esto NO se aplica descuento
FUZZY_MIN_SCORE = 75              # piso de similitud de direccion (0-100)

# --- Ubicacion demo (fallback inicial) ---
DEFAULT_LOCATION = {"lat": -12.1400, "lon": -77.0200, "label": "Barranco, Lima"}

# --- Mapa ---
MAP_MAX_PINS = 8
# Las estaciones sin coordenada exacta comparten el centroide de su distrito.
# Se abren en abanico para poder distinguirlas. 0.0013 grados son unos 145 m:
# a zoom 12 ya se separan en pantalla, y sigue muy por debajo del error que ya
# arrastra un centroide distrital (un distrito de Lima mide kilometros).
MAP_JITTER_DEG = 0.0013

# --- Cache ---
CACHE_TTL_SECONDS = 86400  # 1 dia

# --- UI: tema "Ruta" -------------------------------------------------------
# Roles de color, no una bolsa de tonos. El modo oscuro esta disenado aparte:
# no es el claro invertido (las superficies suben de luminosidad, el ambar baja
# de saturacion para no vibrar sobre fondo oscuro).
THEME = {
    "light": {
        "canvas": "#F6F7F8",
        "surface": "#FFFFFF",
        "ink": "#14181B",
        "ink_2": "#59656C",
        "line": "#D7DEE2",
        "accent": "#B4690E",
        "on_accent": "#FFFFFF",
        "ok": "#0F7A52",
        "ok_bg": "rgba(15,122,82,.10)",
        "chip": "#EEF1F3",
        "chip_ink": "#3A464C",
    },
    "dark": {
        "canvas": "#0F1416",
        "surface": "#182024",
        "ink": "#E9EFF2",
        "ink_2": "#9DACB3",
        "line": "#2C383E",
        "accent": "#F2A93B",
        "on_accent": "#1A1206",
        "ok": "#4ECBA0",
        "ok_bg": "rgba(78,203,160,.13)",
        "chip": "#222C31",
        "chip_ink": "#BFCBD1",
    },
}

APP_NAME = "GasolinApp"
APP_ICON = ROOT / "assets" / "icon.png"
FONT_FAMILY = "Inter"
FONT_CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400;500;600;700;800&display=swap"
)

# --- Branding (editable) ---
AUTHOR_NAME = "Gabriel Villayzan"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/gvillayzan/"
ABOUT_TEXT = (
    "Parte de mis apps personales 🧪 — ejercicios que hago divirtiendome con IA. "
    "Construida con Gemini Spark ✨, Claude Code 🤖 y varios modelos en modo detallado."
)
