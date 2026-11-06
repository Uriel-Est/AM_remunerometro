"""Remunerômetro 2025: base comum para duas especificações ocupacionais.

Execute diretamente no Positron, a partir da raiz do projeto (Path.cwd()).
Não divide treino/teste, não sorteia 2.000 vínculos e não aplica one-hot:
essas operações pertencem ao notebook e aos pipelines do scikit-learn.

Dependências: pip install pandas pyarrow numpy
"""
from __future__ import annotations

from pathlib import Path
from collections import Counter
import csv
import math
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from caminhos import PASTA_ANALISE

PASTA = PASTA_ANALISE
ENTRADA = PASTA / 'rais_2025_candidatos_ampliados.parquet'
CATALOGO = PASTA / 'frequencia_cbo_2025.csv'
SAIDA = PASTA / 'modelagem_dupla'
SAIDA.mkdir(parents=True, exist_ok=True)
PARQUET_SAIDA = SAIDA / 'rais_2025_base_modelagem_dezembro.parquet'
LOTES = 40_000
# Antes de aplicar, confira a tabela de frequências de ativo_3112 da auditoria.
CODIGO_ATIVO_3112 = '1'
# Não eliminamos registros por idade, jornada, escolaridade, UF ou tipologia nesta etapa.
# Nulos e códigos especiais serão tratados DENTRO dos pipelines, após a partição.

# Classes mutuamente exclusivas e exaustivas para os 35 CBOs selecionados.
# Famílias 2111/2112: quantitativas e estatísticas (inclui matemática/atuária).
# Famílias 2122/2123/2124: TI / engenharia / dados.
# Demais ocupações da seleção (negócios, economia, pesquisa, design): expansão.
# Ajustar apenas se houver justificativa substantiva, antes da partição de teste.
def grupo_do_cbo(cbo: str) -> str:
    if cbo.startswith(('2111', '2112')):
        return 'Estatística formal e quantitativas'
    if cbo.startswith(('2122', '2123', '2124')):
        return 'TI e dados'
    return 'Expansão profissional'

REGIAO_POR_UF = {
    **dict.fromkeys(['RO','AC','AM','RR','PA','AP','TO'], 'Norte'),
    **dict.fromkeys(['MA','PI','CE','RN','PB','PE','AL','SE','BA'], 'Nordeste'),
    **dict.fromkeys(['MG','ES','RJ','SP'], 'Sudeste'),
    **dict.fromkeys(['PR','SC','RS'], 'Sul'),
    **dict.fromkeys(['MS','MT','GO','DF'], 'Centro-Oeste'),
}


def texto(s: pd.Series) -> pd.Series:
    return s.astype('string').str.strip()


def salvar_csv(caminho: Path, linhas: list[dict], nomes: list[str]) -> None:
    with caminho.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=nomes, delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)


def carregar_cbos() -> list[str]:
    if not CATALOGO.exists():
        raise FileNotFoundError(f'Catálogo CBO da v3 não encontrado: {CATALOGO}')
    tab = pd.read_csv(CATALOGO, sep=';', dtype={'cbo': 'string'})
    if 'cbo' not in tab:
        raise ValueError(f'O catálogo não contém a coluna cbo: {CATALOGO}')
    lista = sorted({str(x).strip() for x in tab.cbo.dropna()})
    if len(lista) != 35 or any(len(x) != 6 or not x.isdigit() for x in lista):
        raise ValueError(f'Esperados exatamente 35 CBOs válidos de 6 dígitos; encontrados {len(lista)}.')
    return lista


def executar() -> None:
    if not ENTRADA.exists():
        raise FileNotFoundError(f'Parquet consolidado não encontrado: {ENTRADA}')
    cbos = carregar_cbos()
    mapa = {c: grupo_do_cbo(c) for c in cbos}
    salvar_csv(SAIDA / 'catalogo_35_cbos_3_grupos.csv',
               [{'cbo': c, 'grupo_ocupacional': mapa[c]} for c in cbos],
               ['cbo', 'grupo_ocupacional'])

    pf = pq.ParquetFile(ENTRADA)
    colunas_requeridas = [
        'cbo', 'rem_dez_nom', 'rem_media_nom', 'ativo_3112', 'idade', 'horas',
        'escolaridade', 'sexo', 'raca_cor', 'cnae', 'cnae_divisao',
        'code_muni', 'uf_sigla', 'tipologia_ibge',
    ]
    faltam = sorted(set(colunas_requeridas) - set(pf.schema_arrow.names))
    if faltam:
        raise ValueError(f'Faltam colunas no Parquet consolidado: {faltam}')

    destino_tmp = PARQUET_SAIDA.with_suffix('.tmp.parquet')
    if destino_tmp.exists():
        destino_tmp.unlink()

    vistos = Counter()
    codigos_ativo = Counter()
    por_grupo = Counter()
    por_cbo = Counter()
    por_regiao = Counter()
    writer = None
    try:
        for batch in pf.iter_batches(batch_size=LOTES, columns=colunas_requeridas):
            df = batch.to_pandas()
            vistos['total_lidos'] += len(df)
            df['cbo'] = texto(df['cbo'])
            df = df[df['cbo'].isin(cbos)].copy()
            vistos['cbos_reconhecidos'] += len(df)
            if df.empty:
                continue
            ativos = texto(df['ativo_3112'])
            for codigo, quantidade in ativos.value_counts(dropna=False).items():
                codigos_ativo[str(codigo)] += int(quantidade)
            df['rem_dez_nom'] = pd.to_numeric(df['rem_dez_nom'], errors='coerce')
            vistos['ativos_3112'] += int((ativos == CODIGO_ATIVO_3112).sum())
            vistos['rem_dez_positiva'] += int((df.rem_dez_nom > 0).sum())
            df = df.loc[(ativos == CODIGO_ATIVO_3112) & df.rem_dez_nom.gt(0)].copy()
            if df.empty:
                continue
            df['grupo_ocupacional'] = df.cbo.map(mapa)
            df['uf_sigla'] = texto(df['uf_sigla'])
            df['grande_regiao'] = df.uf_sigla.map(REGIAO_POR_UF)
            df['tipologia_ibge'] = texto(df['tipologia_ibge'])
            df['code_muni'] = texto(df['code_muni'])
            df['escolaridade'] = texto(df['escolaridade'])
            df['cnae_divisao'] = texto(df['cnae_divisao'])
            df['idade'] = pd.to_numeric(df['idade'], errors='coerce')
            df['horas'] = pd.to_numeric(df['horas'], errors='coerce')
            df['ln_rem_dez'] = df.rem_dez_nom.map(math.log)
            vistos['elegiveis_dezembro'] += len(df)
            vistos['sem_tipologia'] += int(df.tipologia_ibge.isna().sum())
            vistos['sem_uf'] += int(df.uf_sigla.isna().sum())
            vistos['sem_regiao'] += int(df.grande_regiao.isna().sum())
            vistos['sem_escolaridade'] += int(df.escolaridade.isna().sum())
            vistos['idade_fora_14_100_ou_nula'] += int((df.idade.isna() | ~df.idade.between(14, 100)).sum())
            vistos['horas_fora_1_80_ou_nula'] += int((df.horas.isna() | ~df.horas.between(1, 80)).sum())
            por_grupo.update(df.grupo_ocupacional.value_counts().to_dict())
            por_cbo.update(df.cbo.value_counts().to_dict())
            por_regiao.update(df.grande_regiao.value_counts().to_dict())
            # Tipos estáveis para Arrow, sem impor categorias antecipadamente.
            for coluna in df.select_dtypes(include=['string']).columns:
                df[coluna] = df[coluna].astype('object').where(df[coluna].notna(), None)
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(destino_tmp, table.schema, compression='zstd')
            writer.write_table(table.cast(writer.schema, safe=True))
        if writer is not None:
            writer.close()
            writer = None
            destino_tmp.replace(PARQUET_SAIDA)
        else:
            raise RuntimeError('Nenhum vínculo elegível; confira o código do indicador ativo.')
    finally:
        if writer is not None:
            writer.close()
        if destino_tmp.exists():
            destino_tmp.unlink()

    salvar_csv(SAIDA / 'auditoria_elegibilidade.csv',
               [{'indicador': k, 'quantidade': v} for k, v in vistos.items()],
               ['indicador','quantidade'])
    salvar_csv(SAIDA / 'frequencia_ativo_3112.csv',
               [{'codigo': k, 'vinculos': v} for k, v in codigos_ativo.most_common()],
               ['codigo','vinculos'])
    salvar_csv(SAIDA / 'frequencia_grupos.csv',
               [{'grupo_ocupacional': k,'vinculos': v} for k, v in por_grupo.most_common()],
               ['grupo_ocupacional','vinculos'])
    salvar_csv(SAIDA / 'frequencia_cbo_elegiveis.csv',
               [{'cbo': k, 'grupo_ocupacional': mapa[k], 'vinculos': v} for k, v in por_cbo.most_common()],
               ['cbo','grupo_ocupacional','vinculos'])
    salvar_csv(SAIDA / 'frequencia_regiao.csv',
               [{'grande_regiao': k,'vinculos': v} for k, v in por_regiao.most_common()],
               ['grande_regiao','vinculos'])
    print('\n[CONCLUIDO] Base comum para os dois modelos:', PARQUET_SAIDA)
    print('Vínculos elegíveis:', vistos['elegiveis_dezembro'])
    print('CBOs elegíveis:', len(por_cbo), 'de 35')
    print('Grupos:', dict(por_grupo))
    print('[OBS] Esta preparação não cria partições nem codifica variáveis.')
    print('[OBS] Confirme os códigos de vínculo ativo e o conceito da remuneração de dezembro.')


if __name__ == '__main__':
    executar()
