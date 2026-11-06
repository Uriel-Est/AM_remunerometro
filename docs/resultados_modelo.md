# Resultados dos modelos — RAIS 2025

Resultados da execução com semente numérica **45327** (matrícula **045327**), em **234.693 vínculos** de teste. Os modelos e hiperparâmetros foram escolhidos exclusivamente por validação cruzada na amostra de treinamento de 2.000 vínculos.

| Indicador | Famílias | 35 CBOs |
|---|---:|---:|
| Algoritmo | Ridge | Ridge |
| Alpha | 10 | 10 |
| MAE de validação (R$) | 4.432,37 | 4.230,23 |
| MAE de teste (R$) | 4.337,18 | 4.143,41 |
| RMSE de teste (log) | 0,6173 | 0,5891 |
| Remuneração média observada no teste (R$) | 9.211,01 | 9.211,01 |
| Remuneração média prevista no teste (R$) | 7.541,63 | 7.660,02 |
| Viés médio, previsto menos observado (R$) | -1.669,38 | -1.551,00 |
| Atributos transformados / 2.000 | 107 / 2.000 | 137 / 2.000 |

O modelo por 35 CBOs apresentou MAE **R$ 193,77 menor** que o modelo por famílias, uma redução descritiva de **4,47%**. Essa comparação é preditiva, não uma estimativa causal, nem prova superioridade em todos os grupos ou dados futuros. O teste não deve orientar novos ajustes de hiperparâmetros.

Os diagnósticos por escolaridade, sexo, grupo ocupacional, CBO, grande região e tipologia são apresentados nas tabelas produzidas pelo script 05 e no notebook. Os erros absolutos diferem entre grupos, em parte pela escala dos salários; isso não comprova discriminação causal.

O painel público utiliza apenas agregados de território × CBO com `n >= 30` vínculos. Os resultados do dashboard podem diferir dos resultados do teste integral em razão da supressão de células pequenas. Isso não elimina todo risco de inferência.

Fontes: `notebook/artefatos/01_metricas_finais.csv`, `notebook/artefatos/metadados_treino.json` e os demais relatórios da etapa 05.
