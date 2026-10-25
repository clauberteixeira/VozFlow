"""Rede contra loop de repeticao e eco do prompt (vozflow/texto.py)."""

from vozflow import texto


def test_loop_patologico_e_cortado_em_duas_repeticoes():
    assert texto.colapsar_repeticoes("19, 19, 19, 19, 19") == "19, 19,"


def test_repeticao_natural_da_fala_e_preservada():
    frase = "nao, nao, eu quero muito muito isso"
    assert texto.colapsar_repeticoes(frase) == frase


def test_ngrama_repetido_tambem_e_cortado():
    assert texto.colapsar_repeticoes("a b a b a b a b fim") == "a b a b fim"


def test_texto_curto_passa_intacto():
    assert texto.colapsar_repeticoes("oi oi") == "oi oi"


def test_eco_do_prompt_e_removido():
    saida = texto.remover_eco_do_prompt(
        "Ola. Clauber, VozFlow, Whisper. Tudo bem?", "Clauber, VozFlow, Whisper"
    )
    assert saida == "Ola. Tudo bem?"


def test_fala_curta_que_esta_no_vocabulario_nao_e_comida():
    # menos de 3 palavras: pode ser fala legitima
    assert texto.remover_eco_do_prompt("VozFlow.", "Clauber, VozFlow") == "VozFlow."


def test_sem_prompt_nada_muda():
    assert texto.remover_eco_do_prompt("qualquer coisa", "") == "qualquer coisa"


def test_chave_ignora_acento_pontuacao_e_caixa():
    assert texto._chave("Coração!") == texto._chave("coracao")


def test_limpar_normaliza_espacos():
    assert texto.limpar("  oi   oi  ") == "oi oi"
    assert texto.limpar("") == ""
