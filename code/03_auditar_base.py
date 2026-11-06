"""02 — Auditoria da base elegível do Remunerômetro RAIS 2025.

Execute no Positron a partir da raiz do projeto (Path.cwd()).
Não modifica os dados, não cria treino/teste e não faz one-hot.
Dependências: pandas, numpy, pyarrow.

Entrada: data/analysis/remunerometro/v3/modelagem_dupla/
         rais_2025_base_modelagem_dezembro.parquet
Saída:   .../modelagem_dupla/auditoria_final/*.csv e RESUMO_AUDITORIA.txt
"""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import math
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from caminhos import PASTA_MODELOS

BASE = PASTA_MODELOS
ENTRADA = BASE / 'rais_2025_base_modelagem_dezembro.parquet'
CATALOGO = BASE / 'catalogo_35_cbos_3_grupos.csv'
SAIDA = BASE / 'auditoria_final'
LOTE = 40_000
CODIGO_ATIVO = '1'
GRUPOS = {
    'Estatística formal e quantitativas',
    'TI e dados',
    'Expansão profissional',
}
REGIOES = {
    'Norte': {'RO','AC','AM','RR','PA','AP','TO'},
    'Nordeste': {'MA','PI','CE','RN','PB','PE','AL','SE','BA'},
    'Sudeste': {'MG','ES','RJ','SP'},
    'Sul': {'PR','SC','RS'},
    'Centro-Oeste': {'MS','MT','GO','DF'},
}
UF_REGIAO = {uf: regiao for regiao, ufs in REGIOES.items() for uf in ufs}
TIPOS = {'Urbano', 'Intermediário adjacente', 'Intermediário remoto',
         'Rural adjacente', 'Rural remoto'}


def salvar(nome: str, linhas: list[dict], colunas: list[str]):
    pd.DataFrame(linhas, columns=colunas).to_csv(
        SAIDA / nome, index=False, sep=';', encoding='utf-8-sig', decimal=',')


def canon(s: pd.Series) -> pd.Series:
    return s.astype('string').str.strip()


def resumo_salario(valores: np.ndarray) -> dict:
    x = valores[np.isfinite(valores) & (valores > 0)]
    if len(x) == 0:
        return dict(n=0, media=None, mediana=None, p10=None, p90=None,
                    p99=None, minimo=None, maximo=None)
    p10, mediana, p90, p99 = np.percentile(x, [10, 50, 90, 99])
    return dict(n=len(x), media=float(x.mean()), mediana=float(mediana),
                p10=float(p10), p90=float(p90), p99=float(p99),
                minimo=float(x.min()), maximo=float(x.max()))


def executar():
    if not ENTRADA.is_file():
        raise FileNotFoundError(f'Base elegível não encontrada: {ENTRADA}')
    if not CATALOGO.is_file():
        raise FileNotFoundError(f'Catálogo não encontrado: {CATALOGO}')
    SAIDA.mkdir(parents=True, exist_ok=True)
    catalogo = pd.read_csv(CATALOGO, sep=';', dtype='string', encoding='utf-8-sig')
    if not {'cbo', 'grupo_ocupacional'}.issubset(catalogo.columns):
        raise ValueError('Catálogo precisa conter cbo e grupo_ocupacional.')
    catalogo['cbo'] = canon(catalogo['cbo'])
    catalogo['grupo_ocupacional'] = canon(catalogo['grupo_ocupacional'])
    if len(catalogo) != 35 or catalogo.cbo.nunique() != 35:
        raise ValueError('Catálogo precisa ter exatamente 35 CBOs únicos.')
    if not catalogo.cbo.str.fullmatch(r'\d{6}').all():
        raise ValueError('Há CBOs inválidos no catálogo.')
    mapa = dict(zip(catalogo.cbo, catalogo.grupo_ocupacional))
    if set(mapa.values()) != GRUPOS:
        raise ValueError('Os três grupos esperados não conferem com o catálogo.')

    pf = pq.ParquetFile(ENTRADA)
    colunas = ['cbo', 'grupo_ocupacional', 'ativo_3112', 'rem_dez_nom',
               'ln_rem_dez', 'rem_media_nom', 'idade', 'horas', 'escolaridade',
               'uf_sigla', 'grande_regiao', 'tipologia_ibge', 'code_muni',
               'cnae_divisao', 'sexo']
    ausentes = sorted(set(colunas) - set(pf.schema_arrow.names))
    if ausentes:
        raise ValueError(f'Colunas faltantes no Parquet: {ausentes}')

    cont = Counter()
    cbos = Counter()
    grupos = Counter()
    regioes = Counter()
    tipologias = Counter()
    cbo_grupo = Counter()
    salarios_gerais = []
    sal_por_cbo = defaultdict(list)
    sal_por_grupo = defaultdict(list)
    sal_por_regiao = defaultdict(list)
    sal_por_tipo = defaultdict(list)

    for i, lote in enumerate(pf.iter_batches(columns=colunas, batch_size=LOTE), 1):
        df = lote.to_pandas()
        n = len(df)
        cont['total_linhas'] += n
        for col in ('cbo', 'grupo_ocupacional', 'ativo_3112', 'escolaridade',
                    'uf_sigla', 'grande_regiao', 'tipologia_ibge', 'code_muni',
                    'cnae_divisao', 'sexo'):
            df[col] = canon(df[col]).replace('', pd.NA)
        rem = pd.to_numeric(df['rem_dez_nom'], errors='coerce')
        log = pd.to_numeric(df['ln_rem_dez'], errors='coerce')
        idade = pd.to_numeric(df['idade'], errors='coerce')
        horas = pd.to_numeric(df['horas'], errors='coerce')
        media_anual = pd.to_numeric(df['rem_media_nom'], errors='coerce')
        cont['rem_dez_nula_nao_finita'] += int((~np.isfinite(rem.to_numpy(dtype=float))).sum())
        cont['rem_dez_nao_positiva'] += int((rem.le(0).fillna(False)).sum())
        cont['rem_dez_abaixo_1_real'] += int((rem.gt(0) & rem.lt(1)).sum())
        cont['rem_dez_acima_100mil'] += int(rem.gt(100_000).sum())
        cont['inativo_ou_codigo_inesperado'] += int((df.ativo_3112.ne(CODIGO_ATIVO).fillna(True)).sum())
        cont['cbo_fora_catalogo'] += int((~df.cbo.isin(mapa)).sum())
        cont['grupo_fora_catalogo'] += int((~df.grupo_ocupacional.isin(GRUPOS)).sum())
        grupo_esperado = df.cbo.map(mapa)
        cont['cbo_grupo_inconsistente'] += int((df.grupo_ocupacional.ne(grupo_esperado).fillna(True)).sum())
        cont['uf_ausente_ou_invalida'] += int((~df.uf_sigla.isin(UF_REGIAO)).sum())
        reg_esperada = df.uf_sigla.map(UF_REGIAO)
        cont['regiao_inconsistente'] += int(df.grande_regiao.ne(reg_esperada).fillna(True).sum())
        cont['tipologia_ausente_ou_invalida'] += int((~df.tipologia_ibge.isin(TIPOS)).sum())
        cont['municipio_invalido'] += int((~df.code_muni.str.fullmatch(r'\d{6}').fillna(False)).sum())
        cont['escolaridade_ausente'] += int(df.escolaridade.isna().sum())
        cont['cnae_divisao_ausente'] += int(df.cnae_divisao.isna().sum())
        cont['sexo_ausente'] += int(df.sexo.isna().sum())
        cont['idade_ausente_ou_fora_14_100'] += int((~idade.between(14, 100)).sum())
        cont['jornada_ausente_ou_fora_1_80'] += int((~horas.between(1, 80)).sum())
        cont['media_anual_ausente_ou_nao_positiva'] += int((~media_anual.gt(0)).sum())
        log_real = np.log(rem.where(rem.gt(0)))
        dif = (log - log_real).abs()
        cont['log_invalido_ou_divergente'] += int((~np.isfinite(log.to_numpy(dtype=float)) | dif.gt(1e-8).fillna(False)).sum())
        cbos.update(df.cbo.dropna().value_counts().to_dict())
        grupos.update(df.grupo_ocupacional.dropna().value_counts().to_dict())
        regioes.update(df.grande_regiao.dropna().value_counts().to_dict())
        tipologias.update(df.tipologia_ibge.dropna().value_counts().to_dict())
        cbo_grupo.update(df.groupby(['cbo','grupo_ocupacional'], dropna=False).size().to_dict())
        valid = rem.gt(0) & np.isfinite(rem.to_numpy(dtype=float))
        salarios_gerais.append(rem.loc[valid].to_numpy(dtype='float64'))
        for col, bolsa in [('cbo', sal_por_cbo), ('grupo_ocupacional', sal_por_grupo),
                           ('grande_regiao', sal_por_regiao), ('tipologia_ibge', sal_por_tipo)]:
            for chave, sub in df.loc[valid].groupby(col, dropna=False, sort=False):
                chave = str(chave) if pd.notna(chave) else '(ausente)'
                bolsa[chave].append(rem.loc[sub.index].to_numpy(dtype='float64'))
        if i % 10 == 0:
            print(f'[Auditoria] {cont["total_linhas"]:,} linhas lidas', flush=True)

    total = cont['total_linhas']
    if total == 0:
        raise RuntimeError('Parquet sem registros.')
    if len(cbos) != 35:
        cont['cbos_distintos_ausentes'] = 35-len(cbos)
    valores = np.concatenate(salarios_gerais)
    sal_geral = resumo_salario(valores)
    salvar('01_qualidade.csv', [
        dict(indicador=k, quantidade=int(v), percentual=100*v/total)
        for k, v in sorted(cont.items())], ['indicador','quantidade','percentual'])
    salvar('02_resumo_salario_dezembro.csv', [sal_geral], list(sal_geral))

    col_est = ['categoria','vinculos','esperados_2000','n','media','mediana','p10','p90','p99','minimo','maximo']
    def tabela(arquivo, contagem, sal_bolsa):
        linhas = []
        for cat, qtd in contagem.most_common():
            x = np.concatenate(sal_bolsa[str(cat)]) if str(cat) in sal_bolsa else np.array([])
            linhas.append(dict(categoria=str(cat), vinculos=qtd,
                               esperados_2000=2000*qtd/total, **resumo_salario(x)))
        salvar(arquivo, linhas, col_est)
    tabela('03_por_cbo.csv', cbos, sal_por_cbo)
    tabela('04_por_grupo.csv', grupos, sal_por_grupo)
    tabela('05_por_regiao.csv', regioes, sal_por_regiao)
    tabela('06_por_tipologia.csv', tipologias, sal_por_tipo)
    salvar('07_cruzamento_cbo_grupo.csv', [
        dict(cbo=str(c), grupo_ocupacional=str(g), vinculos=n)
        for (c,g),n in sorted(cbo_grupo.items(), key=lambda x: -x[1])],
        ['cbo','grupo_ocupacional','vinculos'])

    alertas = {k: v for k, v in cont.items() if k in {
        'inativo_ou_codigo_inesperado', 'cbo_fora_catalogo',
        'grupo_fora_catalogo', 'cbo_grupo_inconsistente',
        'rem_dez_nula_nao_finita', 'rem_dez_nao_positiva',
        'log_invalido_ou_divergente'} and v > 0}
    resumo = (
        'AUDITORIA FINAL — REMUNERÔMETRO RAIS 2025\n'
        f'Parquet: {ENTRADA}\nVínculos: {total:,}\n'
        f'CBOs presentes: {len(cbos)} / 35\n'
        f'Grupos presentes: {len(grupos)} / 3\n'
        f'Remuneração de dezembro média: R$ {sal_geral["media"]:,.2f}\n'
        f'Mediana: R$ {sal_geral["mediana"]:,.2f}\n'
        f'P99: R$ {sal_geral["p99"]:,.2f}\n'
        f'Alertas críticos: {alertas if alertas else "nenhum"}\n'
        'Notas: contagens de idade/jornada/geografia são diagnósticas, sem exclusões.\n'
        'Não contém avaliação de desempenho nem treino/teste.\n'
    )
    (SAIDA / 'RESUMO_AUDITORIA.txt').write_text(resumo, encoding='utf-8')
    print('\n'+resumo)
    print(f'Arquivos gerados em {SAIDA}')


if __name__ == '__main__':
    executar()
