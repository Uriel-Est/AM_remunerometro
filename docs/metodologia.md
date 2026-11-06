# Metodologia do Remunerômetro 2025

## Objetivo

Comparar duas especificações preditivas para remuneração nominal de dezembro em vínculos formais da RAIS 2025, entre 35 CBOs selecionados para carreiras quantitativas, de tecnologia, dados e áreas de expansão. A unidade estatística é o **vínculo**, não o trabalhador único.

## Universo e variável-alvo

Foram selecionados vínculos ativos em 31/12/2025, com remuneração de dezembro positiva, nas 35 ocupações definidas pelo projeto. A base elegível compreende **1.173.463 vínculos**. A variável-alvo é o logaritmo da remuneração nominal de dezembro. A remuneração em reais utilizada no MAE é obtida por exponenciação da previsão em log; não deve ser interpretada automaticamente como média condicional em reais.

## Duas especificações independentes

- **Famílias**: representação ocupacional com três grupos: Estatística formal e quantitativas; TI e dados; Expansão profissional.
- **35 CBOs**: representação ocupacional por código CBO completo, com one-hot encoding.

Os demais preditores são compartilhados: UF do estabelecimento, tipologia rural-urbana municipal IBGE, escolaridade, divisão CNAE, idade e jornada. O município é usado para associação territorial, não como um efeito municipal individual no modelo. As correspondências entre CBO e títulos comerciais (como UX/UI ou BI) são aproximações, não equivalências garantidas.

## Partição e avaliação

A divisão registrada foi de 80% para treinamento e 20% para teste, com semente numérica **45327** (matrícula **045327**). Foram sorteados **2.000 vínculos apenas do treinamento** para ajuste e validação cruzada com cinco dobras. Foram comparados baseline, MQO, Ridge e Lasso, e a seleção de modelos e hiperparâmetros ocorreu pelo menor MAE médio de validação cruzada.

Ambas as especificações selecionaram **Ridge com `alpha=10`**. O teste de **234.693 vínculos** foi avaliado uma vez nesta execução na etapa 05, sem reajuste dos modelos. Os MAEs finais foram R$ 4.337,18 (Famílias) e R$ 4.143,41 (35 CBOs). A semente foi corrigida para cumprir o protocolo da matrícula, e não para escolher o melhor resultado no teste.

Os scripts usam `code/caminhos.py` e a variável de ambiente `REMUNEROMETRO_DATA` para acessar os dados analíticos externos ao repositório. O notebook pode reproduzir tabelas e gráficos a partir dos artefatos agregados versionados, sem depender dos microdados.

## Cartografia e interpretação

A versão geográfica agrega municípios por UF e tipologia; a camada metropolitana só é utilizada quando existe correspondência territorial oficial documentada. Um agrupamento cartográfico não representa um coeficiente estimado por região metropolitana. Erros por território são métricas descritivas do conjunto de teste e não evidência de efeitos causais.

## Limitações

A amostra de treino tem categorias ocupacionais raras, especialmente em Estatística; a RAIS exclui parte do mercado informal e do trabalho autônomo; a conversão de previsões em log pode produzir viés negativo em reais. Resultados por células pequenas devem ser suprimidos no painel público. Não publicar microdados ou previsões individuais.
