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


def _instancia_unica(nome: str = "Global\\VozFlow_Singleton") -> bool:
    """Impede duas copias do VozFlow disputando os mesmos atalhos globais.

    O nome continua em Global\\ de proposito: trocar para Local\\ deixaria a
    versao nova rodando junto com uma 1.1.1 ainda aberta (iniciada com o
    Windows) durante a atualizacao. Outro usuario do PC nao e bloqueado: ele
    recebe ERROR_ACCESS_DENIED, nao ERROR_ALREADY_EXISTS.
    """
    global _mutex
    if os.name != "nt":
        return True
    # use_last_error: o ctypes.windll.kernel32.GetLastError() de antes podia
    # ler um codigo ja sobrescrito pelo proprio ctypes entre as duas chamadas.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, nome)
    ja_existe = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    if _mutex is None:
        _mutex = handle   # o handle vive ate o processo acabar
    return not ja_existe


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
