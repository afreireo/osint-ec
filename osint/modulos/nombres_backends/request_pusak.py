# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional
import re
import requests
import urllib3

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
VERIFY_SSL = False  # mantener False si tu entorno da error de certificados

def _clean(x: Optional[str]) -> Optional[str]:
    if not x:
        return x
    x = re.sub(r"\s+", " ", x).strip()
    return x or None

def consultar(identificacion: str) -> Optional[str]:
    """
    Devuelve SOLO el nombre completo (str) o None si no hay datos.
    No imprime warnings de SSL.
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

        # Posibles campos con el nombre completo ya construido
        nombre_directo = (
            data.get("nombresApellidos")
            or data.get("nombreCompleto")
            or data.get("nombresCompletos")
        )

        if not nombre_directo:
            # Armar desde partes si no viene el campo directo
            nombres = data.get("nombre") or data.get("nombres")
            ap_p = data.get("apellidoPaterno") or data.get("apellido1")
            ap_m = data.get("apellidoMaterno") or data.get("apellido2")
            apellidos = " ".join(p for p in [ap_p, ap_m] if p) or data.get("apellidos")
            if nombres and apellidos:
                nombre_directo = f"{nombres} {apellidos}"
            elif nombres:
                nombre_directo = nombres
            elif apellidos:
                nombre_directo = apellidos

        return _clean(nombre_directo)
    except requests.RequestException:
        return None
    except Exception:
        return None
