"""Atualizacao automatica (vozflow/atualizador.py).

Nada aqui acessa a rede nem roda instalador: o GitHub, o download e o
Popen sao falsos.
"""

import hashlib
import io
import json

import pytest

from vozflow import atualizador as atu
from vozflow import config

BASE = atu.PREFIXO_DOWNLOAD + "v9.9.9/"
CONTEUDO = b"instalador falso" * 1000
HASH = hashlib.sha256(CONTEUDO).hexdigest()


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        self.close()


def _release(**mudar):
    dados = {
        "tag_name": "v9.9.9", "draft": False, "prerelease": False,
        "assets": [
            {"name": "VozFlow-9.9.9-instalador.exe", "size": len(CONTEUDO),
             "browser_download_url": BASE + "VozFlow-9.9.9-instalador.exe"},
            {"name": "VozFlow-9.9.9-instalador.exe.sha256", "size": 95,
             "browser_download_url": BASE + "VozFlow-9.9.9-instalador.exe.sha256"},
        ],
    }
    dados.update(mudar)
    return dados


def _rede(release=None, conteudo=CONTEUDO, hash_publicado=HASH):
    """urlopen falso: responde a API, o .sha256 e o .exe; anota as URLs."""
    pedidas = []

    def abrir(req, timeout=None):  # noqa: ARG001
        url = req.full_url
        pedidas.append(url)
        if url == atu.API:
            return Resposta(json.dumps(release or _release()).encode())
        if url.endswith(".sha256"):
            return Resposta(f"{hash_publicado}  VozFlow-9.9.9-instalador.exe\n".encode())
        if url.endswith(".exe"):
            return Resposta(conteudo)
        raise AssertionError("URL inesperada: " + url)

    abrir.pedidas = pedidas
    return abrir


# ----------------------------------------------------------------------
# versao e consulta
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("texto", "esperado"), [
    ("v1.2.3", (1, 2, 3)), ("1.2.10", (1, 2, 10)), ("v2.0", (2, 0)),
    ("", None), (None, None), ("v1.2.3-beta", None), ("latest", None),
])
def test_versao(texto, esperado):
    assert atu.versao(texto) == esperado


def test_1_2_10_e_mais_nova_que_1_2_9():
    """Comparar como texto diria o contrario."""
    lanc = atu.Lancamento("1.2.10", "", "", 0)
    assert atu.e_mais_nova(lanc, atual="1.2.9")
    assert not atu.e_mais_nova(lanc, atual="1.2.10")
    assert not atu.e_mais_nova(lanc, atual="1.3.0")
    assert not atu.e_mais_nova(None)


def test_consulta_acha_instalador_e_hash():
    lanc = atu.consultar(_rede())
    assert lanc.versao == "9.9.9"
    assert lanc.url_instalador == BASE + "VozFlow-9.9.9-instalador.exe"
    assert lanc.url_hash.endswith(".sha256")


@pytest.mark.parametrize("mudar", [
    {"draft": True},
    {"prerelease": True},
    {"tag_name": "nightly"},
    {"assets": []},
    {"assets": [_release()["assets"][0]]},                   # sem o .sha256
])
def test_release_incompleta_ou_de_teste_e_ignorada(mudar):
    assert atu.consultar(_rede(_release(**mudar))) is None


def test_anexo_de_outro_endereco_e_recusado():
    """So aceita download da propria Release do repositorio."""
    rel = _release()
    rel["assets"][0]["browser_download_url"] = "https://exemplo.invalido/VozFlow-9.9.9-instalador.exe"
    assert atu.consultar(_rede(rel)) is None


# ----------------------------------------------------------------------
# download
# ----------------------------------------------------------------------
def _lanc():
    return atu.Lancamento("9.9.9", BASE + "VozFlow-9.9.9-instalador.exe",
                          BASE + "VozFlow-9.9.9-instalador.exe.sha256", len(CONTEUDO))


def test_baixa_e_confere_o_hash(tmp_path):
    caminho = atu.baixar(_lanc(), tmp_path, _rede())
    assert caminho == tmp_path / "VozFlow-9.9.9-instalador.exe"
    assert caminho.read_bytes() == CONTEUDO
    assert not list(tmp_path.glob("*.part"))


def test_hash_que_nao_confere_apaga_o_arquivo(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        atu.baixar(_lanc(), tmp_path, _rede(conteudo=b"trocado no caminho"))
    assert list(tmp_path.iterdir()) == []


def test_hash_publicado_ilegivel_nao_baixa(tmp_path):
    rede = _rede(hash_publicado="nao-e-hash")
    assert atu.baixar(_lanc(), tmp_path, rede) is None
    assert not any(u.endswith(".exe") for u in rede.pedidas)


def test_ja_baixado_e_conferido_nao_baixa_de_novo(tmp_path):
    (tmp_path / "VozFlow-9.9.9-instalador.exe").write_bytes(CONTEUDO)
    rede = _rede()
    assert atu.baixar(_lanc(), tmp_path, rede) is not None
    assert not any(u.endswith(".exe") for u in rede.pedidas)


def test_limpa_instaladores_usados_e_pela_metade(tmp_path):
    for nome in ("VozFlow-1.2.2-instalador.exe", "VozFlow-1.2.3-instalador.exe",
                 "VozFlow-1.2.4-instalador.exe", "VozFlow-1.2.5-instalador.exe.part",
                 "outra-coisa.txt"):
        (tmp_path / nome).write_bytes(b"x")
    atu.limpar_antigos(tmp_path, atual="1.2.3")
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "VozFlow-1.2.4-instalador.exe", "outra-coisa.txt"]


def test_instalador_roda_silencioso_e_reabre():
    chamadas = []
    atu.instalar(atu.Path("C:/x/VozFlow-9.9.9-instalador.exe"),
                 popen=lambda args, **kw: chamadas.append((args, kw)))
    args, kw = chamadas[0]
    assert args[0].endswith("VozFlow-9.9.9-instalador.exe")
    assert {"/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/REABRIR=1"} <= set(args)
    assert kw["close_fds"] is True


# ----------------------------------------------------------------------
# quando instalar
# ----------------------------------------------------------------------
@pytest.fixture
def montar(qapp, monkeypatch):
    def criar(ocupado=False, parado=999.0, auto=True):
        instalados = []
        cfg = config.Config(dict(config.DEFAULTS, atualizar_auto=auto))
        monkeypatch.setattr(atu, "segundos_parado", lambda: parado)
        a = atu.Atualizador(cfg, lambda: ocupado, lambda v, c: instalados.append((v, c)),
                            ativo=True)
        a.pendente = ("9.9.9", "C:/x/VozFlow-9.9.9-instalador.exe")
        a.instalados = instalados
        return a
    return criar


def test_instala_com_o_pc_parado(montar):
    a = montar()
    a._tentar_instalar()
    assert a.instalados == [("9.9.9", atu.Path("C:/x/VozFlow-9.9.9-instalador.exe"))]
    assert a.pendente is None


def test_nao_instala_no_meio_de_uma_ditada(montar):
    a = montar(ocupado=True)
    a._imediato = True                      # nem quando foi pedido pelo menu
    a._tentar_instalar()
    assert a.instalados == []


def test_automatico_espera_o_pc_ficar_parado(montar):
    a = montar(parado=5.0)
    a._tentar_instalar()
    assert a.instalados == []


def test_pedido_pelo_menu_nao_espera_o_pc_parar(montar):
    a = montar(parado=0.0)
    a._imediato = True
    a._tentar_instalar()
    assert len(a.instalados) == 1


def test_desligado_nao_instala_sozinho(montar):
    a = montar(auto=False)
    a._tentar_instalar()
    assert a.instalados == []


def test_codigo_fonte_nunca_se_atualiza(qapp):
    """Rodando do python main.py (sem sys.frozen), nada e consultado."""
    a = atu.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False, lambda v, c: None)
    assert a.ativo is False
    avisos = []
    a.aviso.connect(avisos.append)
    a.verificar(pedido=True)
    assert a._thread is None
    assert avisos and "instalada" in avisos[0]


def test_procura_pelo_menu_com_atualizacao_ja_baixada_instala_logo(montar):
    a = montar(parado=0.0)
    a.verificar(pedido=True)
    assert a._imediato is True and a._thread is None
    a._tentar_instalar()
    assert len(a.instalados) == 1


def test_trabalho_completo_baixa_e_agenda(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(atu, "consultar", lambda: _lanc())
    monkeypatch.setattr(atu, "baixar", lambda lanc: tmp_path / lanc.nome_arquivo)
    a = atu.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False,
                        lambda v, c: None, ativo=True)
    a._trabalho(pedido=False)
    qapp.processEvents()
    assert a.pendente == ("9.9.9", str(tmp_path / "VozFlow-9.9.9-instalador.exe"))
    assert a._timer_instalar.isActive()
    a._timer_instalar.stop()


def test_sem_internet_nao_quebra(qapp, monkeypatch):
    def falha():
        raise OSError("sem rede")
    monkeypatch.setattr(atu, "consultar", falha)
    a = atu.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False,
                        lambda v, c: None, ativo=True)
    avisos = []
    a.aviso.connect(avisos.append)
    a._trabalho(pedido=True)
    qapp.processEvents()
    assert a.pendente is None
    assert avisos and "sem rede" in avisos[0]


def test_padrao_e_atualizar_sozinho(pasta_config):
    assert config.load()["atualizar_auto"] is True
