
# -*- coding: utf-8 -*-
# titulos.py — SENESCYT (Consulta de Títulos)
from __future__ import annotations

import os
import re
import sys
import unicodedata
from time import sleep
from typing import List, Dict, Optional

from PIL import Image, ImageFilter
from pytesseract import image_to_string
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://www.senescyt.gob.ec/consulta-titulos-web/faces/vista/consulta/consulta.xhtml"
NOMBRE_MODULO = "Títulos SENESCYT"

MAX_INTENTOS_CAPTCHA = 12
WAIT_RESULT_MS = 7000  # espera tras "Buscar" a que aparezca tabla o mensaje


# -------------------- Utilidades OCR/CAPTCHA --------------------

def _preprocesar_imagen(captcha_path: str, output_path: str = "captcha_preprocessed.png") -> str:
    img = Image.open(captcha_path).convert("L")  # escala de grises
    img = img.filter(ImageFilter.SHARPEN)        # enfocar
    umbral = 128
    img = img.point(lambda x: 255 if x > umbral else 0)  # binarización
    img.save(output_path)
    return output_path

def _resolver_captcha(captcha_path: str) -> str:
    return image_to_string(
        Image.open(captcha_path),
        config="--psm 7 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyz"
    ).strip()

def _texto_captcha_valido(txt: str) -> bool:
    return len(txt) == 4 and txt.isalnum()

# -------------------- Normalización de texto --------------------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _norm(s: str) -> str:
    s = s.strip()
    s = _strip_accents(s).lower()
    s = re.sub(r"\s+", " ", s)
    return s

# -------------------- Extracción de tablas --------------------

_HEADERS_OBJETIVO = {
    "fecha": _norm("Fecha de Registro"),
    "titulo": _norm("Título"),
    "ies": _norm("Institución de Educación Superior"),
}

def _extraer_registros(page) -> List[Dict[str, str]]:
    """
    Busca tablas que contengan las columnas objetivo y devuelve
    una lista de dicts con: fecha, titulo, ies.
    """
    registros: List[Dict[str, str]] = []
    try:
        tablas = page.locator("table").all()
        for tabla in tablas:
            ths = [th.inner_text().strip() for th in tabla.locator("th").all()]
            if not ths:
                continue

            # Mapa de encabezado normalizado -> índice
            header_idx = {_norm(h): i for i, h in enumerate(ths)}

            # Verificar que existan las 3 columnas clave
            if not all(v in header_idx for v in _HEADERS_OBJETIVO.values()):
                continue

            i_fecha = header_idx[_HEADERS_OBJETIVO["fecha"]]
            i_titulo = header_idx[_HEADERS_OBJETIVO["titulo"]]
            i_ies = header_idx[_HEADERS_OBJETIVO["ies"]]

            filas = tabla.locator("tbody tr").all()
            for fila in filas:
                tds = [td.inner_text().strip() for td in fila.locator("td").all()]
                if not tds or max(i_fecha, i_titulo, i_ies) >= len(tds):
                    continue
                registros.append({
                    "fecha": tds[i_fecha],
                    "titulo": tds[i_titulo],
                    "ies": tds[i_ies],
                })
    except Exception:
        pass
    return registros

# -------------------- Verificación de resultado --------------------

def _verificar_resultado(page) -> str:
    """
    Devuelve:
      - "CAPTCHA_INCORRECTO"
      - "CEDULA_INVALIDA"   (incluye 'No se encontraron resultados')
      - "RESULTADO_OK"
    """
    # 1) Cualquier mensaje (error/warn/info/fatal)
    try:
        msg_box = page.locator('div#formPrincipal\\:messages')
        if msg_box.count() > 0:
            txt = msg_box.inner_text(timeout=1500)
            n = _norm(txt)
            if "caracteres incorrectos" in n:
                return "CAPTCHA_INCORRECTO"
            if ("no se encontraron resultados" in n) or ("no existen registros" in n):
                return "CEDULA_INVALIDA"
    except Exception:
        pass

    # 2) ¿Hay registros reales en tabla?
    if _extraer_registros(page):
        return "RESULTADO_OK"

    # 3) Sin mensaje ni tabla todavía: tratar como captcha incorrecto para reintentar
    return "CAPTCHA_INCORRECTO"


def _intentar_resolver_captcha(page, cedula: str) -> bool:
    intento = 1
    captcha_bytes_prev = None

    while intento <= MAX_INTENTOS_CAPTCHA:
        page.fill('input#formPrincipal\\:identificacion', cedula)

        captcha_sel = 'img#formPrincipal\\:capimg'
        captcha_path = f"captcha_{intento}.png"
        try:
            page.wait_for_selector(captcha_sel, timeout=6000)
            page.locator(captcha_sel).screenshot(path=captcha_path)
        except PWTimeoutError:
            page.reload()
            sleep(1)
            continue

        # Evitar repetir el mismo captcha
        try:
            with open(captcha_path, "rb") as f:
                captcha_bytes = f.read()
        except Exception:
            captcha_bytes = None

        if captcha_bytes_prev == captcha_bytes and captcha_bytes is not None:
            page.reload()
            sleep(1)
            intento += 1
            continue
        captcha_bytes_prev = captcha_bytes

        # OCR
        pre = _preprocesar_imagen(captcha_path)
        txt = _resolver_captcha(pre)

        # Limpieza de temporales
        for fp in (captcha_path, pre):
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass

        if not _texto_captcha_valido(txt):
            intento += 1
            continue

        # Enviar
        page.fill('input#formPrincipal\\:captchaSellerInput', txt)
        page.click('button#formPrincipal\\:boton-buscar')

        # Esperar a que aparezca resultado (mensaje o tabla)
        try:
            page.wait_for_selector("div#formPrincipal\\:messages, table tbody tr", timeout=WAIT_RESULT_MS)
        except PWTimeoutError:
            # No cambió nada visible: tratamos como captcha malo y reintentamos
            intento += 1
            continue

        estado = _verificar_resultado(page)
        if estado == "RESULTADO_OK":
            return True
        if estado == "CEDULA_INVALIDA":
            # Incluye el caso "No se encontraron resultados" => salimos rápido
            return False

        # CAPTCHA_INCORRECTO u otro → reintentar
        intento += 1

    # Límite de intentos alcanzado → tratamos como sin resultados para no colgarse
    return False


# -------------------- Formateo de salida --------------------

def _formatear_vertical(regs: List[Dict[str, str]]) -> str:
    """
    Bloques verticales:
    Título
    Institución de Educación Superior
    Fecha de Registro
    (una línea en blanco entre registros)
    """
    if not regs:
        return ""
    bloques = []
    for r in regs:
        b = [
            f"Título: {r.get('titulo','').strip()}",
            f"Institución de Educación Superior: {r.get('ies','').strip()}",
            f"Fecha de Registro: {r.get('fecha','').strip()}",
        ]
        bloques.append("\n".join(b))
    return "\n\n".join(bloques) + "\n"

# -------------------- API pública del módulo --------------------

def consultar(ci: str, timeout_ms: int = 45000) -> str:
    """
    Retorna:
      Títulos SENESCYT

      Fecha de Registro: ...
      Título: ...
      Institución de Educación Superior: ...

    (si hay varios, separados por una línea en blanco)
    o
      Títulos SENESCYT

      No se encontraron títulos para la cédula <ci>
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except PWTimeoutError:
            browser.close()
            return f"{NOMBRE_MODULO}\n\n(No se pudo cargar la página de SENESCYT)"

        ok = _intentar_resolver_captcha(page, ci)
        if not ok:
            browser.close()
            return f"{NOMBRE_MODULO}\n\nNo se encontraron títulos para la cédula {ci}"

        regs = _extraer_registros(page)
        browser.close()

    if not regs:
        return f"{NOMBRE_MODULO}\n\nNo se encontraron títulos para la cédula {ci}"

    cuerpo = _formatear_vertical(regs)
    return f"{NOMBRE_MODULO}\n\n{cuerpo}".rstrip()  # sin salto final extra

def consultar_o_none(ci: str, timeout_ms: int = 45000):
    """
    Igual que consultar(), pero devuelve None si no hay registros (útil para el menú).
    """
    s = consultar(ci, timeout_ms=timeout_ms) or ""
    # Si contiene al menos una línea de "Fecha de Registro:", lo consideramos válido
    return s if "Fecha de Registro:" in s else None

def search(ci: str, timeout_ms: int = 45000):
    """
    Usado por el menú:
      - Devuelve SOLO el bloque vertical (sin encabezado) si hay títulos.
      - Devuelve None si no hay resultados.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except PWTimeoutError:
            browser.close()
            return None

        ok = _intentar_resolver_captcha(page, ci)
        if not ok:
            browser.close()
            return None

        regs = _extraer_registros(page)
        browser.close()

    return _formatear_vertical(regs).rstrip() if regs else None

# -------------------- CLI --------------------

if __name__ == "__main__":
    ci = sys.argv[1] if len(sys.argv) > 1 else input("Cédula: ").strip()
    print(consultar(ci))
