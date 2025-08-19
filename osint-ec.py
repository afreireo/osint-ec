#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import sys
import argparse
import os
from osint.utils import verificar_cedula  # validador (algoritmo)

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

def is_ten_numeric(value: str) -> bool:
    v = (value or "").strip()
    return len(v) == 10 and v.isdigit()

def prompt_identificacion(predeterminada: str | None, *, show_banner: bool, version: str) -> str:
    # Validación de argumento inicial, con prioridad a 10 dígitos
    if predeterminada:
        if not is_ten_numeric(predeterminada):
            clear_screen()
            if show_banner:
                print_banner(version)
            print("Debe tener 10 caracteres numéricos.")
            print()  # espacio DESPUÉS del mensaje
            predeterminada = None
        elif not verificar_cedula(predeterminada):
            clear_screen()
            if show_banner:
                print_banner(version)
            print("Identificación inválida.")
            print()  # espacio DESPUÉS del mensaje
            predeterminada = None
        else:
            return predeterminada.strip()

    # Loop de entrada interactiva
    while True:
        try:
            val = input("Identificación: ").strip()
        except EOFError:
            val = ""
        if not is_ten_numeric(val):
            clear_screen()
            if show_banner:
                print_banner(version)
            print("Debe tener 10 caracteres numéricos")
            print()  # espacio DESPUÉS del mensaje
            continue
        if not verificar_cedula(val):
            clear_screen()
            if show_banner:
                print_banner(version)
            print("Identificación inválida")
            print()  # espacio DESPUÉS del mensaje
            continue
        return val

def main() -> int:
    args = get_args()

    # Importamos aquí para evitar dependencias circulares al inicio
    try:
        from osint.menu import main_menu, BACK_TO_HOME
    except Exception as e:
        print(f"Error importando menú: {e}", file=sys.stderr)
        return 1

    while True:
        # “Pantalla principal”
        clear_screen()
        if not args.no_banner:
            print_banner(APP_VERSION)

        ident = prompt_identificacion(
            args.identificacion,
            show_banner=(not args.no_banner),
            version=APP_VERSION
        )

        # Para iteraciones siguientes, ya no reutilizamos el -i pasado por CLI
        args.identificacion = None

        # Ir al menú; si el usuario pulsa 0, el menú retorna BACK_TO_HOME
        try:
            status = main_menu(ident)
        except TypeError:
            # Compatibilidad si el menú aún no acepta parámetro de retorno
            main_menu(ident)
            status = BACK_TO_HOME

        if status == BACK_TO_HOME:
            # Repetir el loop ⇒ volver al “home” (pedir identificación nuevamente)
            continue

        # Otros estados futuros (EXIT_APP, etc.) podrían manejarse aquí.
        # Por ahora, regresamos al home siempre.
        continue

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        raise SystemExit(2)
