
# osint/modulos/estado_civil.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional, Iterable
import re
import requests
import urllib3

NOMBRE_MODULO = "Estado Civil"

# Silenciar el warning por verify=False en requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://pusakregistro.fomentoacademico.gob.ec/api/registro-civil/consultar"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://pusakregistro.fomentoacademico.gob.ec",
    "Referer": "https://pusakregistro.fomentoacademico.gob.ec/register",
    "User-Agent": "Mozilla/5.0",
}

TIMEOUT = 20
VERIFY_SSL = False  # ponlo en True si tu entorno no tiene problemas de certificados


def _first(data: dict, keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _from_text_blob(data: dict) -> Optional[str]:
    """
    Busca en cadenas del payload un patrón tipo 'Estado Civil: XYZ'.
    """
    patt = re.compile(r"Estado\s*Civil\s*:\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ\-/\s]+)", re.IGNORECASE)
    for v in data.values():
        if isinstance(v, str):
            m = patt.search(v)
            if m:
                return m.group(1).strip()
    return None


def _normalize_estado(s: str) -> str:
    """
    Normaliza variantes comunes a un conjunto consistente.
    """
    key = re.sub(r"\s+", " ", s.strip().upper())
    mapping = {
        "CASADA": "CASADO",
        "CASADO": "CASADO",
        "SOLTERA": "SOLTERO",
        "SOLTERO": "SOLTERO",
        "DIVORCIADA": "DIVORCIADO",
        "DIVORCIADO": "DIVORCIADO",
        "VIUDA": "VIUDO",
        "VIUDO": "VIUDO",
        "UNION DE HECHO": "UNIÓN DE HECHO",
        "UNION LIBRE": "UNIÓN DE HECHO",
        "CONCUBINATO": "UNIÓN DE HECHO",
        "SEPARADA": "SEPARADO",
        "SEPARADO": "SEPARADO",
    }
    return mapping.get(key, key)


def search(identificacion: str) -> Optional[str]:
    """
    Devuelve SOLO el estado civil (str) o None si no hay datos.
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

        # Intentar campos típicos
        estado = _first(
            data,
            (
                "estadoCivil", "estado_civil", "estadoCivilDesc",
                "estado", "estCivil", "estadocivil", "estadoCivilDescripcion",
            ),
        )

        # Fallback: extraer desde blob de texto
        if not estado:
            estado = _from_text_blob(data)

        return _normalize_estado(estado) if estado else None

    except requests.RequestException:
        return None
    except Exception:
        return None
