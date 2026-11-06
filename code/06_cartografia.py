"""06 — Camada cartográfica agregada do Remunerômetro (executar na raiz do projeto).

Baixa automaticamente a malha municipal oficial via geobr Python (2022)
na primeira execução e mantém cache em data/external/municipios_geobr.gpkg.
Planilha de tipologia IBGE 2017:
  data/Tipologia_municipal_rural_urbano.xlsx
Opcional (necessário para destacar RMs reais de capitais):
  data/external/rm_capitais_2025.csv, colunas: code_muni;nome_rm;uf_sigla
Somente associações verificadas na composição oficial IBGE 2025; não inferir por distância.

Saída: data/analysis/remunerometro/v3/modelagem_dupla/dashboard/territorios.geojson,
       municipios_catalogo.csv e cobertura_geografica.json
"""
from __future__ import annotations
from pathlib import Path
import json
import re
import unicodedata
import pandas as pd
import geopandas as gpd

from caminhos import RAIZ_DADOS, PASTA_DASH_LOCAL, PLANILHA_IBGE

EXTERNAL = RAIZ_DADOS / 'external'
GEO = EXTERNAL / 'municipios_geobr.gpkg'
TIPOLOGIA = PLANILHA_IBGE
MEMBROS_RM = EXTERNAL / 'rm_capitais_2025.csv'
SAIDA = PASTA_DASH_LOCAL
SIMPLIFICAR_METROS = 1700  # projeção métrica; suavização apenas no mapa
ANO_MALHA_GEOBR = 2022
CAPITAIS_IBGE_7 = {  # usado somente para identificar capitais que ainda não têm RM validada
'1100205','1200401','1302603','1400100','1501402','1600303','1721000',
'2111300','2211001','2304400','2408102','2507507','2611606','2704302',
'2800308','2927408','3106200','3205309','3304557','3550308','4106902',
'4205407','4314902','5002704','5103403','5208707','5300108'}

TIPOS = {
 'urbano':'Urbano', 'intermediarioadjacente':'Intermediário adjacente',
 'intermediarioremoto':'Intermediário remoto', 'ruraladjacente':'Rural adjacente',
 'ruralremoto':'Rural remoto'}

def normalizar(s):
    x = unicodedata.normalize('NFKD', str(s).lower())
    return re.sub('[^a-z]', '', ''.join(c for c in x if not unicodedata.combining(c)))

def codigo6(x):
    s = pd.Series(x, dtype='string').str.strip().str.replace(r'\.0$', '', regex=True)
    s = s.str.replace(r'\D', '', regex=True)
    return s.str[:6].where(s.str.len().ge(6))

def carregar_tipologia():
    if not TIPOLOGIA.is_file():
        raise FileNotFoundError(f'Planilha IBGE não encontrada: {TIPOLOGIA}')
    livro = pd.ExcelFile(TIPOLOGIA)
    for aba in livro.sheet_names:
        amostra = pd.read_excel(livro, sheet_name=aba, header=None, nrows=40, dtype='string')
        for i in range(len(amostra)):
            rotulos = [str(v).strip().upper() for v in amostra.iloc[i]]
            if 'CD_GCMUN' in rotulos and 'TIPO' in rotulos:
                tab = pd.read_excel(livro, sheet_name=aba, header=i, dtype='string')
                tab.columns = tab.columns.str.strip().str.upper()
                tab['code_muni'] = codigo6(tab['CD_GCMUN']).values
                tab['tipologia_ibge'] = tab['TIPO'].map(lambda x: TIPOS.get(normalizar(x)))
                if tab['tipologia_ibge'].isna().any():
                    raise ValueError('Há tipologias desconhecidas na planilha IBGE.')
                return tab[['code_muni','tipologia_ibge']].dropna().drop_duplicates('code_muni')
    raise ValueError('Não achei CD_GCMUN e TIPO na planilha IBGE.')

def obter_municipios():
    """Baixa do geobr somente quando o cache local não existe."""
    if GEO.is_file():
        print(f'[CACHE] Malha municipal geobr: {GEO}', flush=True)
        return gpd.read_file(GEO)
    try:
        from geobr import read_municipality
    except ImportError as exc:
        raise ImportError(
            'O download é automático, mas a biblioteca geobr não está instalada. '
            'Execute: python -m pip install geobr geopandas pyogrio'
        ) from exc
    print(f'[GEOBR] Baixando municípios brasileiros, ano {ANO_MALHA_GEOBR}...', flush=True)
    try:
        muni = read_municipality(code_muni='all', year=ANO_MALHA_GEOBR)
    except Exception as exc:
        raise RuntimeError(
            'Não foi possível baixar a malha do geobr. Verifique acesso à internet '
            'e tente novamente. Nenhum polígono artificial será criado.'
        ) from exc
    if muni is None or len(muni) < 5500 or muni.crs is None:
        raise ValueError('A malha baixada parece incompleta ou sem projeção; cache não foi salvo.')
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    tmp = GEO.with_name('municipios_geobr.tmp.gpkg')
    if tmp.exists():
        tmp.unlink()
    try:
        muni.to_file(tmp, driver='GPKG')
        tmp.replace(GEO)
    finally:
        if tmp.exists():
            tmp.unlink()
    print(f'[GEOBR] {len(muni):,} municípios. Cache salvo em {GEO}', flush=True)
    return muni


def executar():
    SAIDA.mkdir(parents=True, exist_ok=True)
    muni = obter_municipios()
    candidatos_codigo = ['code_muni','CD_GCMUN','cd_mun','CD_MUN','codigo_ibge']
    coluna = next((c for c in candidatos_codigo if c in muni.columns), None)
    if coluna is None:
        raise ValueError(f'Código municipal não localizado. Colunas geobr: {list(muni.columns)}')
    muni['code_muni'] = codigo6(muni[coluna]).values
    muni = muni.loc[muni.code_muni.notna()].copy()
    if muni.code_muni.duplicated().any():
        raise ValueError('Existem códigos municipais duplicados nas geometrias.')
    col_nome = next((c for c in ['name_muni','NM_MUN','nome','name'] if c in muni.columns), None)
    muni['municipio_nome'] = muni[col_nome].astype(str) if col_nome else muni['code_muni']
    muni['uf_sigla'] = muni['code_muni'].str[:2].map({
        '11':'RO','12':'AC','13':'AM','14':'RR','15':'PA','16':'AP','17':'TO',
        '21':'MA','22':'PI','23':'CE','24':'RN','25':'PB','26':'PE','27':'AL','28':'SE','29':'BA',
        '31':'MG','32':'ES','33':'RJ','35':'SP','41':'PR','42':'SC','43':'RS',
        '50':'MS','51':'MT','52':'GO','53':'DF'})
    muni = muni.merge(carregar_tipologia(), on='code_muni', how='left', validate='one_to_one')
    if muni.tipologia_ibge.isna().any():
        print(f'[AVISO] {muni.tipologia_ibge.isna().sum()} municípios sem tipologia; ficarão em grupo sem classificação.')
    muni['nome_rm'] = pd.NA
    rm_validada = False
    if MEMBROS_RM.is_file():
        rm = pd.read_csv(MEMBROS_RM, sep=';', dtype='string', encoding='utf-8-sig')
        exigir = {'code_muni','nome_rm','uf_sigla'}
        if not exigir.issubset(rm.columns):
            raise ValueError(f'{MEMBROS_RM.name} deve ter colunas {sorted(exigir)}')
        rm['code_muni'] = codigo6(rm['code_muni']).values
        rm = rm.dropna(subset=['code_muni','nome_rm']).copy()
        # Cada município deve pertencer a uma única área de destaque.
        if rm.code_muni.duplicated().any():
            raise ValueError('Há municípios em mais de uma RM de capital. Resolva sobreposições explicitamente.')
        muni = muni.drop(columns='nome_rm').merge(rm[['code_muni','nome_rm','uf_sigla']].rename(columns={'uf_sigla':'uf_rm'}), on='code_muni', how='left', validate='one_to_one')
        diverg = muni.loc[muni.nome_rm.notna() & muni.uf_sigla.ne(muni.uf_rm)]
        if not diverg.empty:
            raise ValueError('Incompatibilidade de UF no arquivo de RM.')
        rm_validada = True
    muni['territorio_classe'] = muni['tipologia_ibge'].fillna('Sem classificação')
    muni.loc[muni.nome_rm.notna(),'territorio_classe'] = 'RM da capital'
    muni['territorio_id'] = muni['uf_sigla'].fillna('NI') + '__' + muni['territorio_classe']
    muni['territorio_nome'] = muni['uf_sigla'].fillna('NI') + ' · ' + muni['territorio_classe']
    cols = ['code_muni','municipio_nome','uf_sigla','tipologia_ibge','nome_rm','territorio_id','territorio_nome','territorio_classe']
    muni[cols].to_csv(SAIDA / 'municipios_catalogo.csv', sep=';', index=False, encoding='utf-8-sig')
    # Não dissolve na projeção em graus: usa plano métrico para simplificar com tolerância.
    geometria = muni[['territorio_id','territorio_nome','territorio_classe','uf_sigla','geometry']].copy().to_crs(5880)
    dissolvido = geometria.dissolve(by='territorio_id', as_index=False, aggfunc='first')
    dissolvido['geometry'] = dissolvido.geometry.simplify(SIMPLIFICAR_METROS, preserve_topology=True)
    dissolvido = dissolvido.to_crs(4326)
    dissolvido.to_file(SAIDA / 'territorios.geojson', driver='GeoJSON')
    resumo = {'fonte_malha':'geobr Python', 'ano_malha':ANO_MALHA_GEOBR, 'municipios_geobr':len(muni),'territorios':len(dissolvido),
              'municipios_tipologia_ausente':int(muni.tipologia_ibge.isna().sum()),
              'rm_capitais_validada':rm_validada,'municipios_com_rm':int(muni.nome_rm.notna().sum()),
              'fonte_rm':'Composição IBGE 2025 revisada em 29/07/2026; correspondência manual verificada' if rm_validada else 'NÃO FORNECIDA — mapa apenas por tipologia/UF'}
    (SAIDA/'cobertura_geografica.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2),encoding='utf-8')
    print('[OK] Geografia:', resumo)

if __name__ == '__main__':
    executar()
