# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import importlib
import pkgutil
from typing import List, Tuple
from . import __version__ as APP_VERSION

# Códigos de retorno hacia osint-ec.py
BACK_TO_HOME = "BACK_TO_HOME"
EXIT_APP = "EXIT_APP"
SELECTION_MADE = "SELECTION_MADE"  # reservado

# Orden predefinido por nombre de módulo (archivo)
PREDEFINED_ORDER = {
    "osint.modulos.nombres": 1,
    "osint.modulos.titulos": 2,
    "osint.modulos.fallecido": 3,
    "osint.modulos.juicios": 4,
    "osint.modulos.alimentos": 5,
    "osint.modulos.correos": 6,
}

BANNER = r"""
 ██████╗ ███████╗██╗███╗   ██╗████████╗   ███████╗ ██████╗
██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝   ██╔════╝██╔════╝
██║   ██║███████╗██║██╔██╗ ██║   ██║█████╗█████╗  ██║     
██║   ██║╚════██║██║██║╚██╗██║   ██║╚════╝██╔══╝  ██║     
╚██████╔╝███████║██║██║ ╚████║   ██║      ███████╗╚██████╗
 ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝      ╚══════╝ ╚═════╝
"""

def clear_screen() -> None:
    try:
        if os.name == "nt":
            os.system("cls")
        else:
            print("\033c\033[3J\033[H\033[2J", end="")
    except Exception:
        pass

def print_banner() -> None:
    print(BANNER, end="")
    print(f"\nversión: {APP_VERSION}\n")

def discover_modules() -> List[Tuple[str, str, object]]:
    """
    Escanea osint.modulos.* y devuelve lista [(mod_name, label, module)].
    Requiere que cada módulo defina NOMBRE_MODULO (str). Si no, usa el nombre del archivo.
    """
    from . import modulos as pkg

    modules: List[Tuple[str, str, object]] = []
    for _, mod_name, is_pkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        if is_pkg:
            continue
        try:
            m = importlib.import_module(mod_name)
            label = getattr(m, "NOMBRE_MODULO", None)
            if not isinstance(label, str) or not label.strip():
                label = mod_name.rsplit(".", 1)[-1]
            modules.append((mod_name, label.strip(), m))
        except Exception:
            continue

    def order_key(t: Tuple[str, str, object]):
        mod_name, label, _ = t
        weight = PREDEFINED_ORDER.get(mod_name, 10_000)
        return (weight, label.lower())

    modules.sort(key=order_key)
    return modules

def parse_selection(raw: str, total: int) -> List[int]:
    """
    Convierte '1,3,5-7' a índices 1-based. Valida formato.
    Devuelve [] si el formato es inválido o si nada cae en rango.
    """
    raw = raw.strip().lower()
    if raw in ("todos",):
        return list(range(1, total + 1))

    if not re.fullmatch(r"\s*\d+(\s*-\s*\d+)?(\s*,\s*\d+(\s*-\s*\d+)?)*\s*", raw):
        return []

    picked: List[int] = []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        if "-" in p:
            a, b = [x.strip() for x in p.split("-", 1)]
            if a.isdigit() and b.isdigit():
                start, end = int(a), int(b)
                if start <= end:
                    for x in range(start, end + 1):
                        if 1 <= x <= total and x not in picked:
                            picked.append(x)
        else:
            if p.isdigit():
                x = int(p)
                if 1 <= x <= total and x not in picked:
                    picked.append(x)
    return picked

def run_selected(mods: List[Tuple[str, str, object]], selected_idx: List[int], identificacion: str) -> None:
    """
    Placeholder del runner. Aquí lanzarás las consultas reales.
    Ctrl+C devuelve al menú (no sale de la app).
    """
    clear_screen()
    print_banner()
    print(f"Identificación: {identificacion}\n")
    print("Ejecutando módulos...\n")
    try:
        for i in selected_idx:
            mod_name, label, module = mods[i - 1]
            print(f"- {label} (mod: {mod_name}) con Identificación: {identificacion}")
            # Aquí llamarás algo como: module.search(identificacion)
        print("\n(Stub) Ejecución simulada. Presiona Enter para volver al menú...")
        input()
    except KeyboardInterrupt:
        clear_screen()
        print_banner()
        print("Ejecución interrumpida. Regresando al menú...\n")
        try:
            import time; time.sleep(0.8)
        except Exception:
            pass

def main_menu(identificacion: str) -> str:
    """
    Muestra el menú de módulos y permite elegir uno o varios.
    Retorna BACK_TO_HOME para volver a la pantalla principal de osint-ec.py.
    """
    while True:
        clear_screen()
        print_banner()
        print(f"Identificación: {identificacion}\n")

        mods = discover_modules()
        if not mods:
            print("No se encontraron módulos en osint/modulos.")
            print("\n0. Volver a la pantalla principal")
            _ = input("\nPresiona Enter para continuar...")
            return BACK_TO_HOME

        print("Seleccione módulos (ej: 1,3,5-7) o escriba 'todos':\n")
        for idx, (_, label, _) in enumerate(mods, start=1):
            print(f"  {idx}. {label}")
        print("\n  0. Volver a la pantalla principal")

        try:
            raw = input("\nMódulos: ").strip().lower()
        except KeyboardInterrupt:
            clear_screen()
            print_banner()
            print("Selección interrumpida. Intenta de nuevo.\n")
            continue

        if raw in ("0", "volver", "back"):
            return BACK_TO_HOME

        selected = parse_selection(raw, len(mods))
        if not selected:
            clear_screen()
            print_banner()
            print("Formato inválido. Use números separados por coma, rangos (2-4) o 'todos'.")
            print()
            continue

        # 🚀 Arrancar directamente sin confirmación
        run_selected(mods, selected, identificacion)
        # Al terminar (o Ctrl+C), vuelve al menú (loop continúa)
