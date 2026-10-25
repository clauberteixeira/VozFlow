"""Configuracao do VozFlow, persistida em config.json dentro do APPDATA."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import APP_NAME

# VOZFLOW_CONFIG_DIR existe para os testes: sem ele, cada teste que abre a tela
# de configuracoes grava por cima da configuracao real de quem usa o app - foi
# assim que o atalho e o "apertar Enter" do usuario voltaram sozinhos ao padrao
# no meio de uma bateria de testes.
_BASE = os.environ.get("VOZFLOW_CONFIG_DIR")
CONFIG_DIR = Path(_BASE) if _BASE else (
    Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
)
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "transcricoes.txt"

DEFAULTS: dict = {
    # --- atalhos globais (sintaxe da lib `keyboard`) ---
    "hotkey_start": "ctrl+alt+g",
    "hotkey_stop": "ctrl+alt+s",
    "hotkey_cancel": "ctrl+alt+x",
    "suppress_hotkeys": False,  # True = a tecla nao chega ao programa em foco
    # Segundo par de atalhos, com a SUA propria regra de Enter. Serve para ter
    # uma tecla que so escreve e outra que escreve e ja envia.
    "hotkey_start2": "",
    "hotkey_stop2": "",
    "press_enter_after2": False,

    # --- modelo de transcricao ---
    # tiny | base | small | medium | large-v3 | large-v3-turbo
    "model": "large-v3-turbo",
    "language": "pt",
    "device": "auto",          # auto | cuda | cpu
    "compute_type": "auto",    # auto | float16 | int8_float16 | int8
    "initial_prompt": "",      # vocabulario/contexto p/ melhorar nomes proprios

    # --- captura ---
    "input_device": None,      # nome do microfone; None = padrao do Windows
    "partial_interval": 0.45,  # segundos entre retranscricoes do trecho aberto
    "silence_ms": 700,         # silencio que fecha um trecho
    "nivel_minimo": 0.004,     # RMS abaixo disso conta como mudo (anti-alucinacao)
    "nivel_fala": 0.010,       # abaixo disso e som de fundo, nao voce (use Calibrar)
    "max_segment_s": 20.0,     # trecho maximo antes de fechar a forca

    # --- o que fazer ao parar ---
    "action_on_stop": "paste",  # paste | clipboard | webhook
    "insercao_ao_vivo": True,   # escreve cada trecho no campo enquanto voce fala
    "press_enter_after": False,  # cola e ja aperta Enter (envia no WhatsApp/chat)
    "webhook_url": "",
    "webhook_field": "texto",

    # --- interface ---
    "show_overlay": True,
    "overlay_posicao": "inferior-centro",  # ver POSICOES em overlay.py
    "overlay_offset_y": 90,   # distancia da borda de cima ou de baixo
    "overlay_width": 760,
    # Prende a escrita na janela onde a ditada comecou. Sem isso, trocar de
    # janela no meio da fala leva o resto do texto junto.
    "travar_janela": True,
    "sounds": True,
    "log_transcricoes": True,
}


def _migrar_microfone(data: dict) -> None:
    """Versoes antigas gravavam o indice do PortAudio em input_device.

    Esse indice muda de posicao sozinho - basta um fone Bluetooth conectar ou
    o NVIDIA Broadcast ligar - e o numero salvo passa a apontar para outro
    aparelho, as vezes uma SAIDA de audio; ai toda gravacao morre com
    "Unanticipated host error". Converte o indice para o nome do dispositivo,
    que e estavel, e cai para o padrao do Windows quando ele nao existe mais.
    """
    valor = data.get("input_device")
    if valor is None or isinstance(valor, str):
        return
    if isinstance(valor, bool) or not isinstance(valor, int):
        data["input_device"] = None
        return
    try:
        from .audio import nome_do_indice
        data["input_device"] = nome_do_indice(valor)
    except Exception as exc:  # noqa: BLE001 - sem audio: usa o padrao
        print(f"[config] nao consegui migrar input_device={valor} ({exc})")
        data["input_device"] = None


def _tipo_ok(padrao, valor) -> bool:
    """O valor tem o tipo que o codigo espera para esta chave?

    bool e subclasse de int em Python: sem a checagem explicita, "sounds": 1
    passaria por bool e "nivel_fala": true passaria por numero.
    """
    if isinstance(padrao, bool):
        return isinstance(valor, bool)
    if isinstance(padrao, (int, float)):
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if isinstance(padrao, str):
        return isinstance(valor, str)
    if padrao is None:          # input_device: nome do microfone ou padrao do Windows
        return valor is None or isinstance(valor, str)
    return True


def _validar_tipos(data: dict) -> None:
    """Valor com tipo errado volta ao padrao, so naquela chave.

    Antes, um "silence_ms": "700" editado a mao matava a thread do motor na
    primeira comparacao (o app seguia "Pronto" sem transcrever nada), e um
    "overlay_width": "abc" impedia o app de abrir - sob pythonw, sem mensagem.
    Chave desconhecida fica como esta: pode ser de uma versao mais nova.
    """
    for chave, padrao in DEFAULTS.items():
        if chave in data and not _tipo_ok(padrao, data[chave]):
            print(f"[config] {chave}={data[chave]!r} invalido; usando {padrao!r}")
            data[chave] = padrao


class Config(dict):
    """Dicionario de config com acesso por atributo e persistencia em disco."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def _texto(self) -> str:
        return json.dumps(self, indent=2, ensure_ascii=False)

    def save(self) -> None:
        # Arquivo temporario + os.replace: uma queda de energia no meio da
        # gravacao deixa o arquivo antigo inteiro, nunca um JSON pela metade.
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
        tmp.write_text(self._texto(), encoding="utf-8")
        os.replace(tmp, CONFIG_PATH)


def load() -> Config:
    """Le o config.json, completando com os padroes e gravando se faltar algo.

    Le como utf-8-sig de proposito: o Notepad e o PowerShell gravam UTF-8 com
    BOM, e o BOM faz o json.loads falhar. Antes disso, editar o arquivo por fora
    derrubava tudo de volta para os padroes sem avisar.

    Se o arquivo estiver mesmo corrompido, ele e preservado com sufixo .bak em
    vez de ser sobrescrito - a config do usuario nao se perde calada.
    """
    data = dict(DEFAULTS)
    em_disco = None
    if CONFIG_PATH.exists():
        try:
            em_disco = CONFIG_PATH.read_text(encoding="utf-8-sig")
            lido = json.loads(em_disco)
            if not isinstance(lido, dict):
                raise ValueError("o arquivo nao e um objeto JSON")
            data.update(lido)
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            # ValueError cobre o JSONDecodeError
            print(f"[config] config.json invalido ({exc}); usando padroes")
            em_disco = None
            try:
                backup = CONFIG_PATH.with_suffix(".json.bak")
                backup.write_bytes(CONFIG_PATH.read_bytes())
                print(f"[config] copia do arquivo problematico em {backup}")
            except OSError:
                pass
    _migrar_microfone(data)
    _validar_tipos(data)
    cfg = Config(data)
    if em_disco != cfg._texto():   # so regrava se faltava chave ou algo mudou
        cfg.save()
    return cfg
