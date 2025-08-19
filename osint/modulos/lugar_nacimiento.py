
# osint/modulos/lugar_nacimiento.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional, Iterable
import re
import requests
import urllib3

# Silenciar el warning por verify=False en requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NOMBRE_MODULO = "Lugar de Nacimiento"

URL = "https://pusakregistro.fomentoacademico.gob.ec/api/registro-civil/consultar"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://pusakregistro.fomentoacademico.gob.ec",
    "Referer": "https://pusakregistro.fomentoacademico.gob.ec/register",
    "User-Agent": "Mozilla/5.0",
}

TIMEOUT = 20
VERIFY_SSL = False  # ponlo en True si no tienes problemas de certificados


def _first(data: dict, keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _clean_piece(x: Optional[str]) -> Optional[str]:
    if not x:
        return None
    # quita comas finales u otros separadores, normaliza espacios y mayúsculas
    x = re.sub(r"[,\s]+$", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x.upper() or None


def _from_text_blob(data: dict) -> Optional[str]:
    """
    Busca en cualquier string del payload un patrón tipo:
    'Provincia: XXX - Ciudad / Canton: YYY - Parroquia: ZZZ'
    y devuelve 'XXX - YYY - ZZZ'
    """
    patt = re.compile(
        r"Provincia\s*:\s*([^-–—\n\r]+?)\s*-\s*(?:Ciudad\s*/\s*Cant[oó]n|Cant[oó]n|Ciudad)\s*:\s*([^-–—\n\r]+?)\s*-\s*Parroquia\s*:\s*([^\n\r,]+)",
        re.IGNORECASE,
    )
    for v in data.values():
        if isinstance(v, str):
            m = patt.search(v)
            if m:
                p, c, par = (_clean_piece(m.group(1)), _clean_piece(m.group(2)), _clean_piece(m.group(3)))
                if p and c and par:
                    return f"{p} - {c} - {par}"
    return None


def search(identificacion: str) -> Optional[str]:
    """
    Devuelve 'PROVINCIA - CANTON - PARROQUIA' o None si no hay datos.
    """
    try:
        resp = requests.post(
            URL,
            json={"numeroCedula": identificacion},
            headers=HEADERS,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}

        # 1) Intentar campos estructurados
        provincia = _first(
            data,
            ("provinciaNacimiento", "provincia", "provinciaNacimientoDesc", "provinciaNacimientoNombre"),
        )
        canton = _first(
            data,
            ("cantonNacimiento", "ciudadCanton", "canton", "ciudad", "ciudadNacimiento", "ciudadNacimientoDesc"),
        )
        parroquia = _first(
            data,
            ("parroquiaNacimiento", "parroquia", "parroquiaNacimientoDesc", "parroquiaNacimientoNombre"),
        )

        provincia = _clean_piece(provincia)
        canton = _clean_piece(canton)
        parroquia = _clean_piece(parroquia)

        if provincia and canton and parroquia:
            return f"{provincia} - {canton} - {parroquia}"

        # 2) Fallback: extraer desde cadenas largas con etiquetas
        blob = _from_text_blob(data)
        if blob:
            return blob

        return None

    except requests.RequestException:
        return None
    except Exception:
        return None
