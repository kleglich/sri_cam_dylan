"""Punto de entrada del SRI (aplicación de escritorio)."""

from __future__ import annotations

import sys
import traceback


def _activar_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    _activar_dpi()
    from sri.config import cargar_config
    from sri.contexto import Contexto
    from sri.presentacion.app import Aplicacion

    try:
        config = cargar_config()
        contexto = Contexto(config=config)
    except Exception as error:  # noqa: BLE001
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(
            "SRI · Error de inicio",
            f"No se pudo iniciar el sistema:\n\n{error}\n\n"
            "Verifique que las dependencias estén instaladas (pip install -r requirements.txt).",
        )
        raiz.destroy()
        return 1

    aplicacion = Aplicacion(contexto)
    try:
        aplicacion.mainloop()
    finally:
        try:
            contexto.cerrar()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
