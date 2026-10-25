"""Entrega do texto transcrito: colar na janela ativa, copiar ou mandar p/ webhook."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit

import keyboard
import pyperclip

MODIFICADORES = ("ctrl", "alt", "shift")


def esperar_modificadores(timeout: float = 1.2) -> bool:
    """O atalho ainda esta com Ctrl/Alt pressionados quando disparamos o Ctrl+V.

    Espera a soltura natural; se demorar demais, solta na marra para o Ctrl+V
    nao virar Ctrl+Alt+V na janela de destino.
    """
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if not any(keyboard.is_pressed(m) for m in MODIFICADORES):
            return True
        time.sleep(0.02)
    for mod in MODIFICADORES:
        try:
            keyboard.release(mod)
        except Exception:
            pass
    return False


def copiar(texto: str) -> bool:
    if not texto:
        return False
    try:
        pyperclip.copy(texto)
        return True
    except Exception:
        return False


def colar(texto: str, enter: bool = False, restaurar: bool = True) -> bool:
    """Cola o texto na janela que estiver em foco (via area de transferencia)."""
    if not texto:
        return False
    anterior = ""
    if restaurar:
        try:
            anterior = pyperclip.paste()
        except Exception:
            anterior = ""

    if not copiar(texto):
        return False

    esperar_modificadores()
    time.sleep(0.08)  # da tempo do app de destino enxergar o clipboard novo
    keyboard.send("ctrl+v")
    if enter:
        time.sleep(0.15)
        keyboard.send("enter")

    if restaurar and anterior and anterior != texto:
        # Ctrl+V e assincrono: o app de destino le o clipboard quando o loop
        # dele processar a tecla, e Chromium/Office ocupados demoram. Restaurar
        # na hora fazia colar o conteudo ANTERIOR (uma senha copiada, por
        # exemplo). E so restaura se o clipboard ainda for nosso: se a pessoa
        # copiou outra coisa nesse meio-tempo, a copia nova fica.
        threading.Timer(0.8, _restaurar_se_intacto, (texto, anterior)).start()
    return True


def _restaurar_se_intacto(nosso: str, anterior: str) -> None:
    try:
        if pyperclip.paste() != nosso:
            return
    except Exception:  # noqa: BLE001
        return
    copiar(anterior)


def apertar_enter() -> bool:
    """Enter sozinho, para o fim de uma ditada escrita ao vivo."""
    esperar_modificadores()
    time.sleep(0.05)
    keyboard.send("enter")
    return True


def digitar(texto: str, enter: bool = False) -> bool:
    """Alternativa para apps que bloqueiam colagem (digita tecla a tecla)."""
    if not texto:
        return False
    esperar_modificadores()
    time.sleep(0.05)
    keyboard.write(texto, delay=0.005)
    if enter:
        time.sleep(0.1)
        keyboard.send("enter")
    return True


def url_sem_criptografia(url: str) -> bool:
    """True para http:// fora desta maquina: o ditado iria em texto claro pela rede.

    So vira aviso na tela de configuracoes, nunca bloqueio - um n8n ou servidor
    na rede de casa pode nao ter HTTPS. localhost/127.x/::1 nao saem do PC.
    """
    try:
        partes = urlsplit((url or "").strip())
        host = (partes.hostname or "").lower()
    except ValueError:
        return False
    if partes.scheme.lower() != "http":
        return False
    return not (host == "localhost" or host == "::1" or host.startswith("127."))


def enviar_webhook(url: str, campo: str, texto: str, timeout: float = 15.0) -> tuple[bool, str]:
    if not url:
        return False, "webhook_url vazio no config.json"
    try:
        import requests

        r = requests.post(url, json={campo or "texto": texto}, timeout=timeout)
        ok = 200 <= r.status_code < 300
        return ok, "HTTP " + str(r.status_code)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def entregar(cfg, texto: str, enter: bool | None = None) -> tuple[bool, str]:
    """Aplica a acao configurada em `action_on_stop` e devolve (ok, descricao).

    `enter` vindo preenchido manda no lugar do `press_enter_after` da config:
    e assim que o segundo par de atalhos consegue ter a sua propria regra de
    envio (uma tecla so escreve, a outra escreve e envia).
    """
    acao = (cfg.get("action_on_stop") or "paste").lower()
    if enter is None:
        enter = bool(cfg.get("press_enter_after"))

    if acao == "clipboard":
        return copiar(texto), "copiado para a area de transferencia"
    if acao == "type":
        return digitar(texto, enter), "digitado na janela ativa"
    if acao == "webhook":
        ok, detalhe = enviar_webhook(
            cfg.get("webhook_url", ""), cfg.get("webhook_field", "texto"), texto
        )
        return ok, "webhook: " + detalhe
    return colar(texto, enter), "colado na janela ativa"
