
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

URL = "https://appweb.superbancos.gob.ec/fre/publico/formularios/formularioReclamos.jsf"

def _selector_escape(component_id: str) -> str:
    """
    Escapa los dos puntos de los ids JSF para CSS:
    frmFormulario:idCedula -> #frmFormulario\\:idCedula
    """
    return "#" + component_id.replace(":", "\\:")

def consultar(identificacion: str, *, headless: bool = True, timeout_ms: int = 7000) -> Optional[str]:
    """
    Backend Playwright (Superintendencia de Bancos)
    Devuelve SOLO el nombre completo (str) o None si no hay datos.
    No imprime nada.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError  # type: ignore
    except Exception:
        return None

    FIELD_CEDULA = _selector_escape("frmFormulario:idCedula")
    FIELD_NOMBRES = _selector_escape("frmFormulario:idNombres")

    nombre: Optional[str] = None
    try:
        with sync_playwright() as p:
            # usa Firefox por defecto; puedes cambiar a chromium si te conviene
            browser = p.firefox.launch(headless=headless)
            ctx = browser.new_context()
            page = ctx.new_page()

            page.goto(URL, wait_until="networkidle", timeout=timeout_ms)
            page.fill(FIELD_CEDULA, identificacion)
            page.press(FIELD_CEDULA, "Tab")  # dispara valueChange/blur

            try:
                # espera a que el input tenga value o texto no vacío
                page.wait_for_function(
                    """(sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        const v = (el.value ?? el.textContent ?? "").trim();
                        return v.length > 0;
                    }""",
                    arg=FIELD_NOMBRES,
                    timeout=timeout_ms
                )
                nombre = page.get_attribute(FIELD_NOMBRES, "value")
                if not nombre:
                    nombre = page.text_content(FIELD_NOMBRES)
            except PWTimeoutError:
                # intento extra: click en body para forzar blur y reintentar lectura
                try:
                    page.click("body", timeout=1000)
                    nombre = page.get_attribute(FIELD_NOMBRES, "value") or page.text_content(FIELD_NOMBRES)
                except Exception:
                    nombre = None
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception:
        return None

    if nombre:
        nombre = " ".join(nombre.split()).strip()
        return nombre or None
    return None
