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
