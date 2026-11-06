
from pathlib import Path
import os

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

config = os.environ.get("REMUNEROMETRO_DATA")

if not config:
    raise RuntimeError(
        "Configure REMUNEROMETRO_DATA com o diretório externo de dados."
    )

RAIZ_DADOS = Path(config).expanduser().resolve()

if not RAIZ_DADOS.is_dir():
    raise FileNotFoundError(
        f"Diretório de dados não encontrado: {RAIZ_DADOS}"
    )

BRONZE = RAIZ_DADOS / "bronze" / "rais_publica" / "2025"

PASTA_ANALISE = (
    RAIZ_DADOS / "analysis" / "remunerometro" / "v3"
)

PASTA_MODELOS = PASTA_ANALISE / "modelagem_dupla"

PASTA_DASH_LOCAL = PASTA_MODELOS / "dashboard"

PLANILHA_IBGE = (
    RAIZ_PROJETO / "Tipologia_municipal_rural_urbano.xlsx"
)

PASTA_PUBLICA = RAIZ_PROJETO / "data_public"