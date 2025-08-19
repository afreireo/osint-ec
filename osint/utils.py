# osint/utils.py

def verificar_cedula(cedula: str) -> bool:
    """
    Valida cédula ecuatoriana de persona natural (10 dígitos).
    Reglas:
      - Longitud 10 y solo dígitos.
      - Provincia 01..24 o 30.
      - Tercer dígito < 6.
      - Dígito verificador (módulo 10) con coeficientes 2,1,2,1,2,1,2,1,2.
    """
    if not isinstance(cedula, str):
        return False
    cedula = cedula.strip()
    if len(cedula) != 10 or not cedula.isdigit():
        return False

    provincia = int(cedula[0:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        return False

    tercer = int(cedula[2])
    if tercer >= 6:
        return False

    coef = (2, 1, 2, 1, 2, 1, 2, 1, 2)
    total = 0
    for i in range(9):
        prod = int(cedula[i]) * coef[i]
        if prod >= 10:
            prod -= 9
        total += prod

    digito_esperado = (10 - (total % 10)) % 10
    return digito_esperado == int(cedula[9])

def print_table(rows, title: str | None = None) -> None:
    """
    Imprime una lista de dicts como tabla ASCII simple.
    Acepta también un dict (se convierte a [dict]).
    """
    if rows is None:
        print("(sin resultados)\n")
        return
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        print("(sin resultados)\n")
        return
    # Columnas: unión de keys en orden de aparición
    cols: List[str] = []
    for r in rows:
        if isinstance(r, dict):
            for k in r.keys():
                if k not in cols:
                    cols.append(str(k))
    if not cols:
        print("(sin resultados)\n")
        return
    # Anchos
    widths = {c: len(c) for c in cols}
    for r in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(r.get(c, ""))))
    # Render
    if title:
        print(title)
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        line = " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
