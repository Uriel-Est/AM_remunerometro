"""05 — Remunerômetro RAIS 2025: avaliação FINAL do teste intocado.

Execute no Positron a partir da raiz do repositório (Path.cwd()).
Pré-requisito: 04_treinar_modelos.py executado e seus artefatos preservados.

IMPORTANTÍSSIMO:
- NÃO divide dados, NÃO sorteia amostra, NÃO faz fit, NÃO ajusta alpha.
- Carrega os índices e os pipelines JÁ AJUSTADOS no script 04.
- Avalia o MESMO conjunto de teste para Famílias e para CBOs.
- Escreve apenas agregados: métricas, erros por grupos e figuras; não exporta
  previsão individual, salários individuais ou microdados RAIS.
- Bloqueia a reexecução sobre o teste quando o resultado já existe.
- Uma vez aberto o teste, NÃO utilize seus resultados para retreinar ou escolher
  hiperparâmetros. O conjunto de teste é avaliação final, não validação.

Dependências: pandas, numpy, pyarrow, scikit-learn, joblib, matplotlib.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import os
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from joblib import load
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error
from sklearn.utils.validation import check_is_fitted

# ------------------- Configurações locais ----------------------
from caminhos import PASTA_MODELOS

PASTA_BASE = PASTA_MODELOS
BASE = PASTA_BASE / "rais_2025_base_modelagem_dezembro.parquet"
TREINAMENTO = PASTA_BASE / "treinamento"
SAIDA = PASTA_BASE / "avaliacao_final"

# Não reduza esse mínimo para esconder categorias raras; grupos menores que
# o limite são reportados explicitamente como baixa amostra.
MINIMO_GRUPO = 30

CATEGORICAS_COMUNS = ["uf_sigla", "tipologia_ibge", "escolaridade", "cnae_divisao"]
NUMERICAS = ["idade", "horas"]
ESPECIFICACOES = {"familias": "grupo_ocupacional", "cbos": "cbo"}
ATRIBUTOS_AUDITORIA = ["sexo", "escolaridade", "grande_regiao", "tipologia_ibge", "grupo_ocupacional", "cbo"]


def sha256_arquivo(caminho: Path, tamanho_bloco: int = 2**20) -> str:
    digesto = hashlib.sha256()
    with caminho.open("rb") as arq:
        for bloco in iter(lambda: arq.read(tamanho_bloco), b""):
            digesto.update(bloco)
    return digesto.hexdigest()


def carregar_e_conferir_artefatos():
    obrigatorios = [
        BASE,
        TREINAMENTO / "indices_particao.npz",
        TREINAMENTO / "metadados_treino.json",
        TREINAMENTO / "comparacao_validacao_cruzada.csv",
        TREINAMENTO / "pipeline_familias_cv.joblib",
        TREINAMENTO / "pipeline_cbos_cv.joblib",
    ]
    ausentes = [str(p) for p in obrigatorios if not p.is_file()]
    if ausentes:
        raise FileNotFoundError("Arquivos necessários do 03/04 não encontrados:\n" + "\n".join(ausentes))
    meta = json.loads((TREINAMENTO / "metadados_treino.json").read_text(encoding="utf-8"))
    if meta.get("testes_abertos") is not False:
        raise ValueError("O JSON do 04 não identifica o teste como intocado. Verifique antes de prosseguir.")
    if meta.get("alvo") != "ln_rem_dez":
        raise ValueError("Alvo incompatível com a etapa 04 (esperado ln_rem_dez).")
    if meta.get("n_amostra") != 2000 or meta.get("dobras") != 5:
        raise ValueError("Os metadados não correspondem ao protocolo de 2.000 observações e 5 dobras.")
    if set(meta.get("selecionados_cv", {})) != set(ESPECIFICACOES):
        raise ValueError("Metadados não contêm as duas especificações esperadas.")

    with np.load(TREINAMENTO / "indices_particao.npz", allow_pickle=False) as indices:
        if set(indices.files) != {"treino", "teste", "amostra"}:
            raise ValueError("indices_particao.npz deveria conter treino, teste e amostra.")
        particao = {k: indices[k].copy() for k in indices.files}

    n = int(meta["n_populacao"])
    train, test, sample = (particao[k] for k in ("treino", "teste", "amostra"))
    for nome, idx in particao.items():
        if idx.ndim != 1 or not np.issubdtype(idx.dtype, np.integer):
            raise ValueError(f"Índices inválidos em {nome}.")
        if len(idx) != len(np.unique(idx)) or np.any(idx < 0) or np.any(idx >= n):
            raise ValueError(f"Há índices duplicados ou fora de faixa em {nome}.")
    if len(train) != meta["n_treino_populacao"] or len(test) != meta["n_teste_intocado"]:
        raise ValueError("Tamanho das partições incompatível com os metadados do 04.")
    if len(sample) != meta["n_amostra"] or len(train) + len(test) != n:
        raise ValueError("Amostra ou partição incompleta.")
    if np.intersect1d(train, test, assume_unique=True).size:
        raise ValueError("VAZAMENTO: interseção entre treino e teste.")
    if not np.isin(sample, train).all():
        raise ValueError("VAZAMENTO: a amostra de treinamento contém índices fora do treino.")

    modelos = {}
    for esp in ESPECIFICACOES:
        item = meta["selecionados_cv"][esp]
        arquivo = TREINAMENTO / f"pipeline_{esp}_cv.joblib"
        # Um Pipeline persistido não é portátil entre versões do scikit-learn.
        # Falhar com mensagem clara é melhor que avaliar o teste com transformação diferente.
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            try:
                pipeline = load(arquivo)  # apenas artefatos locais do próprio projeto
            except InconsistentVersionWarning as erro:
                raise RuntimeError(
                    f"{arquivo.name} foi treinado com scikit-learn {erro.original_sklearn_version}, "
                    "mas o ambiente atual usa outra versão. Execute o 05 no MESMO ambiente "
                    "do 04 (ou instale a mesma versão) antes de abrir o teste."
                ) from erro
        if not hasattr(pipeline, "named_steps") or not {"preparar", "modelo"} <= set(pipeline.named_steps):
            raise ValueError(f"Arquivo {arquivo.name} não contém o Pipeline esperado.")
        check_is_fitted(pipeline)
        reg = pipeline.named_steps["modelo"]
        algoritmo = item["algoritmo"]
        esperado = {"baseline": "DummyRegressor", "mqo": "LinearRegression", "ridge": "Ridge", "lasso": "Lasso"}[algoritmo]
        if type(reg).__name__ != esperado:
            raise ValueError(f"{esp}: algoritmo salvo difere da seleção CV ({esperado}).")
        if algoritmo in {"ridge", "lasso"} and not math.isclose(float(reg.alpha), float(item["alpha"])):
            raise ValueError(f"{esp}: alpha do arquivo não bate com os metadados de validação.")
        modelos[esp] = pipeline

    # A comparação CV é uma checagem INDEPENDENTE do JSON, não uma nova seleção.
    cv = pd.read_csv(TREINAMENTO / "comparacao_validacao_cruzada.csv", sep=";", decimal=",")
    for esp, item in meta["selecionados_cv"].items():
        linha = cv[(cv["especificacao"] == esp) & (cv["algoritmo"] == item["algoritmo"])]
        if len(linha) != 1:
            raise ValueError(f"Não foi possível confirmar {esp} na tabela de validação cruzada.")
        if not np.isclose(float(linha.iloc[0]["mae_cv_media"]), float(item["mae_cv"]), rtol=1e-8):
            raise ValueError(f"MAE de CV incompatível para {esp}.")
    return meta, particao, modelos


def preparar_como_no_04(df: pd.DataFrame) -> pd.DataFrame:
    """Replica EXATAMENTE a limpeza dos preditores utilizada no 04."""
    df = df.copy()
    for col in ["cbo", "grupo_ocupacional"] + CATEGORICAS_COMUNS:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA).fillna("Ausente").astype(object)
    for col in NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    df.loc[~df["idade"].between(14, 100), "idade"] = np.nan
    df.loc[~df["horas"].between(1, 80), "horas"] = np.nan
    df["ln_rem_dez"] = pd.to_numeric(df["ln_rem_dez"], errors="coerce")
    if df["ln_rem_dez"].isna().any() or not np.isfinite(df["ln_rem_dez"].to_numpy(dtype=float)).all():
        raise ValueError("Há logaritmos de remuneração ausentes ou não finitos na base.")
    return df


def ler_teste(particao: dict, meta: dict) -> pd.DataFrame:
    colunas = list(dict.fromkeys(
        ["cbo", "grupo_ocupacional", "ln_rem_dez", "rem_dez_nom", "sexo", "grande_regiao"]
        + CATEGORICAS_COMUNS + NUMERICAS
    ))
    # Mesma ordem física da base lida no 04 (pandas read_parquet não ordena).
    df = pd.read_parquet(BASE, columns=colunas)
    if len(df) != int(meta["n_populacao"]):
        raise ValueError("A base mudou de tamanho após o 04: NÃO utilize os índices antigos.")
    # Garantia de compatibilidade numérica entre alvo log e remuneração declarada.
    y = pd.to_numeric(df["ln_rem_dez"], errors="coerce").to_numpy(dtype=float)
    sal = pd.to_numeric(df["rem_dez_nom"], errors="coerce").to_numpy(dtype=float)
    idx = particao["teste"]
    if not np.isfinite(sal[idx]).all() or np.any(sal[idx] <= 0):
        raise ValueError("O conjunto de teste contém remuneração nominal não positiva/não finita.")
    if not np.allclose(y[idx], np.log(sal[idx]), rtol=0, atol=1e-8):
        raise ValueError("O log do alvo diverge da remuneração original; verifique a preparação do 03.")
    # Evita carregar índices de treino nos resultados ou exportar linhas individuais.
    retorno = df.iloc[idx].reset_index(drop=True)
    del df
    return preparar_como_no_04(retorno)


def avaliar(esp: str, pipeline, df_teste: pd.DataFrame, meta: dict):
    ocup = ESPECIFICACOES[esp]
    features = [ocup] + CATEGORICAS_COMUNS + NUMERICAS
    if hasattr(pipeline, "feature_names_in_"):
        gravadas = list(pipeline.feature_names_in_)
        if gravadas != features:
            raise ValueError(f"Features de {esp} não correspondem às usadas no 04: {gravadas}")
    x = df_teste[features]
    verdadeiro_log = df_teste["ln_rem_dez"].to_numpy(dtype=np.float64)
    verdadeiro_reais = df_teste["rem_dez_nom"].to_numpy(dtype=np.float64)
    previsto_log = np.asarray(pipeline.predict(x), dtype=float)
    if len(previsto_log) != len(verdadeiro_log) or not np.isfinite(previsto_log).all():
        raise ValueError(f"{esp}: previsões ausentes, não finitas ou em tamanho errado.")
    # Conversão EXATAMENTE como no scorer da etapa 04, para comparabilidade.
    previsto_reais = np.exp(np.clip(previsto_log, -20, 20))
    mae = mean_absolute_error(verdadeiro_reais, previsto_reais)
    rmse_log = float(np.sqrt(mean_squared_error(verdadeiro_log, previsto_log)))
    erro = previsto_reais - verdadeiro_reais  # sinal positivo = superestimação
    linha = {
        "especificacao": esp,
        "algoritmo_congelado_cv": meta["selecionados_cv"][esp]["algoritmo"],
        "alpha_congelado_cv": meta["selecionados_cv"][esp]["alpha"],
        "n_teste": len(df_teste),
        "mae_cv_2mil_reais": meta["selecionados_cv"][esp]["mae_cv"],
        "mae_teste_reais": mae,
        "rmse_teste_log": rmse_log,
        "mediana_erro_absoluto_reais": median_absolute_error(verdadeiro_reais, previsto_reais),
        "vies_medio_reais_previsto_menos_observado": float(erro.mean()),
        "vies_mediano_reais_previsto_menos_observado": float(np.median(erro)),
        "salario_medio_observado_reais": float(verdadeiro_reais.mean()),
        "salario_mediano_observado_reais": float(np.median(verdadeiro_reais)),
        "salario_medio_previsto_reais": float(previsto_reais.mean()),
        "salario_mediano_previsto_reais": float(np.median(previsto_reais)),
        "p_sobre_n_amostra": meta["selecionados_cv"][esp]["p_sobre_n"],
    }
    return linha, previsto_reais, previsto_log


def segmentar(df_teste: pd.DataFrame, previsto_reais: np.ndarray, previsto_log: np.ndarray, esp: str):
    bruto = df_teste["rem_dez_nom"].to_numpy(dtype=float)
    ylog = df_teste["ln_rem_dez"].to_numpy(dtype=float)
    absoluto = np.abs(previsto_reais - bruto)
    residuo_log_2 = (previsto_log - ylog) ** 2
    resultados = []
    for coluna in ATRIBUTOS_AUDITORIA:
        grupos = df_teste[coluna].astype("string").fillna("Ausente").str.strip().replace("", "Ausente")
        # Agrupamento vetorizado; nomes de categorias sempre preservados como strings.
        aux = pd.DataFrame({"categoria": grupos.astype(str), "abs": absoluto,
                            "sq_log": residuo_log_2, "soma_real": bruto, "soma_pred": previsto_reais})
        tab = aux.groupby("categoria", dropna=False, sort=False).agg(
            n=("abs", "size"), mae_reais=("abs", "mean"),
            mse_log=("sq_log", "mean"), salario_medio=("soma_real", "mean"),
            previsao_media=("soma_pred", "mean")
        )
        for cat, r in tab.iterrows():
            n = int(r["n"])
            resultados.append({
                "especificacao": esp, "variavel": coluna, "categoria": str(cat), "n": n,
                "n_minimo_30": bool(n >= MINIMO_GRUPO),
                "mae_teste_reais": float(r["mae_reais"]),
                "rmse_teste_log": float(np.sqrt(r["mse_log"])),
                "remuneracao_media_real": float(r["salario_medio"]),
                "previsao_media_reais": float(r["previsao_media"]),
            })
    return resultados


def salvar_csv(df: pd.DataFrame, caminho: Path):
    df.to_csv(caminho, sep=";", index=False, decimal=",", encoding="utf-8-sig")


def criar_figuras(resultados: pd.DataFrame, segmentos: pd.DataFrame, pasta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pasta.mkdir(parents=True, exist_ok=True)
    # Gráfico 1: duas especificações, validação vs. teste, mesma unidade.
    labels = ["Famílias", "35 CBOs"]
    r = resultados.set_index("especificacao").loc[["familias", "cbos"]]
    x = np.arange(2)
    largura = 0.35
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(x - largura / 2, r["mae_cv_2mil_reais"], largura, label="Validação 5-fold (amostra)")
    ax.bar(x + largura / 2, r["mae_teste_reais"], largura, label="Teste intocado")
    ax.set_xticks(x, labels)
    ax.set_ylabel("MAE (R$)")
    ax.set_title("Remunerômetro — MAE por especificação")
    ax.legend()
    fig.tight_layout()
    fig.savefig(pasta / "01_mae_cv_versus_teste.png", dpi=180)
    plt.close(fig)

    # Gráfico 2: auditoria de erros por escolaridade (apenas categorias com n>=30).
    sub = segmentos[(segmentos["variavel"] == "escolaridade") & segmentos["n_minimo_30"]]
    if not sub.empty:
        pivot = sub.pivot(index="categoria", columns="especificacao", values="mae_teste_reais")
        pivot = pivot.reindex(columns=["familias", "cbos"])
        fig, ax = plt.subplots(figsize=(11, 6))
        pivot.plot(kind="bar", ax=ax)
        ax.set_title("MAE de teste por escolaridade (grupos com n ≥ 30)")
        ax.set_xlabel("Código de escolaridade da RAIS")
        ax.set_ylabel("MAE (R$)")
        ax.legend(["Famílias", "CBOs"])
        fig.tight_layout()
        fig.savefig(pasta / "02_mae_por_escolaridade.png", dpi=180)
        plt.close(fig)


def registrar_relatorio(resultados: pd.DataFrame, segmentos: pd.DataFrame, meta: dict, hashes: dict, pasta: Path):
    a = resultados.set_index("especificacao")
    f = a.loc["familias"]
    c = a.loc["cbos"]
    lin = [
        "# Remunerômetro 2025 — Avaliação final (etapa 05)",
        "",
        "Os modelos foram SELECIONADOS EXCLUSIVAMENTE pela validação cruzada do 04.",
        "Não houve novo treinamento, seleção de hiperparâmetros ou particionamento no 05.",
        "",
        f"- Semente configurada no 04: {meta['semente']}",
        f"- Partição do 04: {meta['frac_teste']:.0%} da população elegível para teste.",
        f"- Amostra para modelagem: {meta['n_amostra']:,} vínculos do treino; {meta['dobras']} dobras.",
        f"- Observações de teste: {meta['n_teste_intocado']:,} vínculos.",
        "",
        "## Modelos congelados e resultados",
        "",
        "| Especificação | Algoritmo | Alpha | MAE CV (R$) | MAE teste (R$) | RMSE teste (log) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for nome, label in [("familias", "Famílias"), ("cbos", "35 CBOs")]:
        r = a.loc[nome]
        lin.append(f"| {label} | {r['algoritmo_congelado_cv']} | {r['alpha_congelado_cv']} | "
                   f"{r['mae_cv_2mil_reais']:,.2f} | {r['mae_teste_reais']:,.2f} | {r['rmse_teste_log']:.4f} |")
    dif = float(f["mae_teste_reais"] - c["mae_teste_reais"])
    lin.extend([
        "", "## Comparação entre as especificações", "",
        f"Diferença MAE (Famílias - CBOs): R$ {dif:,.2f}. "
        "Valor positivo significa menor MAE do modelo por CBOs no teste.",
        "Essa diferença é DESCRITIVA; não deve orientar novas tentativas com o teste.",
        "", "## Diagnósticos por grupo", "",
        "Os arquivos CSV apresentam MAE e RMSE (log) por sexo, escolaridade, "
        "grande região, tipologia, grupo ocupacional e CBO.",
        "Categorias com menos de 30 registros são sinalizadas, não eliminadas nem ocultadas.",
        "As desigualdades de erro entre grupos NÃO demonstram discriminação causal.",
        "", "## Interpretação do alvo", "",
        "Alvo: log da remuneração nominal de dezembro de vínculos formais ativos em 31/12/2025.",
        "As previsões são exp(predição do log), na mesma escala usada para MAE da CV; "
        "isso NÃO é automaticamente a esperança condicional do salário em reais.",
        "", "## Rastreabilidade", "",
    ])
    for nome, hash_ in sorted(hashes.items()):
        lin.append(f"- SHA-256 `{nome}`: `{hash_}`")
    lin.extend(["", "## Regra pós-teste", "", "Não ajustar os modelos após ver estas métricas. "
                "Quaisquer mudanças posteriores requerem outra avaliação, com amostra de teste nova e independente."])
    (pasta / "RELATORIO_AVALIACAO_FINAL.md").write_text("\n".join(lin) + "\n", encoding="utf-8")


def executar():
    # Confere ANTES de abrir o teste se já houve avaliação desta partição.
    marco = SAIDA / "AVALIACAO_FINAL_CONCLUIDA.json"
    if marco.exists():
        raise FileExistsError(f"O teste já foi avaliado. Leia os resultados existentes: {marco}")
    meta, particao, modelos = carregar_e_conferir_artefatos()
    if SAIDA.exists() and any(SAIDA.iterdir()):
        raise FileExistsError(f"A pasta {SAIDA} já contém arquivos. Não sobrescrevemos a avaliação final.")
    SAIDA.mkdir(parents=True, exist_ok=True)
    lock = SAIDA / ".avaliacao_em_execucao.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as arq:
            arq.write(f"processo={os.getpid()}\n")
        print("[05] Lendo a mesma base utilizada no 04...", flush=True)
        df = ler_teste(particao, meta)
        print(f"[05] TESTE FINAL: {len(df):,} vínculos. Sem reajustar modelos.", flush=True)
        metricas = []
        grupos = []
        for esp, pipe in modelos.items():
            print(f"[05] Avaliando especificação {esp}...", flush=True)
            linha, pred_reais, pred_log = avaliar(esp, pipe, df, meta)
            metricas.append(linha)
            grupos.extend(segmentar(df, pred_reais, pred_log, esp))
            print(f"     MAE: R$ {linha['mae_teste_reais']:,.2f} | RMSE log: {linha['rmse_teste_log']:.4f}", flush=True)
        res = pd.DataFrame(metricas)
        seg = pd.DataFrame(grupos)
        salvar_csv(res, SAIDA / "01_metricas_finais.csv")
        salvar_csv(seg, SAIDA / "02_erros_por_grupo.csv")
        for col, titulo in [("sexo", "sexo"), ("escolaridade", "escolaridade"),
                            ("grande_regiao", "grande_regiao"), ("tipologia_ibge", "tipologia"),
                            ("grupo_ocupacional", "grupo_ocupacional"), ("cbo", "cbo")]:
            salvar_csv(seg.loc[seg["variavel"] == col].copy(), SAIDA / f"03_erros_por_{titulo}.csv")
        criar_figuras(res, seg, SAIDA / "figuras")
        arquivos_hash = [BASE, TREINAMENTO / "indices_particao.npz",
                         TREINAMENTO / "metadados_treino.json",
                         TREINAMENTO / "pipeline_familias_cv.joblib",
                         TREINAMENTO / "pipeline_cbos_cv.joblib"]
        hashes = {p.name: sha256_arquivo(p) for p in arquivos_hash}
        registrar_relatorio(res, seg, meta, hashes, SAIDA)
        marcador = {
            "status": "concluida_sem_retuning", "avaliacao_utc": datetime.now(timezone.utc).isoformat(),
            "n_teste": len(df), "modelos": list(modelos), "origem_particao": "04_treinar_modelos.py",
            "hashes_artefatos": hashes, "nota": "Teste utilizado uma única vez para avaliação final."
        }
        # Escreve o marcador POR ÚLTIMO, após os demais relatórios e gráficos.
        marco.write_text(json.dumps(marcador, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[CONCLUÍDO] Relatórios em {SAIDA}", flush=True)
        print("[ATENÇÃO] Não use o teste para novas escolhas de modelo/alpha.", flush=True)
    finally:
        if lock.exists():
            lock.unlink()


if __name__ == "__main__":
    executar()
