"""Checagem de ambiente + download do modelo. Uso: python -m vozflow.diagnostico"""

from __future__ import annotations

import sys

from . import config, modelo
from .transcriber import _cuda_disponivel, _prepare_cuda_dlls


def main() -> int:
    cfg = config.load()
    nome = sys.argv[1] if len(sys.argv) > 1 else cfg.get("model", "auto")

    print("=" * 60)
    print("VozFlow - diagnostico")
    print("=" * 60)
    print("Python           :", sys.version.split()[0])
    print("Config           :", config.CONFIG_PATH)

    # --- microfones ---
    try:
        from .audio import SpeechDetector, list_input_devices

        devs = list_input_devices()
        print("Entradas de audio:", len(devs), "encontradas")
        for idx, nome_dev in devs[:8]:
            print("   [" + str(idx) + "]", nome_dev)
        print("VAD              :", SpeechDetector().backend)
    except Exception as exc:  # noqa: BLE001
        print("ERRO no audio     :", exc)

    # --- GPU ---
    _prepare_cuda_dlls()
    cuda = _cuda_disponivel()
    print("CUDA visivel     :", "sim" if cuda else "nao (vai rodar em CPU)")

    # --- modelo ---
    from faster_whisper import WhisperModel

    # "auto" vira o modelo leve na CPU e o grande na GPU (modelo.resolver_nome):
    # valida os dois que o app pode carregar nesta maquina.
    na_cpu = modelo.resolver_nome(nome, "cpu")
    print("Baixando/validando modelo:", na_cpu, "(pode demorar na primeira vez)")
    try:
        WhisperModel(na_cpu, device="cpu", compute_type="int8")
        print("Modelo em disco  : ok")
    except Exception as exc:  # noqa: BLE001
        print("ERRO ao baixar   :", exc)
        return 1

    if cuda:
        na_gpu = modelo.resolver_nome(nome, "cuda")
        print("Modelo para a GPU:", na_gpu)
        try:
            WhisperModel(na_gpu, device="cuda", compute_type="float16")
            print("Modelo na GPU    : ok (float16)")
        except Exception as exc:  # noqa: BLE001
            print("GPU indisponivel :", exc)
            print("  -> instale: pip install -r requirements-gpu.txt")
            print("  -> o app cai automaticamente para CPU, so fica mais lento")

    print("=" * 60)
    print("Tudo certo. Rode o VozFlow com: VozFlow.vbs (ou python main.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
