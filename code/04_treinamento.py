"""04 — Remunerômetro: amostragem e comparação SEM abrir o teste.

Execute no Positron a partir da raiz do projeto. Antes, configure SEMENTE com os
6 últimos dígitos da matrícula e confirme FRACAO_TESTE conforme o laboratório 5.

Produz para DUAS especificações (grupos e CBOs) a comparação baseline/MQO/
Ridge/Lasso, 5-fold CV, curvas de validação e pipelines persistidos.
A avaliação de teste fica EXCLUSIVAMENTE para a etapa 05.
"""
from __future__ import annotations

from pathlib import Path
import json
import warnings
import hashlib
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.metrics import make_scorer, mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from caminhos import PASTA_MODELOS

ENTRADA = (
    PASTA_MODELOS
    / "rais_2025_base_modelagem_dezembro.parquet"
)

SAIDA = PASTA_MODELOS / "treinamento"

SEMENTE = 45327  # matrícula: 045327
FRACAO_TESTE = 0.20  # CONFIRMAR com a partição do laboratório 5 antes de executar.
N_AMOSTRA = 2_000
DOBRAS = 5
ALPHAS = np.logspace(-4, 4, 9)  # ponto de partida; bordas sinalizadas, nunca ocultadas

CATEGORICAS_COMUNS = ['uf_sigla', 'tipologia_ibge', 'escolaridade', 'cnae_divisao']
NUMERICAS = ['idade', 'horas']
MODELOS_OCUPACIONAIS = {'familias': 'grupo_ocupacional', 'cbos': 'cbo'}


def validar_config():
    if SEMENTE is None or not isinstance(SEMENTE, int) or not (0 <= SEMENTE <= 999999):
        raise ValueError('Configure SEMENTE = últimos seis dígitos da matrícula antes de executar o 04.')
    if not (0 < FRACAO_TESTE < 1):
        raise ValueError('FRACAO_TESTE deve estar entre 0 e 1.')
    if not ENTRADA.is_file():
        raise FileNotFoundError(f'Execute 01 → 03 → 02 antes do 04. Ausente: {ENTRADA}')


def mae_reais(y_true, y_pred):
    # y contém o log da remuneração; evita overflow sem distorcer valores normais
    pred = np.exp(np.clip(y_pred, -20, 20))
    return mean_absolute_error(np.exp(y_true), pred)


def rmse_log(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


SCORING = {
    'mae_reais': make_scorer(mae_reais, greater_is_better=False),
    'rmse_log': make_scorer(rmse_log, greater_is_better=False),
}


def montar_pipeline(ocupacao, regressor):
    categoricas = [ocupacao] + CATEGORICAS_COMUNS
    cat = Pipeline([
        ('imputar', SimpleImputer(strategy='constant', fill_value='Ausente')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', drop='first', sparse_output=True)),
    ])
    num = Pipeline([
        ('imputar', SimpleImputer(strategy='median', add_indicator=True)),
        ('escalar', StandardScaler()),
    ])
    preparar = ColumnTransformer([
        ('categoricas', cat, categoricas),
        ('numericas', num, NUMERICAS),
    ], sparse_threshold=0.3)
    return Pipeline([('preparar', preparar), ('modelo', regressor)])


def limpar(df):
    df = df.copy()
    for c in ['cbo', 'grupo_ocupacional'] + CATEGORICAS_COMUNS:
        df[c] = df[c].astype('string').str.strip().replace('', pd.NA).fillna('Ausente').astype(object)
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
    df.loc[~df['idade'].between(14, 100), 'idade'] = np.nan
    df.loc[~df['horas'].between(1, 80), 'horas'] = np.nan
    df['ln_rem_dez'] = pd.to_numeric(df['ln_rem_dez'], errors='coerce')
    if df['ln_rem_dez'].isna().any() or not np.isfinite(df['ln_rem_dez']).all():
        raise ValueError('Há logaritmos de remuneração ausentes ou não finitos.')
    if df['cbo'].nunique() != 35 or df['grupo_ocupacional'].nunique() != 3:
        raise ValueError('Esperados 35 CBOs e três grupos na população elegível.')
    return df


def cv_resultado(pipeline, X, y, cv):
    r = cross_validate(pipeline, X, y, cv=cv, scoring=SCORING,
                       return_train_score=True, n_jobs=1, error_score='raise')
    return {
        'mae_treino': float(-r['train_mae_reais'].mean()),
        'mae_cv_media': float(-r['test_mae_reais'].mean()),
        'mae_cv_dp': float(r['test_mae_reais'].std()),
        'rmse_log_treino': float(-r['train_rmse_log'].mean()),
        'rmse_log_cv_media': float(-r['test_rmse_log'].mean()),
        'rmse_log_cv_dp': float(r['test_rmse_log'].std()),
    }


def executar():
    validar_config()
    SAIDA.mkdir(parents=True, exist_ok=True)
    cols = list(dict.fromkeys(['cbo', 'grupo_ocupacional', 'ln_rem_dez'] + CATEGORICAS_COMUNS + NUMERICAS))
    df = pd.read_parquet(ENTRADA, columns=cols)
    df = limpar(df)
    y = df['ln_rem_dez']
    # Separação ANTES do sorteio individual; teste nunca é usado no 04.
    idx_treino, idx_teste = train_test_split(np.arange(len(df)), test_size=FRACAO_TESTE,
                                             random_state=SEMENTE, shuffle=True)
    if len(idx_treino) < N_AMOSTRA:
        raise ValueError('Treino tem menos de 2.000 vínculos.')
    rng = np.random.default_rng(SEMENTE)
    idx_amostra = rng.choice(idx_treino, size=N_AMOSTRA, replace=False)
    # Guarda identificadores de LINHA, não os valores reais do teste.
    np.savez_compressed(SAIDA / 'indices_particao.npz', treino=idx_treino,
                        teste=idx_teste, amostra=idx_amostra)
    df_am = df.iloc[idx_amostra].reset_index(drop=True)
    ya = df_am['ln_rem_dez']
    cv = KFold(n_splits=DOBRAS, shuffle=True, random_state=SEMENTE)
    resumo = []
    curvas = []
    selecionados = {}
    for nome_esp, ocup in MODELOS_OCUPACIONAIS.items():
        print(f'\n[ESPECIFICAÇÃO] {nome_esp} — {ocup}', flush=True)
        X = df_am[[ocup] + CATEGORICAS_COMUNS + NUMERICAS]
        candidatos = [
            ('baseline', None, DummyRegressor(strategy='mean')),
            ('mqo', None, LinearRegression()),
        ]
        for algoritmo in ['ridge', 'lasso']:
            for alpha in ALPHAS:
                reg = Ridge(alpha=float(alpha), solver='lsqr') if algoritmo == 'ridge' else Lasso(
                    alpha=float(alpha), max_iter=20_000, selection='cyclic', random_state=SEMENTE)
                candidatos.append((algoritmo, float(alpha), reg))
        resultados = []
        for algoritmo, alpha, reg in candidatos:
            pipe = montar_pipeline(ocup, reg)
            with warnings.catch_warnings(record=True) as capturadas:
                warnings.simplefilter('always')
                metricas = cv_resultado(pipe, X, ya, cv)
            if any('converge' in str(w.message).lower() for w in capturadas):
                print(f'  AVISO: convergência {algoritmo}, alpha={alpha}', flush=True)
            linha = dict(especificacao=nome_esp, algoritmo=algoritmo,
                         alpha=alpha, n_amostra=N_AMOSTRA, **metricas)
            resultados.append(linha)
            if alpha is not None:
                curvas.append(linha.copy())
            print(f'  {algoritmo:8} alpha={str(alpha):>8} MAE CV={metricas["mae_cv_media"]:,.2f}', flush=True)
        # Escolha apenas pela CV: MAE em R$ representa a decisão proposta.
        for algoritmo in ['baseline', 'mqo', 'ridge', 'lasso']:
            alternativas = [r for r in resultados if r['algoritmo'] == algoritmo]
            melhor = min(alternativas, key=lambda r: r['mae_cv_media'])
            resumo.append(melhor)
            if melhor['alpha'] is not None and (melhor['alpha'] == ALPHAS[0] or melhor['alpha'] == ALPHAS[-1]):
                print(f'  ATENÇÃO: {algoritmo} tem ótimo na BORDA da grade ({melhor["alpha"]});'
                      ' amplie ALPHAS e reexecute antes de congelar a escolha.', flush=True)
        melhor_geral = min([r for r in resumo if r['especificacao'] == nome_esp],
                           key=lambda r: r['mae_cv_media'])
        tipo, alpha = melhor_geral['algoritmo'], melhor_geral['alpha']
        reg = {'baseline': lambda: DummyRegressor(strategy='mean'),
               'mqo': lambda: LinearRegression(),
               'ridge': lambda: Ridge(alpha=alpha, solver='lsqr'),
               'lasso': lambda: Lasso(alpha=alpha, max_iter=20_000, random_state=SEMENTE)}[tipo]()
        pipe = montar_pipeline(ocup, reg).fit(X, ya)
        p = pipe.named_steps['preparar'].transform(X.iloc[:1]).shape[1]
        dump(pipe, SAIDA / f'pipeline_{nome_esp}_cv.joblib')
        selecionados[nome_esp] = dict(algoritmo=tipo, alpha=alpha, p=p,
                                      n=N_AMOSTRA, p_sobre_n=p / N_AMOSTRA,
                                      mae_cv=melhor_geral['mae_cv_media'])
    pd.DataFrame(resumo).to_csv(SAIDA / 'comparacao_validacao_cruzada.csv', sep=';', index=False, decimal=',', encoding='utf-8-sig')
    pd.DataFrame(curvas).to_csv(SAIDA / 'curvas_validacao.csv', sep=';', index=False, decimal=',', encoding='utf-8-sig')
    metadata = {
        'semente': SEMENTE, 'frac_teste': FRACAO_TESTE, 'n_populacao': int(len(df)),
        'n_treino_populacao': int(len(idx_treino)), 'n_teste_intocado': int(len(idx_teste)),
        'n_amostra': N_AMOSTRA, 'dobras': DOBRAS, 'grade_alpha': ALPHAS.tolist(),
        'selecionados_cv': selecionados, 'alvo': 'ln_rem_dez',
        'testes_abertos': False,
        'nota': 'Hiperparâmetros definidos por CV da amostra. Nenhuma métrica de teste calculada.',
    }
    (SAIDA / 'metadados_treino.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n[CONCLUÍDO] Comparação por validação cruzada. Teste INTACTO.', flush=True)
    print(f'Outputs: {SAIDA}', flush=True)
    print('Próxima etapa: gerar notebook obrigatório com diagnóstico e, só depois, avaliação única do teste.')


if __name__ == '__main__':
    executar()
