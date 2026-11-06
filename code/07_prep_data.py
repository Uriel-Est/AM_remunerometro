"""07 — Agrega resultados congelados do teste para uso interativo no dashboard.

Não faz fit, não altera hiperparâmetros, não cria novo teste. Os resultados
são DESCRITIVOS do mesmo teste já avaliado no 05; não são nova seleção de modelo.
Não exporta previsões individuais; o CSV agregado deve permanecer fora do GitHub.
"""
from __future__ import annotations
from pathlib import Path
import json
import warnings
import numpy as np
import pandas as pd
from joblib import load
from sklearn.exceptions import InconsistentVersionWarning

from caminhos import PASTA_MODELOS

BASE_DIR = PASTA_MODELOS
BASE = BASE_DIR/'rais_2025_base_modelagem_dezembro.parquet'
TREINO = BASE_DIR/'treinamento'
GEOGRAFIA = BASE_DIR/'dashboard'
SAIDA = GEOGRAFIA/'indicadores_teste_municipio_cbo.parquet'
COLS_CAT = ['uf_sigla','tipologia_ibge','escolaridade','cnae_divisao']
COLS_NUM = ['idade','horas']

def limpar(df):
    df = df.copy()
    for c in ['cbo','grupo_ocupacional']+COLS_CAT:
        df[c] = df[c].astype('string').str.strip().replace('',pd.NA).fillna('Ausente').astype(object)
    for c in COLS_NUM:
        df[c] = pd.to_numeric(df[c],errors='coerce').replace([np.inf,-np.inf],np.nan)
    df.loc[~df.idade.between(14,100),'idade'] = np.nan
    df.loc[~df.horas.between(1,80),'horas'] = np.nan
    return df

def executar():
    if not (GEOGRAFIA/'municipios_catalogo.csv').is_file():
        raise FileNotFoundError('Execute primeiro 06_preparar_geografia.py.')
    with np.load(TREINO/'indices_particao.npz',allow_pickle=False) as arq:
        idx_teste = arq['teste'].copy()
    meta = json.loads((TREINO/'metadados_treino.json').read_text(encoding='utf-8'))
    colunas = ['code_muni','cbo','grupo_ocupacional','ln_rem_dez','rem_dez_nom']+COLS_CAT+COLS_NUM
    df = pd.read_parquet(BASE,columns=colunas)
    if len(df)!=meta['n_populacao'] or len(idx_teste)!=meta['n_teste_intocado']:
        raise ValueError('Base não corresponde à partição salva no 04.')
    teste = limpar(df.iloc[idx_teste].reset_index(drop=True))
    del df
    if not np.allclose(np.log(pd.to_numeric(teste.rem_dez_nom)),teste.ln_rem_dez,atol=1e-8,rtol=0):
        raise ValueError('Inconsistência do alvo com remuneração declarada.')
    catalogo = pd.read_csv(GEOGRAFIA/'municipios_catalogo.csv',sep=';',dtype='string')
    # code_muni: município de estabelecimento usado originalmente no 01.
    teste['code_muni'] = teste['code_muni'].astype('string')
    teste = teste.merge(catalogo[['code_muni','municipio_nome','territorio_id','territorio_nome']],on='code_muni',how='left',validate='many_to_one')
    if teste.territorio_id.isna().any():
        print(f'[AVISO] {teste.territorio_id.isna().sum()} vínculos sem correspondência cartográfica; não entram no mapa.')
    teste = teste.loc[teste.territorio_id.notna()].copy()
    y_real = pd.to_numeric(teste.rem_dez_nom).to_numpy(dtype=float)
    teste['n'] = 1
    teste['soma_obs'] = y_real
    for especificacao,ocup in [('familias','grupo_ocupacional'),('cbos','cbo')]:
        with warnings.catch_warnings():
            warnings.simplefilter('error', InconsistentVersionWarning)
            modelo = load(TREINO/f'pipeline_{especificacao}_cv.joblib')
        # Mesmo pipeline do 04/05, sem fit.
        log_prev = modelo.predict(teste[[ocup]+COLS_CAT+COLS_NUM])
        valor_prev = np.exp(np.clip(log_prev,-20,20))
        teste[f'soma_prev_{especificacao}'] = valor_prev
        teste[f'soma_abs_{especificacao}'] = np.abs(valor_prev-y_real)
        teste[f'soma_sqlog_{especificacao}'] = np.square(log_prev - teste.ln_rem_dez.to_numpy(dtype=float))
    chaves = ['code_muni','municipio_nome','territorio_id','territorio_nome','cbo','grupo_ocupacional']
    campos = ['n','soma_obs','soma_prev_familias','soma_abs_familias','soma_sqlog_familias',
              'soma_prev_cbos','soma_abs_cbos','soma_sqlog_cbos']
    agregados = teste.groupby(chaves,dropna=False,observed=True)[campos].sum().reset_index()
    SAIDA.parent.mkdir(parents=True,exist_ok=True)
    agregados.to_parquet(SAIDA,index=False,compression='zstd')
    resumo = {'amostra':'teste_congelado_04','n_teste':len(idx_teste),
              'n_teste_mapeado':len(teste),'grupos_agregados':len(agregados),
              'sem_retreino':True,'dados_individuais_exportados':False,
              'recomendacao':'Não publicar o Parquet agregado sem revisão de risco de divulgação; pequenas células são ocultadas na interface.'}
    (GEOGRAFIA/'resumo_indicadores.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2),encoding='utf-8')
    print('[OK] Indicadores municipais × CBO:',resumo)

if __name__=='__main__':
    executar()
