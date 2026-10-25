"""Atualizacao automatica pelas Releases do GitHub.

Sai versao nova: o VozFlow baixa o instalador em segundo plano, confere o
SHA-256 publicado junto, e instala sozinho quando ninguem esta usando o PC -
fecha, o instalador roda em silencio (sem pedir administrador: ele instala na
pasta do usuario) e abre o VozFlow de novo ja na versao nova.

So conversa com o GitHub: nenhum dado do usuario sai daqui. Rodando do codigo
fonte (python main.py) nao faz nada - so o executavel instalado se atualiza.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore

from . import __version__

# Repositorio PUBLICO so com os instaladores: o do codigo e privado, e o
# GitHub nao entrega Release de repositorio privado sem login.
REPO = "clauberteixeira/VozFlow-releases"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
# Os anexos so podem vir da propria Release do repositorio
PREFIXO_DOWNLOAD = f"https://github.com/{REPO}/releases/download/"
PASTA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "VozFlow" / "atualizacao"
TAMANHO_MAX = 2 * 1024 ** 3          # o instalador tem ~520 MB
PRIMEIRA_CONSULTA_MS = 60_000        # deixa o app terminar de subir
INTERVALO_MS = 6 * 3600 * 1000
PARADO_PARA_INSTALAR_S = 60          # sem teclado/mouse ha isso: ninguem esta usando


def versao(texto: str | None) -> tuple[int, ...] | None:
    """'v1.2.3' ou '1.2.3' -> (1, 2, 3); qualquer outra coisa -> None."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", (texto or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


@dataclass
class Lancamento:
    versao: str            # "1.2.4"
    url_instalador: str
    url_hash: str
    tamanho: int

    @property
    def nome_arquivo(self) -> str:
        return f"VozFlow-{self.versao}-instalador.exe"


def _abrir(url: str, abrir, timeout: float = 30):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"VozFlow/{__version__}",
    })
    return abrir(req, timeout=timeout)


def consultar(abrir=urllib.request.urlopen) -> Lancamento | None:
    """A ultima Release publicada, se ela tem instalador e hash anexados."""
    with _abrir(API, abrir, timeout=15) as r:
        dados = json.loads(r.read(1_000_000).decode("utf-8"))
    if not isinstance(dados, dict) or dados.get("draft") or dados.get("prerelease"):
        return None
    tag = str(dados.get("tag_name") or "")
    v = versao(tag)
    if v is None:
        return None
    numero = ".".join(map(str, v))
    nome = f"VozFlow-{numero}-instalador.exe"
    anexos = {a.get("name"): a for a in dados.get("assets") or [] if isinstance(a, dict)}
    exe, sha = anexos.get(nome), anexos.get(nome + ".sha256")
    if not exe or not sha:
        return None
    base = PREFIXO_DOWNLOAD + tag + "/"
    url_exe = str(exe.get("browser_download_url") or "")
    url_sha = str(sha.get("browser_download_url") or "")
    if not (url_exe.startswith(base) and url_sha.startswith(base)):
        return None
    return Lancamento(numero, url_exe, url_sha, int(exe.get("size") or 0))


def e_mais_nova(lanc: Lancamento | None, atual: str = __version__) -> bool:
    if lanc is None:
        return False
    nova, agora = versao(lanc.versao), versao(atual)
    return bool(nova and agora and nova > agora)


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(lanc: Lancamento, pasta: Path = PASTA, abrir=urllib.request.urlopen) -> Path | None:
    """Baixa o instalador e confere o SHA-256. Devolve o caminho, ou None.

    Arquivo que nao bate com o hash publicado e apagado: corrompido no
    caminho ou trocado, nao roda.
    """
    with _abrir(lanc.url_hash, abrir) as r:
        texto = r.read(4096).decode("ascii", "replace")
    m = re.search(r"\b([0-9a-fA-F]{64})\b", texto)
    if not m:
        return None
    esperado = m.group(1).lower()

    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / lanc.nome_arquivo
    if destino.exists() and _sha256(destino) == esperado:
        return destino                      # ja baixado numa vez anterior
    parcial = destino.with_name(destino.name + ".part")
    h = hashlib.sha256()
    total = 0
    try:
        with _abrir(lanc.url_instalador, abrir, timeout=60) as r, open(parcial, "wb") as f:
            for bloco in iter(lambda: r.read(1 << 20), b""):
                total += len(bloco)
                if total > TAMANHO_MAX:
                    raise ValueError("instalador grande demais")
                h.update(bloco)
                f.write(bloco)
        if h.hexdigest() != esperado:
            raise ValueError("SHA-256 nao confere")
        os.replace(parcial, destino)
        return destino
    finally:
        try:
            parcial.unlink(missing_ok=True)
        except OSError:
            pass


def limpar_antigos(pasta: Path = PASTA, atual: str = __version__) -> None:
    """Apaga instaladores ja usados (versao <= a atual) e downloads pela metade."""
    if not pasta.is_dir():
        return
    agora = versao(atual)
    for arq in pasta.iterdir():
        m = re.fullmatch(r"VozFlow-(.+)-instalador\.exe(\.part)?", arq.name)
        if not m:
            continue
        v = versao(m.group(1))
        if m.group(2) or v is None or (agora and v <= agora):
            try:
                arq.unlink()
            except OSError:
                pass


def segundos_parado() -> float:
    """Ha quanto tempo ninguem mexe no teclado ou no mouse (0 fora do Windows)."""
    if os.name != "nt":
        return 0.0
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    agora = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((agora - info.dwTime) & 0xFFFFFFFF) / 1000.0


def instalar(caminho: Path, popen=subprocess.Popen) -> None:
    """Dispara o instalador em silencio, separado deste processo.

    /REABRIR=1: o instalador espera o VozFlow fechar (a trava de instancia
    unica sumir) antes de copiar e abre o VozFlow de novo no fim - ver
    instalador.iss.
    """
    popen(
        [str(caminho), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/REABRIR=1"],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )


class Atualizador(QtCore.QObject):
    """Consulta de tempos em tempos, baixa em segundo plano e instala parado.

    `ocupado()` diz se o VozFlow esta no meio de algo (gravando, janela de
    configuracoes aberta); `ao_instalar(caminho)` fecha o app e dispara o
    instalador. A instalacao automatica espera o PC ficar parado; a pedida
    pelo menu so espera o VozFlow desocupar.
    """

    _baixado = QtCore.Signal(str, str, bool)   # versao, caminho, pedido pelo menu
    _resultado = QtCore.Signal(str, bool)      # mensagem, pedido pelo menu
    aviso = QtCore.Signal(str)                 # mensagem para a bandeja

    def __init__(self, cfg, ocupado, ao_instalar, parent=None, ativo=None):
        super().__init__(parent)
        self.cfg = cfg
        self._ocupado = ocupado
        self._ao_instalar = ao_instalar
        # So o executavel instalado se atualiza; do codigo fonte, nunca.
        self.ativo = getattr(sys, "frozen", False) if ativo is None else ativo
        self._thread: threading.Thread | None = None
        self.pendente: tuple[str, str] | None = None   # (versao, caminho)
        self._imediato = False
        self._baixado.connect(self._ao_baixar)
        self._resultado.connect(self._ao_resultado)

        self._timer_consulta = QtCore.QTimer(self)
        self._timer_consulta.timeout.connect(lambda: self.verificar())
        self._timer_instalar = QtCore.QTimer(self)
        self._timer_instalar.timeout.connect(self._tentar_instalar)

    def iniciar(self) -> None:
        if not self.ativo:
            return
        try:
            limpar_antigos()
        except OSError:
            pass
        QtCore.QTimer.singleShot(PRIMEIRA_CONSULTA_MS, self._consulta_automatica)
        self._timer_consulta.start(INTERVALO_MS)

    def _consulta_automatica(self) -> None:
        if self.cfg.get("atualizar_auto", True):
            self.verificar()

    def verificar(self, pedido: bool = False) -> None:
        """Consulta (e baixa) numa thread. `pedido`: veio do menu da bandeja."""
        if not self.ativo:
            if pedido:
                self.aviso.emit("Atualizacao automatica so funciona na versao instalada.")
            return
        if not pedido and not self.cfg.get("atualizar_auto", True):
            return
        if pedido and self.pendente:
            self._imediato = True
            self._timer_instalar.start(2000)
            return
        if self._thread is not None and self._thread.is_alive():
            if pedido:
                self.aviso.emit("Ja estou baixando a atualizacao.")
            return
        self._thread = threading.Thread(target=self._trabalho, args=(pedido,), daemon=True)
        self._thread.start()

    def _trabalho(self, pedido: bool) -> None:
        try:
            lanc = consultar()
            if not e_mais_nova(lanc):
                self._resultado.emit(f"Voce ja esta na versao mais nova ({__version__}).", pedido)
                return
            if pedido:
                self._resultado.emit(f"Baixando a versao {lanc.versao}...", True)
            caminho = baixar(lanc)
            if caminho is None:
                self._resultado.emit("A atualizacao baixada nao conferiu; tento de novo mais tarde.",
                                     pedido)
                return
            self._baixado.emit(lanc.versao, str(caminho), pedido)
        except Exception as exc:  # noqa: BLE001 - sem internet, GitHub fora: tenta depois
            self._resultado.emit(f"Nao consegui procurar atualizacao ({exc}).", pedido)

    def _ao_resultado(self, msg: str, pedido: bool) -> None:
        if pedido:
            self.aviso.emit(msg)

    def _ao_baixar(self, versao_nova: str, caminho: str, pedido: bool) -> None:
        self.pendente = (versao_nova, caminho)
        self._imediato = self._imediato or pedido
        self._timer_instalar.start(2000 if self._imediato else 30_000)

    def _tentar_instalar(self) -> None:
        if not self.pendente or self._ocupado():
            return
        if not self._imediato and segundos_parado() < PARADO_PARA_INSTALAR_S:
            return
        if not self._imediato and not self.cfg.get("atualizar_auto", True):
            return
        self._timer_instalar.stop()
        versao_nova, caminho = self.pendente
        self.pendente = None
        self._ao_instalar(versao_nova, Path(caminho))
