# osint/modulos/supa.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import re
import json
import unicodedata
from typing import List, Dict, Optional, Tuple
from xml.etree import ElementTree as ET
from html import unescape as html_unescape

import requests
from bs4 import BeautifulSoup

NOMBRE_MODULO = "SUPA Pensiones"

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

BASE = "https://supa.funcionjudicial.gob.ec"
CONSULTA_URL = f"{BASE}/pensiones/publico/consulta.jsf"

HEADERS_GET = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HEADERS_POST = {
    "User-Agent": HEADERS_GET["User-Agent"],
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE,
    "Referer": CONSULTA_URL,
    "Connection": "keep-alive",
}

TIMEOUT = 30

# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------

def _format_vertical(rows: List[Dict[str, Optional[str]]]) -> str:
    """
    Formatea las filas en vertical, con un bloque por fila y
    una línea en blanco entre bloques.
    """
    if not rows:
        return ""
    label_order = [
        ("codigo_tarjeta", "Codigo Tarjeta"),
        ("dependencia_jurisdiccional", "Dependencia Jurisdiccional"),
        ("representante_legal", "Representante legal"),
        ("obligado_principal", "Obligado principal"),
        ("pension_actual", "Pension actual"),
        ("total_pendiente", "Total pendiente"),
    ]
    blocks = []
    for r in rows:
        lines = []
        for key, label in label_order:
            val = _normalize_text(r.get(key) or "")
            lines.append(f"{label}: {val}")
        blocks.append("\n".join(lines))
    # línea en blanco entre entradas
    return "\n\n".join(blocks) + "\n"

def _normalize_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _get_viewstate_and_formid(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    vs = soup.find("input", {"name": "javax.faces.ViewState"})
    viewstate = vs["value"] if vs and vs.has_attr("value") else ""
    form = soup.find("form")
    form_id = form.get("id", "form") if form else "form"
    return viewstate, form_id

def _extract_partial_html_and_viewstate(xml_text: str, update_id: str) -> Tuple[str, Optional[str]]:
    """
    Extrae el fragmento HTML del <update id="..."> y el nuevo ViewState usando ElementTree.
    JSF suele poner el HTML escapado dentro de texto → desescapamos.
    """
    raw = (xml_text or "").strip()
    if not raw:
        return "", None

    start = raw.find("<partial-response")
    if start != -1:
        raw = raw[start:]

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "", None

    fragment = ""
    new_vs = None
    for upd in root.iterfind(".//update"):
        uid = upd.get("id") or ""
        content = "".join(upd.itertext())  # contenido textual (posiblemente escapado)
        if uid == update_id:
            fragment = html_unescape(content)
        if uid == "javax.faces.ViewState":
            new_vs = (content or "").strip()

    return fragment, new_vs

def _extract_partial_html(xml_text: str, update_id: str) -> str:
    frag, _ = _extract_partial_html_and_viewstate(xml_text, update_id)
    return frag

# ---------------------------------------------------------------------
# Parseo de tabla principal
# ---------------------------------------------------------------------

def _parse_table_rows(results_html: str) -> List[Dict]:
    """
    Devuelve filas básicas desde el resultado principal, más el id de botón de detalle para enriquecer.
    """
    if not results_html:
        return []
    hsoup = BeautifulSoup(results_html, "html.parser")
    wrapper = hsoup.select_one("div.ui-datatable-tablewrapper table")
    if not wrapper:
        return []
    rows = []
    for tr in wrapper.select("tbody tr[role='row']"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        codigo_tarjeta = _normalize_text(tds[0].get_text(strip=True))
        dependencia = _normalize_text(tds[2].get_text(strip=True))

        # Intervinientes (representante legal / obligado principal)
        inter_dict = {"Representante Legal": None, "Obligado principal": None}
        inter_tbl = tds[4].find("table")
        if inter_tbl:
            for r in inter_tbl.select("tr"):
                cols = r.find_all(["td", "th"])
                if len(cols) >= 2:
                    label = _normalize_text(cols[0].get_text(strip=True)).replace(":", "")
                    val = _normalize_text(cols[1].get_text(" ", strip=True))
                    if "Representante Legal" in label:
                        inter_dict["Representante Legal"] = val or None
                    elif "Obligado principal" in label:
                        inter_dict["Obligado principal"] = val or None

        detalle_button = tds[5].find("button")
        detalle_button_id = detalle_button.get("id") if detalle_button else None

        rows.append({
            "codigo_tarjeta": codigo_tarjeta,
            "dependencia_jurisdiccional": dependencia,
            "representante_legal": inter_dict["Representante Legal"],
            "obligado_principal": inter_dict["Obligado principal"],
            "detalle_button_id": detalle_button_id,  # interno para pedir detalle
            "pension_actual": None,                  # se rellenará
            "total_pendiente": None,                 # se rellenará
        })
    return rows

# ---------------------------------------------------------------------
# Detalle -> "Pensión actual"
# ---------------------------------------------------------------------

def _extract_pension_actual_from_detalle_html(detalle_html: str) -> Optional[str]:
    def _norm_money(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        m = re.search(r"\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})", value.replace("\xa0", " "))
        return m.group(0) if m else None

    s = BeautifulSoup(detalle_html, "html.parser")

    # Buscar en tablas clave/valor
    for tr in s.select("table tr"):
        tds = tr.find_all("td")
        if len(tds) >= 2:
            clave = _normalize_text(tds[0].get_text(" ", strip=True)).rstrip(":")
            if re.search(r"pensi[oó]n\s+actual", clave, re.IGNORECASE):
                raw_val = _normalize_text(tds[1].get_text(" ", strip=True))
                return _norm_money(raw_val) or raw_val or None

    # Etiqueta <label>Pensión actual:</label>
    for tag in s.find_all(string=re.compile(r"pensi[oó]n\s+actual", re.IGNORECASE)):
        parent = tag.parent
        if parent and parent.name == "label":
            td_parent = parent.find_parent("td")
            if td_parent:
                sib = td_parent.find_next_sibling("td")
                if sib:
                    raw_val = _normalize_text(sib.get_text(" ", strip=True))
                    return _norm_money(raw_val) or raw_val or None

    # Fallback regex crudo
    m = re.search(
        r"pensi[oó]n\s+actual\s*:?.{0,200}?(\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
        detalle_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        return _normalize_text(m.group(1))

    return None

def _consultar_detalle(session: requests.Session, viewstate: str, form_id: str,
                       cedula: Optional[str],
                       button_id: Optional[str]) -> Tuple[str, str]:
    """
    Emula el click del botón 'Ver' y, si falla, intenta contentLoad del panel de detalle.
    Devuelve (detalle_html, viewstate_actualizado)
    """
    url = CONSULTA_URL
    vs = viewstate

    # Intento 1: botón 'Ver'
    if button_id:
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": button_id,
            "javax.faces.partial.execute": button_id,
            "javax.faces.partial.render": "form:dDetalle",
            button_id: button_id,
            form_id: form_id,
            "javax.faces.ViewState": vs,
        }
        r = session.post(url, headers=HEADERS_POST, data=payload, timeout=TIMEOUT)
        r.raise_for_status()
        detalle_html, new_vs = _extract_partial_html_and_viewstate(r.text, "form:dDetalle")
        if new_vs:
            vs = new_vs
        if _extract_pension_actual_from_detalle_html(detalle_html):
            return detalle_html, vs

    # Intento 2: contentLoad del detalle
    payload = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "form:dDetalle",
        "javax.faces.partial.execute": "form:dDetalle",
        "javax.faces.partial.render": "form:dDetalle",
        "form:dDetalle": "form:dDetalle",
        "form:dDetalle_contentLoad": "true",
        form_id: form_id,
        "javax.faces.ViewState": vs,
    }
    if cedula:
        payload[f"{form_id}:t_texto_cedula"] = cedula
    payload[f"{form_id}:s_criterio_busqueda"] = "Seleccione..."
    payload[f"{form_id}:t_texto"] = ""

    r = session.post(url, headers=HEADERS_POST, data=payload, timeout=TIMEOUT)
    r.raise_for_status()
    detalle_html, new_vs = _extract_partial_html_and_viewstate(r.text, "form:dDetalle")
    if new_vs:
        vs = new_vs
    return detalle_html, vs

# ---------------------------------------------------------------------
# Pendientes -> "TOTAL PENDIENTE"
# ---------------------------------------------------------------------

def _extract_total_pendiente_from_pendientes_html(pend_html: str) -> Optional[str]:
    """
    Intenta localizar 'TOTAL PENDIENTE' o 'Total pensiones más intereses'.
    Devuelve dinero normalizado '$12,345.67' si es posible.
    """
    def _norm_money(txt: str) -> Optional[str]:
        t = _normalize_text(txt)
        if not t:
            return None
        m = re.search(r"\$?\s*([\d.,]+)", t)
        if not m:
            return None
        raw = m.group(1)
        if "," in raw and "." in raw:
            return f"${raw}"
        try:
            val = float(raw.replace(",", ""))
            return f"${val:,.2f}"
        except Exception:
            return f"${raw}"

    s = BeautifulSoup(pend_html, "html.parser")

    # A) 'TOTAL PENDIENTE'
    for lab in s.find_all("label"):
        text = _normalize_text(lab.get_text(" ", strip=True)).rstrip(":")
        if re.search(r"TOTAL\s+PENDIENTE", text, re.IGNORECASE):
            td = lab.find_parent("td")
            if td:
                val_td = td.find_next_sibling("td")
                if val_td:
                    val_tag = val_td.find("span") or val_td
                    val = _norm_money(val_tag.get_text(" ", strip=True))
                    if val:
                        return val

    # B) 'Total pensiones más intereses'
    for lab in s.find_all("label"):
        text = _normalize_text(lab.get_text(" ", strip=True)).rstrip(":")
        if re.search(r"Total\s+pensiones\s+m[aá]s\s+intereses", text, re.IGNORECASE):
            td = lab.find_parent("td")
            if td:
                val_td = td.find_next_sibling("td")
                if val_td:
                    val = _norm_money(val_td.get_text(" ", strip=True))
                    if val:
                        return val

    # C) tfoot última cifra a la derecha
    tfoot = s.find("tfoot")
    if tfoot:
        for td in tfoot.find_all("td"):
            txt = _normalize_text(td.get_text(" ", strip=True))
            if re.fullmatch(r"[\d.,]+", txt):
                val = _norm_money(txt)
                if val:
                    return val

    # D) Regex crudo
    m = re.search(
        r"TOTAL\s+PENDIENTE\s*:\s*</label>\s*</td>\s*<td[^>]*>\s*(?:<span[^>]*>)?\s*([^<]+?)\s*(?:</span>)?\s*</td>",
        pend_html, flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        return _norm_money(m.group(1))
    m2 = re.search(
        r"Total\s+pensiones\s+m[aá]s\s+intereses\s*:\s*</label>\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>",
        pend_html, flags=re.IGNORECASE | re.DOTALL
    )
    if m2:
        return _norm_money(m2.group(1))

    return None

def _sum_valor_deuda_from_table(pend_html: str) -> Optional[str]:
    """Suma todas las celdas 'Valor de deuda' del tbody (fallback)."""
    s = BeautifulSoup(pend_html, "html.parser")
    table = s.select_one("div.ui-datatable-tablewrapper table")
    if not table:
        return None

    # Índice de columna 'Valor de deuda'
    head = table.find("thead")
    col_idx = None
    if head:
        ths = head.find_all("th")
        for i, th in enumerate(ths):
            t = _normalize_text(th.get_text(" ", strip=True))
            if re.search(r"Valor\s+de\s+deuda", t, re.IGNORECASE):
                col_idx = i
                break
    if col_idx is None:
        return None

    total = 0.0
    rows = 0
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) <= col_idx:
            continue
        txt = _normalize_text(tds[col_idx].get_text(" ", strip=True))
        m = re.search(r"([\d.,]+)", txt)
        if m:
            num = float(m.group(1).replace(",", ""))
            total += num
            rows += 1
    if rows == 0:
        return None
    return f"${total:,.2f}"

def _consultar_pendientes(session: requests.Session, viewstate: str, form_id: str,
                          cedula: Optional[str]) -> Tuple[str, str]:
    """
    Click en 'Ver movimientos pendientes' y, si falla, contentLoad explícito.
    Devuelve (pendientes_html, viewstate_actualizado).
    """
    url = CONSULTA_URL
    vs = viewstate

    def _post(update_id: str, data: dict) -> Tuple[str, Optional[str]]:
        r = session.post(url, headers=HEADERS_POST, data=data, timeout=TIMEOUT)
        r.raise_for_status()
        frag, new_vs = _extract_partial_html_and_viewstate(r.text, update_id)
        return frag, new_vs

    # Paso A: activar pestaña
    try:
        payload_tab = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "form:ta_co_movimientosPendientes",
            "javax.faces.partial.execute": "form:ta_co_movimientosPendientes",
            "javax.faces.partial.render": "form:d_pendientes",
            "form:ta_co_movimientosPendientes": "form:ta_co_movimientosPendientes",
            form_id: form_id,
            "javax.faces.ViewState": vs,
        }
        if cedula:
            payload_tab[f"{form_id}:t_texto_cedula"] = cedula
        payload_tab[f"{form_id}:s_criterio_busqueda"] = "Seleccione..."
        payload_tab[f"{form_id}:t_texto"] = ""

        pend_html, new_vs = _post("form:d_pendientes", payload_tab)
        if new_vs:
            vs = new_vs
        if "TOTAL PENDIENTE" in pend_html.upper():
            return pend_html, vs
    except Exception:
        pass

    # Paso B: contentLoad
    payload_load = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "form:d_pendientes",
        "javax.faces.partial.execute": "form:d_pendientes",
        "javax.faces.partial.render": "form:d_pendientes",
        "form:d_pendientes": "form:d_pendientes",
        "form:d_pendientes_contentLoad": "true",
        form_id: form_id,
        "javax.faces.ViewState": vs,
    }
    if cedula:
        payload_load[f"{form_id}:t_texto_cedula"] = cedula
    payload_load[f"{form_id}:s_criterio_busqueda"] = "Seleccione..."
    payload_load[f"{form_id}:t_texto"] = ""

    pend_html, new_vs = _post("form:d_pendientes", payload_load)
    if new_vs:
        vs = new_vs
    return pend_html, vs

# ---------------------------------------------------------------------
# Búsqueda principal (cruda) y adaptadores
# ---------------------------------------------------------------------

def search_raw(identificacion: str) -> List[Dict[str, Optional[str]]]:
    """
    Devuelve una lista de dicts con SOLO:
      codigo_tarjeta, dependencia_jurisdiccional,
      representante_legal, obligado_principal,
      pension_actual, total_pendiente
    """
    try:
        with requests.Session() as s:
            # GET inicial
            r = s.get(CONSULTA_URL, headers=HEADERS_GET, timeout=TIMEOUT)
            r.raise_for_status()
            viewstate, form_id = _get_viewstate_and_formid(r.text)

            # POST de búsqueda por cédula
            payload = {
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": f"{form_id}:b_buscar_cedula",
                "javax.faces.partial.execute": "@all",
                "javax.faces.partial.render": f"{form_id}:pResultado panelMensajes {form_id}:pFiltro",
                f"{form_id}:b_buscar_cedula": f"{form_id}:b_buscar_cedula",
                form_id: form_id,
                f"{form_id}:t_texto_cedula": identificacion,
                f"{form_id}:s_criterio_busqueda": "Seleccione...",
                f"{form_id}:t_texto": "",
                "javax.faces.ViewState": viewstate,
            }
            r2 = s.post(CONSULTA_URL, headers=HEADERS_POST, data=payload, timeout=TIMEOUT)
            r2.raise_for_status()

            # Actualizar viewstate si vino en el partial
            _, new_vs = _extract_partial_html_and_viewstate(r2.text, f"{form_id}:pResultado")
            if new_vs:
                viewstate = new_vs

            # Parseo tabla principal
            results_html = _extract_partial_html(r2.text, f"{form_id}:pResultado")
            filas = _parse_table_rows(results_html)

            # Enriquecer cada fila con pensión actual y total pendiente
            for fila in filas:
                btn_id = fila.get("detalle_button_id")
                try:
                    detalle_html, viewstate = _consultar_detalle(
                        session=s, viewstate=viewstate, form_id=form_id,
                        cedula=identificacion, button_id=btn_id
                    )
                    fila["pension_actual"] = _extract_pension_actual_from_detalle_html(detalle_html)
                except Exception:
                    pass

                try:
                    pend_html, viewstate = _consultar_pendientes(
                        session=s, viewstate=viewstate, form_id=form_id,
                        cedula=identificacion
                    )
                    total = _extract_total_pendiente_from_pendientes_html(pend_html)
                    if not total:
                        total = _sum_valor_deuda_from_table(pend_html)
                    fila["total_pendiente"] = total
                except Exception:
                    pass

                # limpiar campo interno
                fila.pop("detalle_button_id", None)

            # Filtrar a SOLO los campos solicitados
            wanted = {
                "codigo_tarjeta",
                "dependencia_jurisdiccional",
                "representante_legal",
                "obligado_principal",
                "pension_actual",
                "total_pendiente",
            }
            clean_rows: List[Dict[str, Optional[str]]] = []
            for f in filas:
                clean_rows.append({k: f.get(k) for k in wanted})

            return clean_rows
    except requests.RequestException:
        return []
    except Exception:
        return []

def search(identificacion: str) -> Optional[str]:
    """
    Devuelve un string en formato vertical con:
    Codigo Tarjeta, Dependencia Jurisdiccional, Representante legal,
    Obligado principal, Pension actual, Total pendiente.
    """
    rows = search_raw(identificacion)
    formatted = _format_vertical(rows)
    return formatted if formatted.strip() else None

# ---------------------------------------------------------------------
# CLI de prueba (ejecución directa)
# ---------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Consulta SUPA (pensiones) por cédula. Modo vertical por defecto o JSON con --json."
    )
    parser.add_argument("--cedula", "-c", required=True, help="Cédula/Identificación a consultar.")
    parser.add_argument("--json", action="store_true", help="Imprimir la salida como JSON.")
    parser.add_argument("--debug", action="store_true", help="Mensajes de depuración a stderr.")
    args = parser.parse_args()

    try:
        if args.json:
            rows = search_raw(args.cedula)
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            out = search(args.cedula) or "(sin resultados)"
            print(out, end="")  # ya incluye salto al final en _format_vertical
    except KeyboardInterrupt:
        if args.debug:
            print("\n[DEBUG] Interrumpido por el usuario.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        if args.debug:
            print(f"[DEBUG] Error: {e}", file=sys.stderr)
        print("(error en la consulta)")
        sys.exit(1)
