"""Ejecuta la interfaz desde el repositorio: python -m sri.presentacion."""

from __future__ import annotations

from ..contexto import Contexto
from .app import Aplicacion


def main() -> int:
    contexto = Contexto()
    aplicacion = Aplicacion(contexto)
    try:
        aplicacion.mainloop()
    finally:
        contexto.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
