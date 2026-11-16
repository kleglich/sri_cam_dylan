"""Periodicidad de las suscripciones (RF-01, RF-09, RN-11).

En el listado de repartidores la periodicidad se escribe junto al nombre:
sin anotación = todos los días; «D» = domingo; «S-D» = sábado y domingo;
«L-V» = lunes a viernes; o listas como «miércoles, sábado y domingo».

Se guarda como una máscara de 7 caracteres (lunes a domingo), por ejemplo
"0000011" para sábado y domingo, de modo que en SQL basta con
``substr(periodicidad, dia + 1, 1) = '1'`` para saber si hay entrega.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

DIARIA = "1111111"
LETRAS = {"L": 0, "M": 1, "MI": 2, "X": 2, "J": 3, "V": 4, "S": 5, "D": 6}
NOMBRES = {"LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3, "VIERNES": 4, "SABADO": 5, "DOMINGO": 6}
NOMBRES_DIA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
OPCIONES = ("Diaria", "L-V", "L-S", "S-D", "D")

_DIA = r"(?:LUNES|MARTES|MIERCOLES|JUEVES|VIERNES|SABADO|DOMINGO)"
_LETRA = r"(?:MI|[LMXJVSD])"


def _plano(texto: str) -> str:
    """Mayúsculas sin tildes conservando la longitud (para cortar el texto original)."""
    return "".join(unicodedata.normalize("NFKD", c)[0] for c in texto).upper()


def _mascara(dias: set[int]) -> str:
    return "".join("1" if d in dias else "0" for d in range(7))


def parsear(texto: str) -> str | None:
    """Convierte una anotación de periodicidad en máscara; None si no se reconoce."""
    t = re.sub(r"\s+", " ", _plano(texto or "")).strip(" .")
    if t in ("", "DIARIA", "DIARIO", "TODOS LOS DIAS", "L-D"):
        return DIARIA
    rango = re.fullmatch(rf"({_LETRA})\s*-\s*({_LETRA})|({_DIA}) A ({_DIA})", t)
    if rango:
        a, b = (LETRAS[rango[1]], LETRAS[rango[2]]) if rango[1] else (NOMBRES[rango[3]], NOMBRES[rango[4]])
        return _mascara(set(range(a, b + 1))) if a < b else None
    partes = [p for p in re.split(r"\s*(?:,|/|\bY\b)\s*|\s+", t) if p]
    dias = set()
    for parte in partes:
        if parte in NOMBRES:
            dias.add(NOMBRES[parte])
        elif parte in LETRAS:
            dias.add(LETRAS[parte])
        else:
            return None
    return _mascara(dias) if dias else None


def separar_nombre(nombre: str) -> tuple[str, str, bool]:
    """Separa la periodicidad escrita junto al nombre.

    Devuelve (nombre sin la anotación, máscara, reconocida). Si al final hay
    algo con forma de código que no se entiende, se devuelve la máscara diaria
    con ``reconocida=False`` para que la Gerencia lo revise.
    """
    original = re.sub(r"\s+", " ", (nombre or "")).strip()
    plano = _plano(original)
    patrones = (
        r"\s*\(([^()]*)\)$",  # JUAN PÉREZ (S-D)
        rf"[\s,\-]+((?:{_DIA}(?:\s*,\s*|\s+Y\s+|\s+A\s+|\s+)?)+)$",  # ... MIÉRCOLES, SÁBADO Y DOMINGO
        rf"\s+(?:-\s+)?({_LETRA}(?:\s*-\s*{_LETRA})?)$",  # JUAN PÉREZ S-D / JUAN PÉREZ - D
    )
    for patron in patrones:
        encontrado = re.search(patron, plano)
        if encontrado:
            mascara = parsear(encontrado.group(1))
            base = original[: encontrado.start()].strip(" -,")
            if base:
                return base, mascara or DIARIA, mascara is not None
    if re.search(r"\s[A-Z]{1,3}(?:-[A-Z]{1,3})+$", plano):  # código desconocido, p. ej. «L-X-V»
        return original, DIARIA, False
    return original, DIARIA, True


def etiqueta(mascara: str) -> str:
    """Texto legible de una máscara: Diaria, L-V, S-D, D o la lista de días."""
    if mascara == DIARIA:
        return "Diaria"
    dias = [i for i, c in enumerate(mascara) if c == "1"]
    if not dias:
        return "Sin días"
    letras = "LMXJVSD"
    if len(dias) > 1 and dias == list(range(dias[0], dias[-1] + 1)) and dias[0] != 2 and dias[-1] != 2:
        return f"{letras[dias[0]]}-{letras[dias[-1]]}"
    if len(dias) == 1 and dias[0] in (5, 6):
        return letras[dias[0]]
    nombres = [NOMBRES_DIA[d] for d in dias]
    texto = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
    return texto.capitalize()


def programado(mascara: str, fecha: date) -> bool:
    return mascara[fecha.weekday()] == "1"


def solo_fin_de_semana(mascara: str) -> bool:
    return mascara[:5] == "00000" and mascara[5:] != "00"


def solo_entre_semana(mascara: str) -> bool:
    return mascara[5:] == "00" and mascara[:5] != "00000"


def unir(a: str, b: str) -> str:
    return "".join("1" if x == "1" or y == "1" else "0" for x, y in zip(a, b))
