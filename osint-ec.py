#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import sys
import argparse
import os
from osint.utils import verificar_cedula  # ← ahora desde utils

try:
    from osint import __version__ as APP_VERSION
except Exception:
    APP_VERSION = "0.1.0"

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

def print_banner(version: str) -> None:
    print(BANNER, end="")
    print(f"\nversión: {version}\n")

def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="osint-ec",
        description="Framework ligero de OSINT (Ecuador) para consola."
    )
    parser.add_argument("-i", "--id", dest="identificacion", default=None,
                        help="Identificación inicial (10 dígitos).")
    parser.add_argument("--no-banner", action="store_true",
                        help="No mostrar el banner ASCII al iniciar.")
    return parser.parse_args()

def prompt_identificacion(predeterminada: str | None, *, show_banner: bool, version: str) -> str:
    # Si vino por argumento y es inválida, limpiar y avisar
    if predeterminada and not verificar_cedula(predeterminada):
        clear_screen()
        if show_banner:
            print_banner(version)
        print()  # espacio antes del mensaje
        print("Identificación inválida. Debe ser una cédula válida de 10 dígitos.")
        predeterminada = None

    if predeterminada and verificar_cedula(predeterminada):
        return predeterminada.strip()

    while True:
        try:
            val = input("Identificación: ").strip()
        except EOFError:
            val = ""
        if verificar_cedula(val):
            return val
        # Entrada inválida: limpiar pantalla y reimprimir banner + mensaje
        clear_screen()
        if show_banner:
            print_banner(version)
        print()  # espacio antes del mensaje
        print("Identificación inválida. Debe ser una cédula válida de 10 dígitos.")

def main() -> int:
    args = get_args()
    clear_screen()
    if not args.no_banner:
        print_banner(APP_VERSION)

    ident = prompt_identificacion(args.identificacion, show_banner=(not args.no_banner), version=APP_VERSION)

    # Delegar al menú
    try:
        from osint.menu import main_menu
    except Exception as e:
        print(f"Error importando menú: {e}", file=sys.stderr)
        return 1

    try:
        main_menu(ident)
    except TypeError:
        main_menu()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        raise SystemExit(2)
