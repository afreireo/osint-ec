# osint/modulos/nombres.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional

NOMBRE_MODULO = "Nombres"

def search(identificacion: str) -> Optional[str]:
    """
    Devuelve SOLO un string con el nombre completo, o None si no hay datos.
    """
    # 1) Backend requests (SIIRS)
    
    try:
        from .nombres_backends.request_siirs import consultar as req_siirs
        name = req_siirs(identificacion)
        if name:
            return name
    except Exception:
        pass  # fallar en silencio y probar otros backends


    # 2) PUSAK (requests)
    try:
        from .nombres_backends.request_pusak import consultar as pusak_consultar
        name2 = pusak_consultar(identificacion)
        if name2:
            return name2
    except Exception:
        pass


    # 3) Playwright (Super de Bancos)
    try:
        from .nombres_backends.playwright_super import consultar as pw_super
        name3 = pw_super(identificacion)
        if name3:
            return name3
    except Exception:
        pass


    return None
