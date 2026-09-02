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

# --- Cache ---
CACHE_TTL_SECONDS = 86400  # 1 dia

# --- UI ---
COLORS = {
    "bg": "#FAFAFA",
    "text": "#111111",
    "accent": "#10B981",
    "muted": "#6B7280",
    "card": "#FFFFFF",
    "border": "#ECECEC",
}
APP_NAME = "GasolinApp"

# --- Branding (editable) ---
AUTHOR_NAME = "Gabriel Villayzan"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/gvillayzan/"
ABOUT_TEXT = (
    "Parte de mis apps personales 🧪 — ejercicios que hago divirtiendome con IA. "
    "Construida con Gemini Spark ✨, Claude Code 🤖 y varios modelos en modo detallado."
)
