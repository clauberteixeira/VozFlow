"""Atualizacao automatica (vozflow/atualizador.py, assinatura.py).

Nada aqui acessa a rede nem roda instalador: o GitHub, o download e o
Popen sao falsos. A chave de assinatura dos testes e gerada aqui; a de
verdade fica fora do repositorio.
"""

import hashlib
import io
import json
import re
import urllib.error
from pathlib import Path

import pytest

from vozflow import __version__, assinatura, config
from vozflow import atualizador as atu

RAIZ = Path(__file__).resolve().parent.parent
TAG = "v9.9.9"
NOME = "VozFlow-9.9.9-instalador.exe"
BASE = f"https://github.com/{atu.REPO}/releases/download/{TAG}/"
CONTEUDO = b"instalador falso" * 1000
SECRETA = bytes(range(32))
PUBLICA = assinatura.chave_publica(SECRETA)


def _sig(conteudo=CONTEUDO, nome=NOME, secreta=SECRETA):
    sha = hashlib.sha256(conteudo).hexdigest()
    return assinatura.assinar(secreta, assinatura.mensagem(nome, sha)).hex()


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        self.close()


def _release(**mudar):
    dados = {
        "tag_name": TAG, "draft": False, "prerelease": False,
        "assets": [
            {"name": NOME, "size": len(CONTEUDO), "browser_download_url": BASE + NOME},
            {"name": NOME + ".sig", "size": 129, "browser_download_url": BASE + NOME + ".sig"},
        ],
    }
    dados.update(mudar)
    return dados


def _rede(release=None, conteudo=CONTEUDO, sig=None):
    """urlopen falso: responde a API, o .sig e o .exe; anota as URLs."""
    pedidas = []

    def abrir(req, timeout=None):  # noqa: ARG001
        url = req.full_url
        pedidas.append(url)
        if url == atu.API:
            return Resposta(json.dumps(release or _release()).encode())
        if url.endswith(".sig"):
            return Resposta(((sig if sig is not None else _sig()) + "\n").encode())
        if url.endswith(".exe"):
            return Resposta(conteudo)
        raise AssertionError("URL inesperada: " + url)

    abrir.pedidas = pedidas
    return abrir


def _lanc(tamanho=len(CONTEUDO)):
    return atu.Lancamento("9.9.9", BASE + NOME, BASE + NOME + ".sig", tamanho)


# ----------------------------------------------------------------------
# assinatura Ed25519
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("secreta", "publica", "msg", "sig"), [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e3970"
     "1cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613"
     "d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
])
def test_vetores_da_rfc_8032(secreta, publica, msg, sig):
    secreta, publica, msg, sig = map(bytes.fromhex, (secreta, publica, msg, sig))
    assert assinatura.chave_publica(secreta) == publica
    assert assinatura.assinar(secreta, msg) == sig
    assert assinatura.conferir(publica, msg, sig)


def test_assinatura_recusa_adulteracao():
    msg = assinatura.mensagem(NOME, "ab" * 32)
    sig = assinatura.assinar(SECRETA, msg)
    assert assinatura.conferir(PUBLICA, msg, sig)
    assert not assinatura.conferir(PUBLICA, msg + b"x", sig)
    assert not assinatura.conferir(PUBLICA, msg, sig[:-1] + bytes([sig[-1] ^ 1]))
    assert not assinatura.conferir(assinatura.chave_publica(bytes(32)), msg, sig)   # outra chave
    s_grande = (int.from_bytes(sig[32:], "little") + assinatura.q).to_bytes(32, "little")
    assert not assinatura.conferir(PUBLICA, msg, sig[:32] + s_grande)   # s >= q (maleavel)
    assert not assinatura.conferir(PUBLICA, msg, sig[:63])


def test_chave_de_ordem_pequena_e_recusada():
    """Com a identidade como chave, R = identidade e s = 0 "confeririam"."""
    identidade = (1).to_bytes(32, "little")
    assert not assinatura.conferir(identidade, b"qualquer", identidade + bytes(32))


def test_codificacao_nao_canonica_e_recusada():
    """y = p-1 com bit de sinal 1 decodificava para x = p."""
    nao_canonica = ((assinatura.p - 1) | (1 << 255)).to_bytes(32, "little")
    assert assinatura._descomprimir(nao_canonica) is None


def test_app_tem_a_chave_publica_de_verdade():
    assert len(atu.CHAVE_PUBLICA) == 32
    assert atu.CHAVE_PUBLICA != PUBLICA


# ----------------------------------------------------------------------
# versao e consulta
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("texto", "esperado"), [
    ("v1.2.3", (1, 2, 3)), ("1.2.10", (1, 2, 10)), ("v2.0", (2, 0)),
    ("", None), (None, None), ("v1.2.3-beta", None), ("latest", None),
])
def test_versao(texto, esperado):
    assert atu.versao(texto) == esperado


def test_comparacao_de_versao():
    """1.2.10 > 1.2.9 (como texto seria o contrario) e 1.2.0 == 1.2."""
    assert atu.e_mais_nova(atu.Lancamento("1.2.10", "", "", 0), atual="1.2.9")
    assert not atu.e_mais_nova(atu.Lancamento("1.2.10", "", "", 0), atual="1.2.10")
    assert not atu.e_mais_nova(atu.Lancamento("1.2.0", "", "", 0), atual="1.2")
    assert not atu.e_mais_nova(atu.Lancamento("1.2.4", "", "", 0), atual="1.3.0")
    assert not atu.e_mais_nova(None)


def test_versao_do_instalador_bate_com_a_do_app():
    """Duas fontes de versao: se divergirem, o app reinstalaria a mesma
    versao para sempre (o instalador "1.2.4" abriria um app que diz 1.2.3)."""
    iss = (RAIZ / "instalador.iss").read_text(encoding="utf-8")
    assert re.search(r'#define Versao\s+"([^"]+)"', iss).group(1) == __version__


def test_consulta_acha_instalador_e_assinatura():
    lanc = atu.consultar(_rede())
    assert (lanc.versao, lanc.url_instalador, lanc.url_assinatura) == (
        "9.9.9", BASE + NOME, BASE + NOME + ".sig")


@pytest.mark.parametrize("mudar", [
    {"draft": True},
    {"prerelease": True},
    {"tag_name": "nightly"},
    {"assets": []},
    {"assets": [_release()["assets"][0]]},                   # sem a assinatura
])
def test_release_incompleta_ou_de_teste_e_ignorada(mudar):
    assert atu.consultar(_rede(_release(**mudar))) is None


@pytest.mark.parametrize("url", [
    "https://exemplo.invalido/" + NOME,
    BASE + "../../../../../outro/repo/" + NOME,
    BASE + NOME + "?x=1",
    BASE.replace("https", "http") + NOME,
])
def test_anexo_fora_do_endereco_exato_e_recusado(url):
    rel = _release()
    rel["assets"][0]["browser_download_url"] = url
    assert atu.consultar(_rede(rel)) is None


def test_repositorio_sem_versao_publicada():
    def abrir(req, timeout=None):  # noqa: ARG001
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    with pytest.raises(atu.SemVersaoPublicada):
        atu.consultar(abrir)


# ----------------------------------------------------------------------
# download
# ----------------------------------------------------------------------
def test_baixa_e_confere_a_assinatura(tmp_path):
    caminho = atu.baixar(_lanc(), tmp_path, _rede(), chave=PUBLICA)
    assert caminho == tmp_path / NOME
    assert caminho.read_bytes() == CONTEUDO
    assert not list(tmp_path.glob("*.part"))


def test_instalador_trocado_e_apagado(tmp_path):
    """Quem trocou o instalador nao tem a chave privada para assinar o novo."""
    trocado = b"malicioso" * 100
    with pytest.raises(ValueError, match="assinatura"):
        atu.baixar(_lanc(len(trocado)), tmp_path, _rede(conteudo=trocado), chave=PUBLICA)
    assert list(tmp_path.iterdir()) == []


def test_assinatura_de_outra_chave_e_recusada(tmp_path):
    rede = _rede(sig=_sig(secreta=bytes(32)))
    with pytest.raises(ValueError, match="assinatura"):
        atu.baixar(_lanc(), tmp_path, rede, chave=PUBLICA)


def test_assinatura_de_outra_versao_nao_serve(tmp_path):
    """A assinatura cobre o NOME (com a versao): nao da para reaproveitar a de
    uma versao antiga num instalador antigo renomeado."""
    rede = _rede(sig=_sig(nome="VozFlow-1.0.0-instalador.exe"))
    with pytest.raises(ValueError, match="assinatura"):
        atu.baixar(_lanc(), tmp_path, rede, chave=PUBLICA)


def test_download_incompleto_e_recusado(tmp_path):
    with pytest.raises(ValueError, match="incompleto"):
        atu.baixar(_lanc(len(CONTEUDO) + 10), tmp_path, _rede(), chave=PUBLICA)


def test_ja_baixado_e_assinado_nao_baixa_de_novo(tmp_path):
    (tmp_path / NOME).write_bytes(CONTEUDO)
    rede = _rede()
    assert atu.baixar(_lanc(), tmp_path, rede, chave=PUBLICA) == tmp_path / NOME
    assert not any(u.endswith(".exe") for u in rede.pedidas)


def test_arquivo_antigo_adulterado_e_baixado_de_novo(tmp_path):
    (tmp_path / NOME).write_bytes(b"adulterado")
    rede = _rede()
    atu.baixar(_lanc(), tmp_path, rede, chave=PUBLICA)
    assert (tmp_path / NOME).read_bytes() == CONTEUDO
    assert any(u.endswith(".exe") for u in rede.pedidas)


def test_limpa_instaladores_usados_e_pela_metade(tmp_path):
    for nome in ("VozFlow-1.2.2-instalador.exe", "VozFlow-1.2.3-instalador.exe",
                 "VozFlow-1.2.4-instalador.exe", "VozFlow-1.2.5-instalador.exe.part",
                 "estado.json"):
        (tmp_path / nome).write_bytes(b"x")
    atu.limpar_antigos(tmp_path, atual="1.2.3")
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "VozFlow-1.2.4-instalador.exe", "estado.json"]


def test_instalador_roda_silencioso_reabre_e_sabe_voltar(monkeypatch):
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "x")
    monkeypatch.setenv("_MEIPASS2", "y")
    chamadas = []
    atu.instalar(Path("C:/x/" + NOME), popen=lambda args, **kw: chamadas.append((args, kw)),
                 voltar="C:/Programas/VozFlow/VozFlow.exe")
    args, kw = chamadas[0]
    assert args[0].endswith(NOME)
    assert {"/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/REABRIR=1",
            "/VOLTAR=C:/Programas/VozFlow/VozFlow.exe"} <= set(args)
    assert kw["close_fds"] is True
    assert "_PYI_APPLICATION_HOME_DIR" not in kw["env"] and "_MEIPASS2" not in kw["env"]
    assert kw["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


# ----------------------------------------------------------------------
# quando instalar
# ----------------------------------------------------------------------
@pytest.fixture
def montar(qapp, monkeypatch, tmp_path):
    def criar(ocupado=False, parado=999.0, auto=True):
        instalados = []
        cfg = config.Config(dict(config.DEFAULTS, atualizar_auto=auto))
        monkeypatch.setattr(atu, "segundos_parado", lambda: parado)
        a = atu.Atualizador(cfg, lambda: ocupado, lambda v, c: instalados.append((v, c)),
                            ativo=True, pasta=tmp_path)
        a.pendente = ("9.9.9", "C:/x/" + NOME)
        a.instalados = instalados
        return a
    return criar


def test_instala_com_o_pc_parado(montar):
    a = montar()
    a._tentar_instalar()
    assert a.instalados == [("9.9.9", Path("C:/x/" + NOME))]
    assert a.pendente is None
    assert "tentada" not in atu.ler_estado(a.pasta)      # so ao disparar o instalador


def test_marcar_tentativa_limpa_falha_anterior(montar):
    a = montar()
    atu.gravar_estado({"vista": "1.0", "falhou": "9.9.8"}, a.pasta)
    a.marcar_tentativa("9.9.9")
    assert atu.ler_estado(a.pasta) == {"vista": "1.0", "tentada": {"versao": "9.9.9"}}


def test_procura_sem_novidade_nao_apressa_a_proxima_automatica(montar, monkeypatch):
    """Um "ja esta na mais nova" pelo menu nao pode fazer a proxima
    atualizacao automatica pular a espera do PC parado."""
    monkeypatch.setattr(atu, "consultar", lambda: None)       # sem rede
    a = montar(parado=0.0)
    a.pendente = None
    a.verificar(pedido=True)
    a._thread.join(5)
    a._ao_baixar("9.9.9", "C:/x/" + NOME, False)
    assert a._imediato is False and a._timer_instalar.interval() == 30_000
    a._timer_instalar.stop()
    a._tentar_instalar()
    assert a.instalados == []


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


def test_adiar_volta_a_esperar_sem_contar_tentativa(montar):
    a = montar()
    a._tentar_instalar()
    a.adiar("9.9.9", "C:/x/" + NOME)
    assert a.pendente == ("9.9.9", "C:/x/" + NOME)
    assert "tentada" not in atu.ler_estado(a.pasta)
    assert a._timer_instalar.isActive()
    a._timer_instalar.stop()


def test_procura_pelo_menu_durante_download_instala_logo_ao_terminar(montar):
    a = montar(parado=0.0)
    a.pendente = None

    class Viva:
        def is_alive(self):
            return True
    a._thread = Viva()
    a.verificar(pedido=True)
    assert a._imediato is True
    a._ao_baixar("9.9.9", "C:/x/" + NOME, False)     # o download automatico terminou
    assert a._timer_instalar.interval() == 2000
    a._timer_instalar.stop()
    a._tentar_instalar()
    assert len(a.instalados) == 1


def test_codigo_fonte_nunca_se_atualiza(qapp):
    """Rodando do python main.py (sem sys.frozen), nada e consultado."""
    a = atu.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False, lambda v, c: None)
    assert a.ativo is False
    avisos = []
    a.aviso.connect(avisos.append)
    a.verificar(pedido=True)
    assert a._thread is None
    assert avisos and "instalada" in avisos[0]
    assert a.conferir_abertura() is None


# ----------------------------------------------------------------------
# abertura: atualizou? falhou?
# ----------------------------------------------------------------------
def _atualizador(tmp_path):
    return atu.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False,
                           lambda v, c: None, ativo=True, pasta=tmp_path)


def test_avisa_que_atualizou(tmp_path, qapp):
    atu.gravar_estado({"vista": "0.0.1", "tentada": {"versao": __version__}}, tmp_path)
    a = _atualizador(tmp_path)
    assert __version__ in a.conferir_abertura()
    assert atu.ler_estado(tmp_path) == {"vista": __version__}
    assert a.conferir_abertura() is None                 # so uma vez


def test_primeira_abertura_nao_avisa(tmp_path, qapp):
    assert _atualizador(tmp_path).conferir_abertura() is None
    assert atu.ler_estado(tmp_path)["vista"] == __version__


def test_instalacao_que_falhou_nao_tenta_sozinha_de_novo(tmp_path, qapp, monkeypatch):
    """Abriu numa versao menor que a tentada: a instalacao falhou. Sem isto o
    app fecharia de novo a cada minuto parado, sem nunca conseguir."""
    atu.gravar_estado({"vista": __version__, "tentada": {"versao": "99.0.0"}}, tmp_path)
    a = _atualizador(tmp_path)
    msg = a.conferir_abertura()
    assert "99.0.0" in msg and "nao terminou" in msg
    assert atu.ler_estado(tmp_path)["falhou"] == "99.0.0"

    monkeypatch.setattr(atu, "consultar", lambda: atu.Lancamento("99.0.0", "", "", 0))
    baixados = []
    monkeypatch.setattr(atu, "baixar", lambda lanc, pasta: baixados.append(lanc) or pasta / "x")
    a._trabalho(pedido=False)
    assert baixados == []                    # automatico: deixa quieto
    a._trabalho(pedido=True)
    assert len(baixados) == 1                # pelo menu: tenta
    qapp.processEvents()
    a._timer_instalar.stop()


def test_estado_travado_nao_e_regravado(tmp_path, qapp, monkeypatch):
    """Travado no boot (antivirus): regravar so com {"vista"} apagaria o
    "falhou" - e o app voltaria a fechar a cada minuto parado."""
    atu.gravar_estado({"vista": "0.0.1", "falhou": "99.0.0"}, tmp_path)
    antes = (tmp_path / "estado.json").read_bytes()
    real = Path.read_text

    def travado(self, *a, **k):
        if self.name == "estado.json":
            raise PermissionError("em uso")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", travado)
    assert atu.ler_estado(tmp_path) is None
    assert _atualizador(tmp_path).conferir_abertura() is None
    monkeypatch.undo()
    assert (tmp_path / "estado.json").read_bytes() == antes


def test_estado_travado_nao_tenta_sozinho(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(atu, "ler_estado", lambda pasta: None)
    monkeypatch.setattr(atu, "consultar", lambda: atu.Lancamento("99.0.0", "", "", 0))
    baixados = []
    monkeypatch.setattr(atu, "baixar", lambda lanc, pasta: baixados.append(lanc))
    _atualizador(tmp_path)._trabalho(pedido=False)
    assert baixados == []


def test_estado_ilegivel_nao_quebra(tmp_path, qapp):
    (tmp_path / "estado.json").write_text("{nao e json", encoding="utf-8")
    assert _atualizador(tmp_path).conferir_abertura() is None


def test_abrir_nao_regrava_a_config(tmp_path, qapp, pasta_config):
    """O estado vive fora do config.json: com ele travado no boot, o load()
    usa os padroes - regravar a config ali apagaria a do usuario."""
    config.CONFIG_PATH.write_text('{"historico_dias": 99}', encoding="utf-8")
    antes = config.CONFIG_PATH.read_bytes()
    atu.gravar_estado({"vista": "0.0.1"}, tmp_path)
    _atualizador(tmp_path).conferir_abertura()
    assert config.CONFIG_PATH.read_bytes() == antes


# ----------------------------------------------------------------------
# trabalho em segundo plano
# ----------------------------------------------------------------------
def test_trabalho_completo_baixa_e_agenda(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(atu, "consultar", lambda: _lanc())
    monkeypatch.setattr(atu, "baixar", lambda lanc, pasta: pasta / lanc.nome_arquivo)
    a = _atualizador(tmp_path)
    a._trabalho(pedido=False)
    qapp.processEvents()
    assert a.pendente == ("9.9.9", str(tmp_path / NOME))
    assert a._timer_instalar.isActive()
    a._timer_instalar.stop()


@pytest.mark.parametrize(("erro", "trecho"), [
    (OSError("sem rede"), "sem rede"),
    (atu.SemVersaoPublicada(), "mais nova"),
    (ValueError("a assinatura do instalador nao confere"), "descartada"),
])
def test_erros_viram_mensagem_so_quando_pedido(qapp, monkeypatch, tmp_path, erro, trecho):
    def falha():
        raise erro
    monkeypatch.setattr(atu, "consultar", falha)
    a = _atualizador(tmp_path)
    avisos = []
    a.aviso.connect(avisos.append)
    a._trabalho(pedido=False)
    qapp.processEvents()
    assert avisos == []                       # automatico: silencio
    a._trabalho(pedido=True)
    qapp.processEvents()
    assert avisos and trecho in avisos[0]
    assert a.pendente is None


def test_padrao_e_atualizar_sozinho(pasta_config):
    assert config.load()["atualizar_auto"] is True


# ----------------------------------------------------------------------
# o app: quando esta ocupado demais para fechar
# ----------------------------------------------------------------------
@pytest.mark.parametrize("estado", ["_quer_gravar", "_segurando", "_baixando"])
def test_app_ocupado_nao_fecha_para_atualizar(vozflow_app, estado):
    app, *_ = vozflow_app()
    assert app._ocupado_para_atualizar() is False
    setattr(app, estado, True)
    assert app._ocupado_para_atualizar() is True
    setattr(app, estado, False)


def test_app_ocupado_enquanto_entrega_o_texto(vozflow_app):
    """`recording` ja e False enquanto o fim da fala transcreve e e digitado."""
    app, *_ = vozflow_app()
    app._dones_pendentes = 1
    assert app._ocupado_para_atualizar() is True
    app._dones_pendentes = 0


def test_app_adia_se_comecou_a_ditar_antes_de_fechar(vozflow_app, monkeypatch):
    from vozflow import app as modulo_app

    app, *_ = vozflow_app()
    disparos = []
    monkeypatch.setattr(modulo_app, "instalar_atualizacao", lambda *a, **k: disparos.append(a))
    adiados = []
    monkeypatch.setattr(app.atualizador, "adiar", lambda v, c: adiados.append(v))
    app._quer_gravar = True
    app._fechar_para_atualizar("9.9.9", Path("C:/x/" + NOME))
    assert disparos == [] and adiados == ["9.9.9"]
    app._quer_gravar = False


def test_app_livre_dispara_marca_e_sai_de_vez(vozflow_app, monkeypatch):
    from vozflow import app as modulo_app

    app, *_ = vozflow_app()
    ordem = []
    monkeypatch.setattr(modulo_app, "instalar_atualizacao",
                        lambda caminho, voltar=None: ordem.append(("instalar", voltar)))
    monkeypatch.setattr(app.atualizador, "marcar_tentativa", lambda v: ordem.append(("marcar", v)))
    monkeypatch.setattr(app, "encerrar", lambda de_vez=False: ordem.append(("encerrar", de_vez)))
    app._fechar_para_atualizar("9.9.9", Path("C:/x/" + NOME))
    assert [o[0] for o in ordem] == ["instalar", "marcar", "encerrar"]
    assert ordem[0][1] and ordem[2][1] is True      # passa o /VOLTAR e sai de vez
