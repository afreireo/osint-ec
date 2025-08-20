# -*- coding: utf-8 -*-
"""
correo.py — Registro Civil: extrae el email desde el XML de la primera factura.
- Entra a /portalCiudadano/comprobantes.jsf
- Busca por NUI
- En la tabla FACTURAS, hace clic en "Descargar XML" de la 1era fila
- Lee el XML y extrae <campoAdicional nombre="Email">...</campoAdicional>

CLI:
    python correo.py 1726207275
"""

import sys
import re
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://apps.registrocivil.gob.ec/portalCiudadano/comprobantes.jsf"
NOMBRE_MODULO = "Correo en facturas RC"

# --------- Utilidades XML ---------

def _extraer_email_desde_xml_bytes(xml_bytes: bytes) -> Optional[str]:
    """
    Intenta encontrar el email en <campoAdicional nombre="Email">...</campoAdicional>.
    Si no aparece, busca cualquier <campoAdicional> cuyo texto contenga '@'.
    """
    if not xml_bytes:
        return None

    # Evitar problemas con firmas XML y namespaces: parseo simple con regex tolerante.
    # 1) Buscar el bloque infoAdicional ... campoAdicional ... (más rápido)
    try:
        xml_txt = xml_bytes.decode("utf-8", errors="ignore")
    except Exception:
        try:
            xml_txt = xml_bytes.decode("latin-1", errors="ignore")
        except Exception:
            return None

    # Prioridad: campoAdicional nombre="Email"
    m = re.search(
        r'<campoAdicional\s+[^>]*nombre\s*=\s*"(?:Email|EMAIL|email)"[^>]*>([^<]+)</campoAdicional>',
        xml_txt,
        re.IGNORECASE,
    )
    if m:
        email = m.group(1).strip()
        # Limpieza simple
        email = email.replace("\r", "").replace("\n", "").strip()
        return email if "@" in email else None

    # Fallback: cualquier campoAdicional con un correo dentro
    for m in re.finditer(r'<campoAdicional[^>]*>([^<]+)</campoAdicional>', xml_txt, re.IGNORECASE):
        cand = m.group(1).strip()
        if "@" in cand:
            # Tomar el primer candidato con @
            return cand.replace("\r", "").replace("\n", "").strip()

    return None

# --------- Navegación / scraping ---------

def _buscar_y_abrir_xml_primera_factura(ci: str, timeout_ms: int, headless: bool = True) -> Optional[bytes]:
    """
    Abre la página, busca el NUI, y descarga el XML de la primera factura.
    Devuelve los bytes del XML o None si falla.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="es-EC",
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            extra_http_headers={"Accept-Language": "es-EC,es;q=0.9"},
        )
        page = context.new_page()

        try:
            # 1) Ir al portal
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)

            # 2) Esperar input y enviar NUI
            page.wait_for_selector('input[id$=":txtIdentificacion"]', timeout=timeout_ms)
            page.fill('input[id$=":txtIdentificacion"]', ci)

            # 3) Clic en "Buscar" (enlace PrimeFaces)
            #    id exacto suele ser j_idt107:j_idt111, pero usamos sufijo robusto.
            buscar = page.locator('a[id$=":j_idt111"]').first
            if buscar.count() == 0:
                # Fallback por aria-label/title
                buscar = page.locator('a[aria-label="Buscar"], a[title="Buscar"]').first
            if buscar.count() == 0:
                raise RuntimeError("No se encontró el botón de 'Buscar'.")

            # Ejecuta la petición Ajax de PrimeFaces
            buscar.click()

            # 4) Esperar a que se renderice la tabla de FACTURAS y al menos una fila
            #    (tbody ... :tabFacturas_data  y fila data-ri="0")
            page.wait_for_selector('tbody[id$=":tabFacturas_data"] tr[data-ri="0"]', timeout=timeout_ms)

            # 5) Dentro de la primera fila, localizar el botón "Descargar XML"
            first_row = page.locator('tbody[id$=":tabFacturas_data"] tr[data-ri="0"]').first

            # a) Selector por sufijo de id PrimeFaces
            xml_link = first_row.locator('a[id$=":j_idt125"]').first

            # b) Fallback por imagen (alt/title) → subir al <a> padre
            if xml_link.count() == 0:
                xml_link = first_row.locator('xpath=.//img[@alt="Descargar XML" or @title="Descargar XML"]/parent::a').first

            if xml_link.count() == 0:
                # Como último recurso: buscar en toda la tabla el primer botón XML
                xml_link = page.locator('tbody[id$=":tabFacturas_data"] a[id$=":j_idt125"]').first
                if xml_link.count() == 0:
                    xml_link = page.locator(
                        'xpath=//tbody[substring(@id, string-length(@id) - string-length(":tabFacturas_data") + 1) = ":tabFacturas_data"]'
                        '//img[@alt="Descargar XML" or @title="Descargar XML"]/parent::a'
                    ).first

            if xml_link.count() == 0:
                return None  # no hay botón XML visible

            try:
                xml_link.scroll_into_view_if_needed(timeout=timeout_ms)
            except Exception:
                pass

            # 6) Descargar (Content-Disposition: attachment; ... .xml)
            with page.expect_download(timeout=timeout_ms + 15000) as dl_info:
                xml_link.click(force=True)
            download = dl_info.value

            # 7) Obtener bytes del XML
            xml_bytes = None
            try:
                xml_bytes = download.content()
            except Exception:
                tmp_path = download.path()  # puede ser None en algunas versiones
                if tmp_path:
                    with open(tmp_path, "rb") as f:
                        xml_bytes = f.read()

            return xml_bytes

        except PWTimeoutError:
            return None
        except Exception:
            return None
        finally:
            context.close()
            browser.close()

# --------- API del módulo ---------

def consultar(ci: str, timeout_ms: int = 20000, headless: bool = True) -> str:
    """
    Retorna:
      Correo en facturas RC

      Email: alguien@dominio.tld
    o
      Correo en facturas RC

      No se encontró email en el XML de la primera factura para la identificación <ci>
    o
      Correo en facturas RC

      No se encontró enlace XML / No hay facturas visibles / Timeout.
    """
    xml_bytes = _buscar_y_abrir_xml_primera_factura(ci, timeout_ms=timeout_ms, headless=headless)
    if not xml_bytes:
        return f"{NOMBRE_MODULO}\n\nNo se pudo obtener el XML de la primera factura (botón no encontrado o descarga fallida)."

    email = _extraer_email_desde_xml_bytes(xml_bytes)
    if email:
        return f"{NOMBRE_MODULO}\n\nEmail: {email}"

    return f"{NOMBRE_MODULO}\n\nNo se encontró email en el XML de la primera factura para la identificación {ci}"

# Compatibles con tu menú:
import re as _re
_RE_LINEA_EMAIL = _re.compile(r"Email:\s*(.+)", _re.IGNORECASE)

def consultar_o_none(ci: str, timeout_ms: int = 20000, headless: bool = True):
    """
    Igual que consultar(), pero:
    - Devuelve el string SOLO si encuentra 'Email: ...'
    - Devuelve None si no hay email / timeout / fallo de descarga.
    """
    s = consultar(ci, timeout_ms=timeout_ms, headless=headless)
    if s and _RE_LINEA_EMAIL.search(s):
        return s
    return None

def search(ci: str, timeout_ms: int = 20000, headless: bool = True):
    """
    Usado por el menú:
      - Devuelve "Email: correo@dominio" si existe.
      - Devuelve None si no encuentra email.
    """
    salida = consultar(ci, timeout_ms=timeout_ms, headless=headless) or ""
    m = _RE_LINEA_EMAIL.search(salida)
    if m:
        return f"{m.group(1).strip()}"
    return None

# --------- CLI ---------

if __name__ == "__main__":
    ci = sys.argv[1] if len(sys.argv) > 1 else "1726207260"
    print(consultar(ci))
