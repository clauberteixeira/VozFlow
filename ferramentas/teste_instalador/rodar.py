"""Confere de verdade o [Code]/[Run] da atualizacao do instalador.iss.

    .venv\\Scripts\\python -B ferramentas\\teste_instalador\\rodar.py .

Compila teste.iss (mesmo codigo de atualizacao do instalador.iss, mas com
outra trava, sem desinstalador nem registro, instalando um arquivo falso numa
pasta aqui dentro) e o roda com as MESMAS opcoes de atualizador.instalar, em
quatro cenarios: atualizacao normal (espera a trava sumir e reabre), VozFlow
que nao fecha (desiste sem instalar), falha antes da copia (reabre a versao
antiga, com espaco no caminho) e falha depois de um arquivo - este ultimo NAO
aborta o Inno (BeforeInstall nao e fatal); fica como registro do limite.
Nao mexe no VozFlow instalado.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, sys.argv[1])
from vozflow import atualizador as atu  # noqa: E402

EXE = AQUI / "teste-atualizacao.exe"
# faz o papel do VozFlow antigo: um programa inofensivo, num caminho com espaco
VOLTAR = AQUI / "pasta com espaco" / "whoami copia.exe"
if not VOLTAR.exists():
    VOLTAR.parent.mkdir(exist_ok=True)
    shutil.copy(Path(os.environ["SystemRoot"]) / "System32" / "whoami.exe", VOLTAR)
VOLTAR = str(VOLTAR)
if not EXE.exists():
    iscc = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe"
    subprocess.run([str(iscc), "/Q", str(AQUI / "teste.iss")], check=True, cwd=AQUI)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateMutexW.restype = ctypes.c_void_p
base = AQUI / "destino"
base.mkdir(exist_ok=True)


def rodar(nome: str, soltar_em: float | None, extra=()):
    destino = base / nome
    shutil.rmtree(destino, ignore_errors=True)
    log = base / (nome + ".log")
    log.unlink(missing_ok=True)
    trava = k32.CreateMutexW(None, False, "Global\\VozFlowTesteAtualizacao_Mutex")
    procs = []

    def popen(args, **kw):
        procs.append(subprocess.Popen([*args, *extra, f"/DESTINO={destino}", f"/LOG={log}"], **kw))

    t0 = time.monotonic()
    atu.instalar(EXE, popen=popen, voltar=VOLTAR)
    if soltar_em is not None:
        time.sleep(soltar_em)
        k32.CloseHandle(ctypes.c_void_p(trava))
    procs[0].wait(90)
    t_fim = time.monotonic() - t0
    if soltar_em is None:
        k32.CloseHandle(ctypes.c_void_p(trava))
    time.sleep(1.0)
    texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return dict(codigo=procs[0].returncode, fim_s=round(t_fim, 1),
                instalado=(destino / "arquivo.txt").exists(),
                reabriu_nova=(destino / "reaberto.txt").exists(),
                reabriu_antiga="reabrindo" in texto,
                desistiu="desistindo" in texto)


print("1 atualizacao normal (trava solta em 3 s):", rodar("a", 3.0))
print("2 VozFlow nao fecha (trava presa):        ", rodar("b", None))
print("3 falha antes de copiar:                   ", rodar("c", 0.5, ["/FALHAR=1"]))
print("4 falha depois de 1 arquivo copiado:      ", rodar("d", 0.5, ["/FALHAR=2"]))
