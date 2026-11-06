"""08 — Gera indicadores agregados do teste para revisão ANTES de publicar.

Entrada: C:/Users/uriel/data/analysis/remunerometro/v3/modelagem_dupla/dashboard/
Saída: <raiz do repositório>/data_public/indicadores_agregados.parquet

Nenhuma previsão individual é exportada. Células território x CBO abaixo de
LIMIAR não são exportadas. A revisão dos dados ANTES de publicar é obrigatória.
Este arquivo NÃO é substituto direto do dataset municipal no app.py atual.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

from caminhos import RAIZ_PROJETO, PASTA_DASH_LOCAL

DADOS = PASTA_DASH_LOCAL
ENTRADA = DADOS / "indicadores_teste_municipio_cbo.parquet"
SAIDA = RAIZ_PROJETO / "data_public" / "indicadores_agregados.parquet"
LIMIAR = 30
CHAVES = ["territorio_id", "territorio_nome", "grupo_ocupacional", "cbo"]
SOMAS = ["n", "soma_obs", "soma_prev_familias", "soma_abs_familias",
         "soma_sqlog_familias", "soma_prev_cbos", "soma_abs_cbos", "soma_sqlog_cbos"]

def executar():
    if not ENTRADA.exists():
        raise FileNotFoundError(f"Execute antes o script 07: {ENTRADA}")
    df = pd.read_parquet(ENTRADA, columns=CHAVES + SOMAS)
    for col in SOMAS:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if df[SOMAS].isna().any().any() or (df["n"] < 0).any():
        raise ValueError("Nulos ou contagens negativas nos indicadores de entrada.")
    agg = df.groupby(CHAVES, dropna=False, observed=True, as_index=False)[SOMAS].sum()
    agg = agg.loc[agg["n"] >= LIMIAR].copy()
    if agg.empty:
        raise ValueError("Nenhuma célula atinge o limiar configurado.")
    agg = agg.sort_values(CHAVES, kind="stable").reset_index(drop=True)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    agg.to_parquet(SAIDA, index=False, compression="zstd")
    print(f"[OK] {len(agg):,} células território × CBO, todas com n >= {LIMIAR}.")
    print(f"[ARQUIVO] {SAIDA}")
    print("[ATENÇÃO] Revise conteúdo, tamanho e risco de divulgação antes do git add.")
    print("[ATENÇÃO] Dashboard local ainda usa o arquivo municipal original; adaptar para nuvem.")

if __name__ == "__main__":
    executar()
