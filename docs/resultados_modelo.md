# Resultados dos modelos — RAIS 2025

Resultados da avaliação final congelada em 03/11/2026, sobre **234.693 vínculos** de teste. Ambos os modelos foram selecionados previamente por validação cruzada.

| Indicador | Famílias | 35 CBOs |
|---|---:|---:|
| Algoritmo | Lasso | Lasso |
| Alpha | 0,001 | 0,001 |
| MAE de validação (R$) | 4.444,33 | 4.197,62 |
| MAE de teste (R$) | 4.338,33 | 4.115,23 |
| RMSE de teste (log) | 0,6171 | 0,5865 |
| Remuneração média observada no teste (R$) | 9.230,74 | 9.230,74 |
| Remuneração média prevista no teste (R$) | 7.672,44 | 7.784,68 |
| Viés médio, previsto menos observado (R$) | −1.558,30 | −1.446,06 |
| Atributos transformados / 2.000 | 110 / 2.000 | 137 / 2.000 |

O modelo por CBO apresenta MAE de teste aproximadamente R$ 223,11 menor que o modelo por famílias, uma redução descritiva de 5,14%. Essa comparação **não deve motivar uma nova seleção com o teste já observado**.

Os erros por escolaridade, sexo, ocupação, região e tipologia variam. A desigualdade de erro entre categorias não demonstra discriminação causal. No grupo Estatística formal e quantitativas, por exemplo, o modelo por famílias teve MAE inferior ao por CBOs, apesar do resultado agregado inverso.

Fontes internas: `01_metricas_finais.csv`, `RELATORIO_AVALIACAO_FINAL.md` e tabelas `03_erros_por_*.csv`, produzidos no script 05.
