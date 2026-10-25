"""Atualizacao automatica pelas Releases do GitHub.

Sai versao nova: o VozFlow baixa o instalador em segundo plano, confere a
ASSINATURA (vozflow/assinatura.py) e instala sozinho quando ninguem esta
usando o PC - fecha, o instalador roda em silencio (sem pedir administrador:
ele instala na pasta do usuario) e abre o VozFlow de novo ja na versao nova.

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
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore

from . import __version__, assinatura

# Repositorio PUBLICO so com os instaladores: o do codigo e privado, e o
# GitHub nao entrega Release de repositorio privado sem login.
REPO = "clauberteixeira/VozFlow-releases"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
# Chave publica de quem publica (ferramentas/assinar.py). A privada nunca vai
# para o GitHub: e ela que impede uma conta invadida de soltar um instalador.
CHAVE_PUBLICA = bytes.fromhex("c154cfa04cf44adff8dcd64f840f4ef4e0517391ac99053fde38108554e66855")
PASTA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "VozFlow" / "atualizacao"
TAMANHO_MAX = 2 * 1024 ** 3          # o instalador tem ~520 MB
PRIMEIRA_CONSULTA_MS = 60_000        # deixa o app terminar de subir
INTERVALO_MS = 6 * 3600 * 1000
PARADO_PARA_INSTALAR_S = 60          # sem teclado/mouse ha isso: ninguem esta usando


class SemVersaoPublicada(Exception):
    pass


def versao(texto: str | None) -> tuple[int, ...] | None:
    """'v1.2.3' ou '1.2.3' -> (1, 2, 3); qualquer outra coisa -> None."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", (texto or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def _maior(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """1.2.0 e 1.2 sao a mesma versao."""
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


@dataclass
class Lancamento:
    versao: str            # "1.2.4"
    url_instalador: str
    url_assinatura: str
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


def _url_do_anexo(url: str, tag: str, nome: str) -> bool:
    """Exatamente https://github.com/<REPO>/releases/download/<tag>/<nome>."""
    u = urllib.parse.urlsplit(url)
    return (u.scheme == "https" and u.netloc == "github.com" and not u.query
            and u.path == f"/{REPO}/releases/download/{tag}/{nome}")


def consultar(abrir=urllib.request.urlopen) -> Lancamento | None:
    """A ultima Release publicada, se tem instalador e assinatura anexados."""
    try:
        with _abrir(API, abrir, timeout=15) as r:
            dados = json.loads(r.read(1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:               # repositorio ainda sem nenhuma Release
            raise SemVersaoPublicada() from exc
        raise
    if not isinstance(dados, dict) or dados.get("draft") or dados.get("prerelease"):
        return None
    tag = str(dados.get("tag_name") or "")
    v = versao(tag)
    if v is None:
        return None
    nome = f"VozFlow-{'.'.join(map(str, v))}-instalador.exe"
    anexos = {a.get("name"): a for a in dados.get("assets") or [] if isinstance(a, dict)}
    exe, sig = anexos.get(nome), anexos.get(nome + ".sig")
    if not exe or not sig:
        return None
    url_exe = str(exe.get("browser_download_url") or "")
    url_sig = str(sig.get("browser_download_url") or "")
    if not (_url_do_anexo(url_exe, tag, nome) and _url_do_anexo(url_sig, tag, nome + ".sig")):
        return None
    return Lancamento(".".join(map(str, v)), url_exe, url_sig, int(exe.get("size") or 0))


def e_mais_nova(lanc: Lancamento | None, atual: str = __version__) -> bool:
    if lanc is None:
        return False
    nova, agora = versao(lanc.versao), versao(atual)
    return bool(nova and agora and _maior(nova, agora))


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _assinado(nome: str, sha: str, assinatura_hex: str, chave: bytes) -> bool:
    try:
        sig = bytes.fromhex(assinatura_hex)
    except ValueError:
        return False
    return assinatura.conferir(chave, assinatura.mensagem(nome, sha), sig)


def baixar(lanc: Lancamento, pasta: Path = PASTA, abrir=urllib.request.urlopen,
           chave: bytes = CHAVE_PUBLICA) -> Path:
    """Baixa o instalador e confere a assinatura. Devolve o caminho.

    Levanta ValueError se o arquivo nao confere: ele e apagado e nao roda.
    """
    with _abrir(lanc.url_assinatura, abrir) as r:
        assinatura_hex = r.read(1024).decode("ascii", "replace").strip()

    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / lanc.nome_arquivo
    if destino.exists() and _assinado(lanc.nome_arquivo, _sha256(destino), assinatura_hex, chave):
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
        if lanc.tamanho and total != lanc.tamanho:
            raise ValueError("download incompleto")
        if not _assinado(lanc.nome_arquivo, h.hexdigest(), assinatura_hex, chave):
            raise ValueError("a assinatura do instalador nao confere")
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
        if m.group(2) or v is None or (agora and not _maior(v, agora)):
            try:
                arq.unlink()
            except OSError:
                pass


# ----------------------------------------------------------------------
# estado: fica num arquivo proprio, nunca no config.json. Regravar a config
# na inicializacao podia trocar a do usuario pelos padroes quando o
# config.json estava travado (antivirus no boot).
# ----------------------------------------------------------------------
def ler_estado(pasta: Path = PASTA) -> dict | None:
    """O estado salvo; {} se ainda nao existe; None se existe mas nao deu para
    ler (travado no boot) - ai quem chamou nao deve regravar por cima."""
    try:
        bruto = (pasta / "estado.json").read_bytes()
    except FileNotFoundError:
        return {}
    except OSError:
        return None
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except ValueError:                 # inclui UnicodeDecodeError
        return {}                      # corrompido: recomecar e o melhor
    return dados if isinstance(dados, dict) else {}


def gravar_estado(estado: dict, pasta: Path = PASTA) -> None:
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        tmp = pasta / "estado.json.tmp"
        tmp.write_text(json.dumps(estado), encoding="utf-8")
        os.replace(tmp, pasta / "estado.json")
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


def instalar(caminho: Path, popen=subprocess.Popen, voltar: str | None = None) -> None:
    """Dispara o instalador em silencio, separado deste processo.

    /REABRIR=1: o instalador espera o VozFlow fechar (a trava de instancia
    unica sumir) antes de copiar e abre o VozFlow de novo no fim. /VOLTAR: se
    a instalacao falhar no meio, reabre a versao que ja estava instalada -
    ver instalador.iss.
    """
    args = [str(caminho), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/REABRIR=1"]
    if voltar:
        args.append(f"/VOLTAR={voltar}")
    # O ambiente do executavel do PyInstaller (_PYI_*, _MEIPASS2) nao pode
    # vazar para o VozFlow que o instalador reabre.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("_PYI_") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    popen(
        args,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
        env=env,
    )


class Atualizador(QtCore.QObject):
    """Consulta de tempos em tempos, baixa em segundo plano e instala parado.

    `ocupado()` diz se o VozFlow esta no meio de algo (gravando, entregando
    texto, janela de configuracoes aberta); `ao_instalar(versao, caminho)`
    fecha o app e dispara o instalador. A instalacao automatica espera o PC
    ficar parado; a pedida pelo menu so espera o VozFlow desocupar.
    """

    _baixado = QtCore.Signal(str, str, bool)   # versao, caminho, pedido pelo menu
    _resultado = QtCore.Signal(str, bool)      # mensagem, pedido pelo menu
    aviso = QtCore.Signal(str)                 # mensagem para a bandeja

    def __init__(self, cfg, ocupado, ao_instalar, parent=None, ativo=None, pasta: Path = PASTA):
        super().__init__(parent)
        self.cfg = cfg
        self._ocupado = ocupado
        self._ao_instalar = ao_instalar
        self.pasta = pasta
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
            limpar_antigos(self.pasta)
        except OSError:
            pass
        QtCore.QTimer.singleShot(PRIMEIRA_CONSULTA_MS, self._consulta_automatica)
        self._timer_consulta.start(INTERVALO_MS)

    # -- o que aconteceu desde a ultima abertura -------------------------
    def conferir_abertura(self) -> str | None:
        """Mensagem para a bandeja nesta abertura, se houver.

        Atualizou: "atualizado para X". Abriu numa versao MENOR que a da
        ultima tentativa: a instalacao falhou - essa versao deixa de ser
        instalada sozinha (so pelo menu), senao o app fecharia de novo a cada
        minuto parado, sem nunca conseguir.
        """
        if not self.ativo:
            return None
        estado = ler_estado(self.pasta)
        if estado is None:          # travado agora: nao regrava por cima do "falhou"
            return None
        agora = versao(__version__)
        msg = None
        tentada = estado.get("tentada") or {}
        v_tentada = versao(tentada.get("versao"))
        if v_tentada and agora:
            if _maior(v_tentada, agora):
                estado["falhou"] = tentada.get("versao")
                msg = (f"A atualizacao para a versao {tentada.get('versao')} nao terminou. "
                       "Use 'Procurar atualizacao agora' no menu para tentar de novo.")
            estado.pop("tentada", None)
        vista = versao(estado.get("vista"))
        if msg is None and vista and agora and _maior(agora, vista):
            msg = f"VozFlow atualizado para a versao {__version__}."
        if estado.get("vista") != __version__ or msg:
            estado["vista"] = __version__
            gravar_estado(estado, self.pasta)
        return msg

    # -- consulta e download ---------------------------------------------
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
        # "Pedido" so vira instalacao imediata quando ha o que instalar: um
        # "ja esta na mais nova" nao pode deixar a PROXIMA automatica pular a
        # espera do PC parado.
        if pedido and self.pendente:
            self._imediato = True
            self._timer_instalar.start(2000)
            return
        if self._thread is not None and self._thread.is_alive():
            if pedido:
                self._imediato = True       # o download em andamento instala ao terminar
                self.aviso.emit("Ja estou baixando a atualizacao; instalo assim que terminar.")
            return
        self._thread = threading.Thread(target=self._trabalho, args=(pedido,), daemon=True)
        self._thread.start()

    def _trabalho(self, pedido: bool) -> None:
        try:
            lanc = consultar()
            if not e_mais_nova(lanc):
                self._resultado.emit(f"Voce ja esta na versao mais nova ({__version__}).", pedido)
                return
            if not pedido:
                estado = ler_estado(self.pasta)
                # falhou antes (ou nao da para saber agora): so pelo menu
                if estado is None or estado.get("falhou") == lanc.versao:
                    return
            if pedido:
                self._resultado.emit(f"Baixando a versao {lanc.versao}...", True)
            caminho = baixar(lanc, self.pasta)
            self._baixado.emit(lanc.versao, str(caminho), pedido)
        except SemVersaoPublicada:
            self._resultado.emit(f"Voce ja esta na versao mais nova ({__version__}).", pedido)
        except ValueError as exc:
            self._resultado.emit(f"A atualizacao baixada foi descartada: {exc}.", pedido)
        except Exception as exc:  # noqa: BLE001 - sem internet, GitHub fora: tenta depois
            self._resultado.emit(f"Nao consegui procurar atualizacao ({exc}).", pedido)

    def _ao_resultado(self, msg: str, pedido: bool) -> None:
        # A procura terminou sem nada para instalar: o pedido do menu acabou
        # aqui e nao vale para a proxima automatica.
        if not self.pendente:
            self._imediato = False
        if pedido:
            self.aviso.emit(msg)

    def _ao_baixar(self, versao_nova: str, caminho: str, pedido: bool) -> None:
        self.pendente = (versao_nova, caminho)
        self._imediato = self._imediato or pedido
        self._timer_instalar.start(2000 if self._imediato else 30_000)

    # -- instalacao --------------------------------------------------------
    def _tentar_instalar(self) -> None:
        if not self.pendente or self._ocupado():
            return
        if not self._imediato:
            if not self.cfg.get("atualizar_auto", True):
                return
            if segundos_parado() < PARADO_PARA_INSTALAR_S:
                return
        self._timer_instalar.stop()
        versao_nova, caminho = self.pendente
        self.pendente = None
        self._ao_instalar(versao_nova, Path(caminho))

    def marcar_tentativa(self, versao_nova: str) -> None:
        """Logo antes de disparar o instalador (nao antes do aviso de 1,5 s:
        um Sair nesse meio-tempo nao e uma instalacao que falhou)."""
        estado = ler_estado(self.pasta) or {}
        estado["tentada"] = {"versao": versao_nova}
        estado.pop("falhou", None)
        gravar_estado(estado, self.pasta)

    def adiar(self, versao_nova: str, caminho) -> None:
        """O app nao pode fechar agora: volta a esperar."""
        self.pendente = (versao_nova, str(caminho))
        self._timer_instalar.start(2000 if self._imediato else 30_000)
