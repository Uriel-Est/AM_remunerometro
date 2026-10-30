"""REMUNERÔMETRO — preparação exploratória RAIS Bronze 2025 (versão 3 + correção de escala).

- Lê os sete arquivos regionais da RAIS 2025 em lotes; não lê os estabelecimentos,
  o backup .corrompido.bak ou dados de anos anteriores.
- Município principal = município do ESTABELECIMENTO; UF e tipologia IBGE no
  arquivo analítico principal. Município de trabalho apenas como diagnóstico.
- Inclui famílias previamente analisadas + CBOs candidatos de dados, BI e UX.
- CBO não é título de vaga. Os rótulos analíticos são HIPÓTESES de correspondência.
- NÃO define a amostra de 2.000, partição de teste ou modelo: isso será feito
  depois da escolha final do universo ocupacional, seguindo o laboratório.

CORREÇÃO v3 (integrada): as colunas Vl Rem Média Nom e Vl Rem Dezembro Nom são
divididas por 100 logo após a leitura, porque a rotina anterior removia o ponto
decimal e inflava os valores em 100x. A auditoria da correção é gravada em
auditoria_correcao_remuneracao.csv. A correção pressupõe que AMBAS as colunas
foram multiplicadas por 100 na versão 3; refazer a auditoria salarial usando o
parquet de saída, não os arquivos Bronze.

Nunca execute duas cópias desta rotina simultaneamente.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

# ===================== CONFIGURAÇÕES =====================
RAIZ = Path.cwd()
BRONZE = RAIZ / "data" / "bronze" / "rais_publica" / "2025"
ARQUIVO_IBGE = RAIZ / "data" / "Tipologia_municipal_rural_urbano.xlsx"
SAIDA = RAIZ / "data" / "analysis" / "remunerometro" / "v3"
LOTE = 50_000

# Universo exploratório AMPLIADO (não é seleção definitiva para o treino).
# Famílias anteriores, mantidas para comparação com o primeiro diagnóstico:
FAMILIAS_EXPLORATORIAS = {"2111", "2112", "2123", "2124", "2522", "2525"}
# Adições explícitas. Alguns códigos são APROXIMAÇÕES de títulos de mercado.
CBOS_ADICIONAIS = {
    "212205": ("Engenharia de dados (aproximação: engenheiro de aplicativos)", "aproximado"),
    "142330": ("Analista de negócios; BI é apenas correspondência possível", "aproximado"),
    "142335": ("Analista de pesquisa de mercado; pesquisa quantitativa possível", "aproximado"),
    "262410": ("UX/UI (aproximação: designer gráfico)", "aproximado"),
    "262420": ("Design de produto (aproximação)", "aproximado"),
}

# CORREÇÃO v3: escala das remunerações. A rotina antiga removia o ponto decimal
# de Vl Rem Média Nom e Vl Rem Dezembro Nom; a correção é dividir por 100.
COLUNAS_REMUNERACAO = ("rem_media_nom", "rem_dez_nom")
ESCALA_CORRECAO = 100.0

COLUNAS = {
    "CBO 2002 Ocupação - Código": "cbo",
    "CNAE 2.0 Subclasse - Codigo": "cnae",
    "Ind Vínculo Ativo 31/12 - Código": "ativo_3112",
    "Escolaridade Após 2005 - Código": "escolaridade",
    "Qtd Hora Contr": "horas",
    "Idade": "idade",
    "Município Trab - Código": "municipio_trabalho",
    "Município - Código": "municipio_estab",
    "Vl Rem Média Nom": "rem_media_nom",
    "Vl Rem Dezembro Nom": "rem_dez_nom",
    "Sexo - Código": "sexo",
    "Raça Cor - Código": "raca_cor",
    "Tipo Vínculo - Código": "tipo_vinculo",
    "Tamanho Estabelecimento - Código": "tamanho_estabelecimento",
    "Tempo Emprego": "tempo_emprego",
    "Natureza Jurídica - Código": "natureza_juridica",
}

TIPOS = {
    "urbano": "Urbano",
    "intermediarioadjacente": "Intermediário adjacente",
    "intermediarioremoto": "Intermediário remoto",
    "ruraladjacente": "Rural adjacente",
    "ruralremoto": "Rural remoto",
}
UF = {
    "11":"RO", "12":"AC", "13":"AM", "14":"RR", "15":"PA", "16":"AP", "17":"TO",
    "21":"MA", "22":"PI", "23":"CE", "24":"RN", "25":"PB", "26":"PE", "27":"AL", "28":"SE", "29":"BA",
    "31":"MG", "32":"ES", "33":"RJ", "35":"SP", "41":"PR", "42":"SC", "43":"RS",
    "50":"MS", "51":"MT", "52":"GO", "53":"DF",
}
REGIOES = {
    "rais_vinc_pub_centro_oeste_2025.parquet", "rais_vinc_pub_mg_es_rj_2025.parquet",
    "rais_vinc_pub_ni_2025.parquet", "rais_vinc_pub_nordeste_2025.parquet",
    "rais_vinc_pub_norte_2025.parquet", "rais_vinc_pub_sp_2025.parquet",
    "rais_vinc_pub_sul_2025.parquet",
}


def chave_texto(valor):
    if pd.isna(valor):
        return None
    x = unicodedata.normalize("NFKD", str(valor).strip().lower())
    return re.sub("[^a-z]", "", "".join(c for c in x if not unicodedata.combining(c)))


def codigo(serie, comprimento=None):
    x = serie.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    x = x.where(x.str.fullmatch(r"\d+"))
    if comprimento:
        x = x.where(x.str.len().eq(comprimento))
    return x


def numero_ptbr(serie):
    x = serie.astype("string").str.strip()
    # RAIS usa vírgula decimal e, quando há separador de milhar, ponto.
    x = x.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(x, errors="coerce").astype("float64")


def mapa_ibge():
    if not ARQUIVO_IBGE.exists():
        raise FileNotFoundError(f"Planilha do IBGE não encontrada: {ARQUIVO_IBGE}")
    livro = pd.ExcelFile(ARQUIVO_IBGE)
    for aba in livro.sheet_names:
        topo = pd.read_excel(livro, sheet_name=aba, header=None, nrows=40, dtype="string")
        for i in range(len(topo)):
            nomes = [str(x).strip().upper() for x in topo.iloc[i]]
            if "CD_GCMUN" not in nomes or "TIPO" not in nomes:
                continue
            df = pd.read_excel(livro, sheet_name=aba, header=i, dtype="string")
            df.columns = [str(c).strip().upper() for c in df.columns]
            k = codigo(df["CD_GCMUN"], 7).str[:6]
            t = df["TIPO"].map(lambda v: TIPOS.get(chave_texto(v)))
            ignorados = df.loc[df["TIPO"].notna() & t.isna(), "TIPO"]
            if not ignorados.empty:
                raise ValueError(f"Categorias IBGE não reconhecidas: {ignorados.value_counts().head().to_dict()}")
            m = pd.DataFrame({"code_muni": k, "tipologia_ibge": t}).dropna()
            conflito = m.groupby("code_muni")["tipologia_ibge"].nunique()
            if (conflito > 1).any():
                raise ValueError("A tabela IBGE possui códigos municipais com tipologias conflitantes")
            m = m.drop_duplicates("code_muni")
            print(f"[IBGE] {len(m):,} códigos municipais, aba {aba}", flush=True)
            return dict(zip(m.code_muni, m.tipologia_ibge))
    raise ValueError("Não foram encontradas colunas CD_GCMUN e TIPO na planilha do IBGE")


def gravar_csv(nome, linhas, colunas):
    pd.DataFrame(linhas, columns=colunas).to_csv(SAIDA / nome, sep=";", index=False, encoding="utf-8-sig")


def acumular_stats_remuneracao(df, stats):
    """Registra estatísticas das remunerações ANTES da divisão corretiva.

    Replica exatamente o que a rotina de fix calculava sobre o Parquet
    'original' inflado, para que auditoria_correcao_remuneracao.csv
    continue comparável com a versão anterior da correção.
    """
    for campo in COLUNAS_REMUNERACAO:
        serie = df[campo]
        r = stats[campo]
        r["nulos"] += int(serie.isna().sum())
        validos = serie.dropna()
        if len(validos):
            v = validos.to_numpy(dtype=np.float64)
            if not np.all(np.isfinite(v)):
                raise ValueError(f"{campo}: valores não finitos detectados; interrompendo.")
            r["zeros"] += int((v == 0).sum())
            r["positivos"] += int((v > 0).sum())
            if np.any(v > 0):
                r["min_positivo_original"] = min(
                    r["min_positivo_original"], float(v[v > 0].min())
                )
            r["max_original"] = max(r["max_original"], float(v.max()))
            r["soma_original"] += float(v.sum())


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    presentes = {p.name for p in BRONZE.glob("*.parquet")}
    ausentes = sorted(REGIOES - presentes)
    if ausentes:
        raise FileNotFoundError(f"Faltam arquivos regionais: {ausentes}")
    arquivos = [BRONZE / nome for nome in sorted(REGIOES)]
    tipos = mapa_ibge()
    total_lido = 0
    total_selecionado = 0
    cont = Counter()
    por_cbo = Counter()
    por_cbo_uf = Counter()
    por_uf_tipo = Counter()
    sem_tipo = Counter()
    por_arquivo = []
    stats_rem = {
        c: {"nulos": 0, "zeros": 0, "positivos": 0,
            "min_positivo_original": float("inf"),
            "max_original": float("-inf"), "soma_original": 0.0}
        for c in COLUNAS_REMUNERACAO
    }

    destino = SAIDA / "rais_2025_candidatos_ampliados.parquet"
    temporario = SAIDA / "rais_2025_candidatos_ampliados.tmp.parquet"
    escritor = None
    nomes_saida = ["cbo", "familia_cbo", "grupo_selecao", "rotulo_mercado_aproximado",
                   "cnae", "cnae_divisao", "ativo_3112", "escolaridade", "horas",
                   "idade", "municipio_trabalho", "municipio_estab", "code_muni",
                   "uf_codigo", "uf_sigla", "tipologia_ibge", "municipio_trabalho_valido",
                   "municipio_trabalho_difere_estab", "rem_media_nom", "rem_dez_nom",
                   "sexo", "raca_cor", "tipo_vinculo", "tamanho_estabelecimento",
                   "tempo_emprego", "natureza_juridica", "arquivo_origem"]
    campos_numericos = {"horas", "idade", "rem_media_nom", "rem_dez_nom", "tempo_emprego"}
    campos_booleanos = {"municipio_trabalho_valido", "municipio_trabalho_difere_estab"}
    esquema = pa.schema([pa.field(n, pa.float64() if n in campos_numericos else
                                pa.bool_() if n in campos_booleanos else pa.string())
                        for n in nomes_saida])
    print(f"[CORREÇÃO v3] {list(COLUNAS_REMUNERACAO)} serão divididas por {ESCALA_CORRECAO:g}.",
          flush=True)
    try:
        escritor = pq.ParquetWriter(temporario, esquema, compression="zstd")
        for arquivo in arquivos:
            pf = pq.ParquetFile(arquivo)
            faltam = sorted(set(COLUNAS) - set(pf.schema_arrow.names))
            if faltam:
                raise ValueError(f"{arquivo.name}: colunas não encontradas: {faltam}")
            n_arq = 0
            n_sel_arq = 0
            print(f"[LENDO] {arquivo.name} | {pf.metadata.num_rows:,} linhas", flush=True)
            for lote in pf.iter_batches(batch_size=LOTE, columns=list(COLUNAS)):
                n = lote.num_rows
                total_lido += n
                n_arq += n
                c = pc.utf8_trim_whitespace(lote.column(0))  # CBO é a primeira coluna solicitada
                # Seleção vetorizada Arrow, antes de converter o lote para pandas.
                cbos = pc.utf8_slice_codeunits(c, 0, 4)
                selecionar = pc.or_(pc.is_in(cbos, value_set=pa.array(sorted(FAMILIAS_EXPLORATORIAS))),
                                   pc.is_in(c, value_set=pa.array(sorted(CBOS_ADICIONAIS))))
                selecionar = pc.fill_null(selecionar, False)
                filtrado = lote.filter(selecionar)
                if filtrado.num_rows == 0:
                    continue
                df = filtrado.to_pandas().rename(columns=COLUNAS)
                df["cbo"] = codigo(df["cbo"], 6)
                df = df.loc[df["cbo"].notna()].copy()
                if df.empty:
                    continue
                df["familia_cbo"] = df["cbo"].str[:4]
                df["grupo_selecao"] = df["cbo"].map(
                    lambda x: "familia_exploratoria" if x[:4] in FAMILIAS_EXPLORATORIAS else "adicao_especifica"
                )
                df["rotulo_mercado_aproximado"] = df["cbo"].map(
                    lambda x: CBOS_ADICIONAIS.get(x, ("", ""))[0] if x in CBOS_ADICIONAIS else ""
                )
                df["municipio_estab"] = codigo(df["municipio_estab"], 6)
                df["municipio_trabalho"] = codigo(df["municipio_trabalho"], 6)
                df["code_muni"] = df["municipio_estab"].where(
                    df["municipio_estab"].ne("999999").fillna(False)
                )
                df["uf_codigo"] = df["code_muni"].str[:2]
                df["uf_sigla"] = df["uf_codigo"].map(UF)
                df["tipologia_ibge"] = df["code_muni"].map(tipos)
                df["municipio_trabalho_valido"] = (
                    df["municipio_trabalho"].ne("999999").fillna(False)
                    & df["municipio_trabalho"].str[:2].isin(UF)
                ).astype(bool)
                df["municipio_trabalho_difere_estab"] = (
                    df["municipio_trabalho_valido"]
                    & df["code_muni"].notna()
                    & df["municipio_trabalho"].ne(df["code_muni"])
                ).fillna(False).astype(bool)
                df["cnae"] = codigo(df["cnae"])
                df["cnae_divisao"] = df["cnae"].str[:2]
                for campo in campos_numericos:
                    df[campo] = numero_ptbr(df[campo])

                # ---- CORREÇÃO v3 -------------------------------------------------
                # 1) estatísticas ANTES da divisão (compatíveis com o fix original);
                # 2) divisão de Vl Rem Média Nom / Vl Rem Dezembro Nom por 100.
                acumular_stats_remuneracao(df, stats_rem)
                for campo in COLUNAS_REMUNERACAO:
                    df[campo] = df[campo] / ESCALA_CORRECAO
                # ------------------------------------------------------------------

                for campo in ["escolaridade", "ativo_3112", "sexo", "raca_cor", "tipo_vinculo",
                              "tamanho_estabelecimento", "natureza_juridica"]:
                    df[campo] = codigo(df[campo])
                df["arquivo_origem"] = arquivo.name
                validos = df["rem_media_nom"].notna() & df["rem_media_nom"].gt(0)
                cont["remuneracao_media_nao_positiva_ou_nula"] += int((~validos).sum())
                cont["tipologia_ausente"] += int(df["tipologia_ibge"].isna().sum())
                cont["uf_ausente"] += int(df["uf_sigla"].isna().sum())
                cont["municipio_trabalho_indisponivel"] += int((~df["municipio_trabalho_valido"]).sum())
                cont["municipio_trabalho_difere_estab"] += int(df["municipio_trabalho_difere_estab"].sum())
                for k, v in df["cbo"].value_counts().items():
                    por_cbo[str(k)] += int(v)
                for (cbo, uf), qtd in df[["cbo", "uf_sigla"]].value_counts().items():
                    por_cbo_uf[(str(cbo), str(uf))] += int(qtd)
                for (uf, tipo), qtd in df[["uf_sigla", "tipologia_ibge"]].value_counts().items():
                    por_uf_tipo[(str(uf), str(tipo))] += int(qtd)
                for k, v in df.loc[df["tipologia_ibge"].isna(), "code_muni"].dropna().value_counts().items():
                    sem_tipo[str(k)] += int(v)
                for nm in nomes_saida:
                    if nm not in campos_numericos and nm not in campos_booleanos:
                        df[nm] = df[nm].astype("object").where(df[nm].notna(), None)
                tabela = pa.Table.from_pandas(df[nomes_saida], schema=esquema, preserve_index=False)
                escritor.write_table(tabela)
                total_selecionado += len(df)
                n_sel_arq += len(df)
            por_arquivo.append({"arquivo": arquivo.name, "linhas": n_arq, "candidatos": n_sel_arq})
            print(f"  candidatos: {n_sel_arq:,}", flush=True)
        escritor.close()
        escritor = None
        temporario.replace(destino)
    finally:
        if escritor is not None:
            escritor.close()
        if temporario.exists():
            temporario.unlink()

    gravar_csv("frequencia_cbo_2025.csv", [
        {"cbo": k, "vinculos": v,
         "origem": "familia_exploratoria" if k[:4] in FAMILIAS_EXPLORATORIAS else "adicao_especifica",
         "rotulo_aproximado": CBOS_ADICIONAIS.get(k, ("", ""))[0]}
        for k, v in por_cbo.most_common()],
        ["cbo", "vinculos", "origem", "rotulo_aproximado"])
    gravar_csv("frequencia_cbo_uf_2025.csv", [
        {"cbo": cbo, "uf_sigla": uf, "vinculos": v} for (cbo, uf), v in por_cbo_uf.most_common()],
        ["cbo", "uf_sigla", "vinculos"])
    gravar_csv("frequencia_uf_tipologia_2025.csv", [
        {"uf_sigla": uf, "tipologia_ibge": tip, "vinculos": v} for (uf, tip), v in por_uf_tipo.most_common()],
        ["uf_sigla", "tipologia_ibge", "vinculos"])
    gravar_csv("municipios_sem_tipologia_2025.csv", [
        {"code_muni": k, "vinculos": v} for k, v in sem_tipo.most_common()], ["code_muni", "vinculos"])
    gravar_csv("auditoria_2025.csv", [
        {"indicador": "vinculos_lidos", "quantidade": total_lido, "percentual_sobre_candidatos": None},
        {"indicador": "candidatos_ampliados", "quantidade": total_selecionado, "percentual_sobre_candidatos": 100},
        *({"indicador": k, "quantidade": v, "percentual_sobre_candidatos": round(100 * v / total_selecionado, 5)}
          for k, v in sorted(cont.items()))],
        ["indicador", "quantidade", "percentual_sobre_candidatos"])
    gravar_csv("arquivos_processados.csv", por_arquivo, ["arquivo", "linhas", "candidatos"])
    gravar_csv("catalogo_cbos_adicionados.csv", [
        {"cbo": k, "rotulo_de_mercado": r, "correspondencia": grau,
         "nota": "Não identifica título real de vaga individualmente"}
        for k, (r, grau) in sorted(CBOS_ADICIONAIS.items())],
        ["cbo", "rotulo_de_mercado", "correspondencia", "nota"])

    # ---- Auditoria da correção de escala (mesmo esquema da rotina de fix) ----
    linhas_correcao = []
    for col in COLUNAS_REMUNERACAO:
        r = stats_rem[col]
        validos = total_selecionado - r["nulos"]
        mini = r["min_positivo_original"] if math.isfinite(r["min_positivo_original"]) else None
        maxi = r["max_original"] if math.isfinite(r["max_original"]) else None
        linhas_correcao.append({
            "coluna": col, "linhas": total_selecionado, "nulos": r["nulos"],
            "zeros": r["zeros"], "positivos": r["positivos"],
            "media_original": r["soma_original"] / validos if validos else None,
            "media_corrigida": r["soma_original"] / validos / ESCALA_CORRECAO if validos else None,
            "min_positivo_original": mini,
            "min_positivo_corrigido": mini / ESCALA_CORRECAO if mini is not None else None,
            "max_original": maxi,
            "max_corrigido": maxi / ESCALA_CORRECAO if maxi is not None else None,
        })
    gravar_csv(
        "auditoria_correcao_remuneracao.csv",
        linhas_correcao,
        ["coluna", "linhas", "nulos", "zeros", "positivos", "media_original", "media_corrigida",
         "min_positivo_original", "min_positivo_corrigido", "max_original", "max_corrigido"],
    )

    print("\n[CONCLUÍDO]", flush=True)
    print(f"Vínculos lidos: {total_lido:,} | candidatos: {total_selecionado:,}")
    print(f"Parquet: {destino}")
    print("Remunerações corrigidas (/100); auditoria em auditoria_correcao_remuneracao.csv.")
    print("ATENÇÃO: recorte exploratório amplo; NÃO é a amostra final de 2.000 vínculos.")
    print("Os CBOs aproximados devem ser revisados antes de escolher o universo do modelo.")


if __name__ == "__main__":
    main()
