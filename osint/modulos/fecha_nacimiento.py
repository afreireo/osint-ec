# osint/modulos/fecha_nacimiento.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional
import requests
import urllib3
from datetime import datetime, date

NOMBRE_MODULO = "Fecha Nacimiento"

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
VERIFY_SSL = False  # mantener False si tu entorno presenta errores de certificados


def _parse_ddmmyyyy(fecha: str) -> Optional[date]:
    """Convierte 'dd/mm/YYYY' a date."""
    try:
        return datetime.strptime(fecha.strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def _edad(desde: date, hoy: Optional[date] = None) -> int:
    """Calcula edad exacta en años."""
    hoy = hoy or date.today()
    return hoy.year - desde.year - ((hoy.month, hoy.day) < (desde.month, desde.day))


def search(identificacion: str) -> Optional[str]:
    """
    Devuelve una cadena 'YYYY-MM-DD (N años)' o None si no hay datos.
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

        # La API devuelve 'fechaNacimiento' en formato 'dd/mm/YYYY'
        fn_raw: Optional[str] = data.get("fechaNacimiento")
        if not fn_raw:
            return None

        dob = _parse_ddmmyyyy(fn_raw)
        if not dob:
            return None

        years = _edad(dob)
        # Formato solicitado: YYYY-MM-DD (N años)
        return f"{dob.isoformat()} ({years} años)"

    except requests.RequestException:
        return None
    except Exception:
        return None
