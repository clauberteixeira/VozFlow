"""Mensagens de falha do download do modelo (vozflow/modelo.py)."""

from vozflow import modelo


def test_sem_internet():
    msg = modelo.explicar_falha(OSError("Connection refused"))
    assert "sem acesso a internet" in msg


def test_sem_espaco():
    msg = modelo.explicar_falha(OSError("[Errno 28] No space left on device"))
    assert "espaco em disco" in msg


def test_acesso_negado():
    assert "recusou o acesso" in modelo.explicar_falha(RuntimeError("401 Client Error"))


def test_erro_desconhecido_e_truncado():
    msg = modelo.explicar_falha(RuntimeError("x" * 500))
    assert msg.startswith("Nao consegui baixar o modelo: ")
    assert len(msg) <= len("Nao consegui baixar o modelo: ") + 160


def test_tamanho_conhecido_do_modelo_padrao():
    assert modelo.TAMANHOS_MB["large-v3-turbo"] > 1000
