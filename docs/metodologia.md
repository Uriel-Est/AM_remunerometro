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

A divisão registrada foi 80% treino e 20% teste, com semente 5327; **2.000 vínculos foram sorteados do treino** para ajuste e validação cruzada com cinco dobras. Dentro de cada especificação foram avaliados baseline, MQO, Ridge e Lasso. A seleção de hiperparâmetros ocorreu exclusivamente por validação cruzada. O teste de 234.693 vínculos foi utilizado uma única vez na etapa 05, sem novo ajuste dos modelos.

Ambas as especificações selecionaram Lasso com `alpha=0.001`. A regra de 20% de teste precisa ser confrontada com o procedimento exato previsto no laboratório de referência, se ele exigir outra fração.

## Cartografia e interpretação

A versão geográfica agrega municípios por UF e tipologia; a camada metropolitana só é utilizada quando existe correspondência territorial oficial documentada. Um agrupamento cartográfico não representa um coeficiente estimado por região metropolitana. Erros por território são métricas descritivas do conjunto de teste e não evidência de efeitos causais.

## Limitações

A amostra de treino tem categorias ocupacionais raras, especialmente em Estatística; a RAIS exclui parte do mercado informal e do trabalho autônomo; a conversão de previsões em log pode produzir viés negativo em reais. Resultados por células pequenas devem ser suprimidos no painel público. Não publicar microdados ou previsões individuais.
