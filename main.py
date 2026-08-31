"""Ponto de entrada do VozFlow. Rode com: pythonw main.py"""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6 import QtWidgets

from vozflow import APP_NAME
from vozflow.app import VozFlow

_mutex = None
_instancia = None  # segura a referencia; sem isso o GC derruba o icone da bandeja


def _instancia_unica() -> bool:
    """Impede duas copias do VozFlow disputando os mesmos atalhos globais."""
    global _mutex
    if os.name != "nt":
        return True
    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, False, "Global\\VozFlow_Singleton")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main() -> int:
    global _instancia
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VozFlow.App")
        except Exception:
            pass

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    if not _instancia_unica():
        QtWidgets.QMessageBox.information(
            None, APP_NAME, "O VozFlow ja esta rodando (veja o icone na bandeja)."
        )
        return 0

    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(
            None, APP_NAME, "A bandeja do sistema nao esta disponivel nesta sessao."
        )
        return 1

    _instancia = VozFlow(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
