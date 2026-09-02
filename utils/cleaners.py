"""Saneamiento de texto.

Las fuentes traen mojibake real (UTF-8 y latin-1 leidos como CP932):
    'AV. JESUS Nﾂｺ 2307'     -> 'AV. JESUS Nº 2307'
    'AV. JACINTO IBAﾑEZ S/N' -> 'AV. JACINTO IBAÑEZ S/N'
    'BREﾑA'                  -> 'BREÑA'

Se mantienen dos versiones de cada texto:
    *_display -> legible, con tildes, para la UI
    *_norm    -> mayusculas sin tildes ni puntuacion, para joins y comparaciones
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

# Marcadores de codificacion rota: katakana halfwidth, punto medio y replacement char.
_SUSPECT = re.compile(r"[\uFF61-\uFF9F\u30FB\uFFFD]")

# Pares conocidos que se pierden al copiar/pegar (recuperacion dirigida).
_PAIRS = {
    "\uFF83\uFF65": "Ñ",
    "\uFF83\u30FB": "Ñ",
}

# Alias de division politica: Osinergmin y el maestro de distritos difieren.
DEPT_ALIASES = {
    "PROV CONST DEL CALLAO": "CALLAO",
    "PROVINCIA CONSTITUCIONAL DEL CALLAO": "CALLAO",
}

_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00ad]")
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]")
_SPACES = re.compile(r"\s+")


def _halfwidth_to_byte(ch: str) -> bytes | None:
    """Katakana halfwidth -> el byte simple que lo origino en CP932."""
    o = ord(ch)
    if 0xFF61 <= o <= 0xFF9F:
        return bytes([o - 0xFF61 + 0xA1])
    return None


def _decode_run(buf: bytes) -> str:
    """Decodifica una corrida de bytes: UTF-8 si es valido, si no CP1252."""
    try:
        out = buf.decode("utf-8")
        if not _SUSPECT.search(out):
            return out
    except UnicodeDecodeError:
        pass
    return buf.decode("cp1252", errors="replace")


def repair_mojibake(text: str) -> str:
    """Repara texto corrompido por doble decodificacion. Idempotente y seguro.

    No toca cadenas que no muestran sintomas, para no danar texto ya correcto.
    """
    if not isinstance(text, str) or not _SUSPECT.search(text):
        return text

    for broken, fixed in _PAIRS.items():
        text = text.replace(broken, fixed)
    if not _SUSPECT.search(text):
        return text

    # Caso 1: la cadena entera es UTF-8 leido como CP932 -> roundtrip exacto.
    try:
        whole = text.encode("cp932").decode("utf-8")
        if not _SUSPECT.search(whole):
            return whole
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    # Caso 2: bytes latin-1 sueltos mezclados con texto sano.
    out: list[str] = []
    run = b""
    for ch in text:
        byte = _halfwidth_to_byte(ch)
        if byte is not None:
            run += byte
            continue
        if run:
            out.append(_decode_run(run))
            run = b""
        out.append(ch)
    if run:
        out.append(_decode_run(run))
    return "".join(out)


def clean_display(value) -> str:
    """Texto listo para mostrar: reparado, sin invisibles, espacios colapsados."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = repair_mojibake(str(value))
    text = _INVISIBLE.sub("", text)
    return _SPACES.sub(" ", text).strip()


def norm_key(value) -> str:
    """Clave normalizada para matching: MAYUSCULAS, sin tildes ni puntuacion."""
    text = clean_display(value).upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _NON_ALNUM.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def norm_admin(value) -> str:
    """Como norm_key pero resolviendo alias de departamento/provincia."""
    key = norm_key(value)
    return DEPT_ALIASES.get(key, key)


_ADDRESS_ABBR = {
    r"\bAVENIDA\b": "AV",
    r"\bAV\b": "AV",
    r"\bJIRON\b": "JR",
    r"\bCALLE\b": "CA",
    r"\bCARRETERA\b": "CARR",
    r"\bPANAMERICANA\b": "PANAM",
    r"\bKILOMETRO\b": "KM",
    r"\bNRO\b": "",
    r"\bNo\b": "",
    r"\bN\b": "",
    r"\bMZ\b": "MZ",
    r"\bS N\b": "",
}


def norm_address(value) -> str:
    """Direccion normalizada para comparacion (abreviaturas homogeneas)."""
    text = norm_key(value)
    for pattern, repl in _ADDRESS_ABBR.items():
        text = re.sub(pattern, repl, text)
    return _SPACES.sub(" ", text).strip()


def clean_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Aplica clean_display sobre las columnas de texto indicadas."""
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].map(clean_display)
    return out
