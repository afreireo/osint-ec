# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import html
import urllib.parse
from typing import Optional, Tuple, List
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

URL_FORM   = "https://siirs.registrosocial.gob.ec/pages/publico/requerimiento.jsf"
FORM_ID    = "frmIngreso"
INPUT_ID   = "frmIngreso:txtCedula"
RENDER_IDS = [
    "frmIngreso:txtCedula", "frmIngreso", "frmIngreso:messCuen", "msgs2",
    "frmIngreso:lblUbicacion", "frmValidacion", "frmIngreso:checkMensaje"
]

AJAX_HEADERS = {
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0",
}

def _abs_url(base_url: str, action: str) -> str:
    return urllib.parse.urljoin(base_url, action or "")

def _parse_form_and_viewstate(html_text: str, form_id: str):
    soup = BeautifulSoup(html_text, "html.parser")
    form = soup.find("form", id=form_id)
    if not form:
        raise RuntimeError(f"No se encontró <form id='{form_id}'>")
    fields = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "").lower()
        if itype in ("checkbox","radio"):
            if inp.has_attr("checked"):
                fields[name] = inp.get("value","on")
        else:
            fields[name] = inp.get("value","")
    if "javax.faces.ViewState" not in fields:
        vs = form.find(id="javax.faces.ViewState")
        if vs and vs.has_attr("value"):
            fields["javax.faces.ViewState"] = vs["value"]
    if "javax.faces.ViewState" not in fields:
        raise RuntimeError("No se pudo extraer javax.faces.ViewState.")
    return fields, form.get("action","")

def _build_ajax_payload(base_fields, form_id, input_id, value, render_ids):
    data = dict(base_fields)
    data.update({
        form_id: form_id,
        input_id: value,
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": input_id,
        "javax.faces.partial.execute": input_id,
        "javax.faces.partial.render": " ".join(render_ids),
        "javax.faces.behavior.event": "valueChange",
        "javax.faces.partial.event": "change",
    })
    return data

def _extract_updates_html(xml_text: str) -> List[Tuple[str,str]]:
    raw = xml_text.strip()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        start = raw.find("<partial-response")
        if start == -1:
            raise
        root = ET.fromstring(raw[start:])
    out: List[Tuple[str,str]] = []
    for upd in root.iterfind(".//update"):
        uid = upd.get("id") or ""
        upd_xml = ET.tostring(upd, encoding="unicode")
        inner_xml = upd_xml.split(">", 1)[1].rsplit("</update>", 1)[0]
        inner_html = html.unescape(inner_xml)
        out.append((uid, inner_html))
    return out

def _pick_html_chunks(updates: List[Tuple[str,str]], prefer_ids: List[str]) -> List[str]:
    chunks: List[str] = []
    wanted = set(prefer_ids)
    for uid, inner in updates:
        if uid in wanted:
            chunks.append(inner)
    if not chunks:
        chunks = [inner for _, inner in updates]
    return chunks

def _text_of_id(soup: BeautifulSoup, id_: str) -> Optional[str]:
    el = soup.find(id=id_)
    if el:
        t = el.get_text(" ").strip()
        return t if t else None
    return None

def _find_by_label(soup: BeautifulSoup, label_regex: str) -> Optional[str]:
    lab = soup.find(string=re.compile(label_regex, re.I))
    if lab:
        td = getattr(lab, "parent", None)
        if td:
            sib = td.find_next(["td","span","div"])
            if sib:
                txt = sib.get_text(" ").strip()
                if txt:
                    return txt
    text = soup.get_text("\n")
    m = re.search(label_regex + r"\s*:\s*([^\n\r]+)", text, re.I)
    return m.group(1).strip() if m else None

def consultar(identificacion: str, timeout: int = 25) -> Optional[str]:
    """
    Devuelve SOLO el nombre completo (str) o None si no hay datos.
    """
    try:
        with requests.Session() as s:
            r0 = s.get(URL_FORM, timeout=timeout, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            r0.raise_for_status()
            fields, action = _parse_form_and_viewstate(r0.text, FORM_ID)
            post_url = _abs_url(r0.url, action)

            headers = dict(AJAX_HEADERS)
            headers["Referer"] = r0.url
            pu = urllib.parse.urlparse(r0.url)
            headers["Origin"] = f"{pu.scheme}://{pu.netloc}"

            data = _build_ajax_payload(fields, FORM_ID, INPUT_ID, identificacion, RENDER_IDS)
            r1 = s.post(post_url, data=data, headers=headers, timeout=timeout)
            r1.raise_for_status()

            updates = _extract_updates_html(r1.text)
            chunks = _pick_html_chunks(updates, [FORM_ID])

            nombre_completo: Optional[str] = None
            nombres = apellidos = None

            for chunk in chunks:
                soup = BeautifulSoup(chunk, "html.parser")
                # 1) nombre completo directo
                nombre_completo = _text_of_id(soup, "frmIngreso:lblName") or nombre_completo
                # 2) si no viene junto, armarlo por partes
                if not nombre_completo:
                    if not nombres:
                        nombres = _text_of_id(soup, "frmIngreso:lblNombres") or _find_by_label(soup, r"\bNombres?\b")
                    if not apellidos:
                        apellidos = _text_of_id(soup, "frmIngreso:lblApellidos") or _find_by_label(soup, r"\bApellidos?\b")
                if nombre_completo or (nombres or apellidos):
                    break

            def _clean(x: Optional[str]) -> Optional[str]:
                if not x:
                    return x
                x = re.sub(r"\s+", " ", x).strip()
                return x or None

            nombre_completo = _clean(nombre_completo)
            if not nombre_completo:
                nombres = _clean(nombres)
                apellidos = _clean(apellidos)
                if nombres or apellidos:
                    nombre_completo = " ".join([p for p in [nombres, apellidos] if p]) or None

            return nombre_completo or None

    except requests.RequestException:
        return None
    except Exception:
        return None
