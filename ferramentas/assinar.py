"""Assina o instalador para a atualizacao automatica aceitar.

    python ferramentas\\assinar.py gerar-chave
        Cria a chave privada (uma vez so) e mostra a chave publica, que vai em
        vozflow/atualizador.py (CHAVE_PUBLICA).

    python ferramentas\\assinar.py instalador\\VozFlow-1.2.4-instalador.exe
        Grava VozFlow-1.2.4-instalador.exe.sig ao lado. Publique o .sig na
        Release junto com o instalador.

A chave privada fica em %USERPROFILE%\\.vozflow-assinatura\\, FORA do
repositorio e do GitHub - e o que impede uma conta do GitHub invadida de
publicar um instalador que todo VozFlow aceitaria. Guarde uma copia dela num
lugar seguro: sem ela, as versoes novas nao sao aceitas pelos apps ja
instalados (seria preciso reinstalar a mao uma versao com chave nova).
"""

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vozflow import assinatura  # noqa: E402

PASTA = Path(os.environ.get("VOZFLOW_PASTA_CHAVE") or Path.home() / ".vozflow-assinatura")
CHAVE = PASTA / "chave-privada.txt"


def gerar_chave() -> None:
    if CHAVE.exists():
        sys.exit(f"Ja existe uma chave em {CHAVE}. Nao sobrescrevo.")
    PASTA.mkdir(parents=True, exist_ok=True)
    secreta = os.urandom(32)
    CHAVE.write_text(secreta.hex() + "\n", encoding="ascii")
    print("Chave privada:", CHAVE)
    print("Chave publica:", assinatura.chave_publica(secreta).hex())


def assinar(exe: Path) -> Path:
    secreta = bytes.fromhex(CHAVE.read_text(encoding="ascii").strip())
    h = hashlib.sha256()
    with open(exe, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    msg = assinatura.mensagem(exe.name, h.hexdigest())
    sig = assinatura.assinar(secreta, msg)
    publica = assinatura.chave_publica(secreta)
    assert assinatura.conferir(publica, msg, sig)
    saida = exe.with_name(exe.name + ".sig")
    saida.write_text(sig.hex() + "\n", encoding="ascii")
    print("Assinado:", saida)
    print("Chave publica usada:", publica.hex())
    return saida


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if sys.argv[1] == "gerar-chave":
        gerar_chave()
    else:
        assinar(Path(sys.argv[1]))
