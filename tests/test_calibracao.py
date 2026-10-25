"""Calculo do limiar voz x ambiente (vozflow/calibracao.py)."""

import numpy as np
import pytest

from vozflow.calibracao import calcular_limiar


def test_limiar_fica_na_media_geometrica():
    fundo = np.full(40, 0.001)
    voz = np.full(40, 0.05)
    limiar, aviso = calcular_limiar(fundo, voz)
    assert aviso == ""
    assert limiar == pytest.approx(np.sqrt(0.001 * 0.05))


def test_pouca_voz_nao_calibra():
    fundo = np.full(40, 0.001)
    voz = np.concatenate([np.full(3, 0.05), np.full(37, 0.001)])
    limiar, aviso = calcular_limiar(fundo, voz)
    assert limiar == 0.0
    assert "Nao ouvi voz" in aviso


def test_voz_perto_do_ambiente_nao_calibra():
    fundo = np.full(40, 0.01)
    voz = np.full(40, 0.03)
    limiar, aviso = calcular_limiar(fundo, voz)
    assert limiar == 0.0
    assert "perto demais" in aviso


def test_limiar_nunca_colado_no_ambiente():
    fundo = np.full(40, 0.001)
    voz = np.full(40, 0.02)
    limiar, _ = calcular_limiar(fundo, voz)
    assert limiar >= 0.003      # pelo menos 3x o ambiente


def test_com_limites_em_conflito_vale_o_teto_da_voz():
    # voz so 4,5x acima do ambiente: 3x o fundo passaria de 0,45x a voz, e o
    # teto (aplicado por ultimo) ganha - o corte nunca encosta na propria voz
    fundo = np.full(40, 0.001)
    voz = np.full(40, 0.0045)
    limiar, _ = calcular_limiar(fundo, voz)
    assert limiar == pytest.approx(0.0045 * 0.45)
