# osint/modulos/delitos.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import List, Optional

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False

NOMBRE_MODULO = "Noticias de delitos"

BASE_URL = "https://www.gestiondefiscalias.gob.ec/siaf/comunes/noticiasdelito/info_mod.php"
REFERER = "https://www.gestiondefiscalias.gob.ec/siaf/informacion/web/noticiasdelito/index.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-EC,es;q=0.9,en;q=0.8",
    "Referer": REFERER,
    "Connection": "keep-alive",
}

# RegEx auxiliares (fallback sin bs4)
_RE_TABLE_SPLIT = re.compile(r"<th[^>]*>\s*NOTICIA DEL DELITO\b.*?</th>", re.IGNORECASE | re.DOTALL)
_RE_LUGAR_FECHA = re.compile(
    r"LUGAR\s*</td>\s*<td[^>]*>\s*(?P<lugar>.*?)\s*</td>\s*"
    r"<td[^>]*>\s*FECHA\s*</td>\s*<td[^>]*>\s*(?P<fecha>\d{4}-\d{2}-\d{2})\s*</td>",
    re.IGNORECASE | re.DOTALL,
)
_RE_DELITO = re.compile(
    r"DELITO:\s*</td>\s*<td[^>]*>\s*(?P<delito>.*?)\s*</td>",
    re.IGNORECASE | re.DOTALL,
)

def _php_businfo(ci: str) -> str:
    """Construye a:1:{i:0;s:<len>:"<ci>";}"""
    ci_norm = (ci or "").strip()
    return f'a:1:{{i:0;s:{len(ci_norm)}:"{ci_norm}";}}'

def _limpiar_texto(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _limpiar_delito(s: str) -> str:
    # Quita el código entre paréntesis al final: p.ej. "ROBO(4664)" -> "ROBO"
    s = _limpiar_texto(s)
    s = re.sub(r"\s*\(\d+\)\s*$", "", s)
    return s

def _parse_con_bs4(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    resultados: List[str] = []

    for tabla in soup.find_all("table"):
        th = tabla.find("th")
        if not th:
            continue
        titulo = th.get_text(" ", strip=True)
        if "NOTICIA DEL DELITO" not in (titulo or ""):
            continue

        lugar = fecha = delito = None

        for tr in tabla.find_all("tr"):
            celdas = tr.find_all("td")
            if not celdas:
                continue
            txts = [c.get_text(" ", strip=True) for c in celdas]
            for i, t in enumerate(txts):
                t_upper = (t or "").upper()
                if t_upper.startswith("LUGAR") and i + 1 < len(txts):
                    lugar = txts[i + 1]
                if t_upper.startswith("FECHA") and i + 1 < len(txts):
                    fecha = txts[i + 1]
                if t_upper.startswith("DELITO:") and i + 1 < len(txts):
                    delito = txts[i + 1]

        if fecha and lugar and delito:
            fecha = _limpiar_texto(fecha)
            lugar = _limpiar_texto(lugar)
            delito = _limpiar_delito(delito)
            resultados.append(f"{fecha}: {delito}, {lugar}")

    return resultados

def _parse_con_regex(html: str) -> List[str]:
    resultados: List[str] = []
    partes = _RE_TABLE_SPLIT.split(html)
    for parte in partes[1:]:
        lugar = fecha = delito = None
        m1 = _RE_LUGAR_FECHA.search(parte)
        if m1:
            lugar = _limpiar_texto(m1.group("lugar"))
            fecha = _limpiar_texto(m1.group("fecha"))
        m2 = _RE_DELITO.search(parte)
        if m2:
            delito = _limpiar_delito(m2.group("delito"))
        if fecha and lugar and delito:
            resultados.append(f"{fecha}: {delito}, {lugar}")
    return resultados

def _parse_noticias(html: str) -> List[str]:
    if _HAS_BS4:
        res = _parse_con_bs4(html)
        if res:
            return res
    return _parse_con_regex(html)

def consultar(ci: str, timeout: int = 30) -> List[str]:
    """Devuelve lista de 'YYYY-MM-DD: DELITO, LUGAR'."""
    params = {"businfo": _php_businfo(ci)}
    r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=timeout)
    r.raise_for_status()
    r.encoding = "utf-8"
    return _parse_noticias(r.text)

def search(ci: str) -> Optional[List[str]]:
    """
    Integración con menú:
    - List[str] con 'fecha: delito, lugar'
    - None si no hay resultados o error
    """
    try:
        filas = consultar(ci)
    except Exception:
        return None
    return filas if filas else None


if __name__ == "__main__":
    import sys
    ci = sys.argv[1] if len(sys.argv) > 1 else "0940436892"
    try:
        items = consultar(ci)
        if not items:
            print("(sin resultados)")
        else:
            for line in items:
                print(line)
    except Exception as e:
        print(f"(error) {e}")
