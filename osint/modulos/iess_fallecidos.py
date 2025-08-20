# iess_fallecidos.py
# -*- coding: utf-8 -*-
import sys
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://iess.gob.ec/prjPensionesJubilacion-web/pages/solicitudGenerica/solicitud.jsf"
NOMBRE_MODULO = "Fallecidos"

def consultar(ci: str, timeout_ms: int = 12000) -> str:
    """
    Retorna:
      IESS Fallecidos

      Fallecimiento: YYYY-MM-DD
    o
      IESS Fallecidos

      No existe fecha de fallecimiento para la cédula <ci>
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="es-EC",
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
        )
        page = context.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector('input[id$=":cedcau"]', timeout=timeout_ms)

        page.fill('input[id$=":cedcau"]', ci)
        page.click('input[type="button"][value="Continuar"]', force=True)

        # Buscar SOLO dentro del fieldset "Fecha de Fallecimiento"
        fecha_locator = page.locator(
            'fieldset:has(legend:has-text("Fecha de Fallecimiento")) >> span[id$=":fecFallecimiento"]'
        )

        try:
            fecha_text = fecha_locator.text_content(timeout=timeout_ms)
        except PWTimeoutError:
            fecha_text = None

        context.close()
        browser.close()

    if fecha_text:
        fecha = fecha_text.strip()
        if len(fecha) == 10 and fecha[4] == "-" and fecha[7] == "-":
            return f"{NOMBRE_MODULO}\n\nFallecimiento: {fecha}"

    return f"{NOMBRE_MODULO}\n\nNo existe fecha de fallecimiento para la cédula {ci}"


# -------- Helpers para el menú --------

# Captura y extrae la fecha del string de consultar()
_RE_LINEA_FECHA = re.compile(r"Fallecimiento:\s*(\d{4}-\d{2}-\d{2})")

def consultar_o_none(ci: str, timeout_ms: int = 12000):
    """
    Igual que consultar(), pero:
    - Devuelve el string COMPLETO solo si existe 'Fallecimiento: YYYY-MM-DD'
    - Devuelve None si no hay fecha / no fallecido / timeout / error
    """
    try:
        s = consultar(ci, timeout_ms)
    except Exception:
        return None
    return s if s and _RE_LINEA_FECHA.search(s) else None


def search(ci: str, timeout_ms: int = 12000):
    """
    Usado por el menú:
      - Devuelve "Fallecimiento: YYYY-MM-DD" si existe.
      - Devuelve None si no hay fecha / no fallecido / error.
    """
    try:
        salida = consultar(ci, timeout_ms) or ""
        m = _RE_LINEA_FECHA.search(salida)
        if m:
            # Solo la línea que el menú mostrará bajo "==> IESS Fallecidos"
            return f"Fallecimiento: {m.group(1)}"
        return None
    except Exception:
        return None


if __name__ == "__main__":
    ci = sys.argv[1] if len(sys.argv) > 1 else "1723326110"
    print(consultar(ci))
