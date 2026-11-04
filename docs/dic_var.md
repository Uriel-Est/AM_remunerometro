# Dicionário de variáveis

## Base de modelagem

| Variável | Definição / observação |
|---|---|
| `cbo` | Código de ocupação CBO com seis dígitos. |
| `grupo_ocupacional` | Estatística formal e quantitativas; TI e dados; Expansão profissional. |
| `ativo_3112` | Indicador de vínculo ativo em 31/12; o projeto seleciona código `1`. |
| `rem_dez_nom` | Remuneração nominal de dezembro em reais, positiva na base elegível. |
| `ln_rem_dez` | Logaritmo natural de `rem_dez_nom`; alvo dos modelos. |
| `rem_media_nom` | Remuneração média nominal, não utilizada como preditora. |
| `uf_sigla` | UF do estabelecimento do vínculo. |
| `code_muni` | Código IBGE municipal de seis dígitos derivado do estabelecimento. |
| `tipologia_ibge` | Urbano; Intermediário adjacente/remoto; Rural adjacente/remoto, classificação IBGE 2017. |
| `grande_regiao` | Região geográfica correspondente à UF. |
| `escolaridade` | Código RAIS de escolaridade. |
| `cnae_divisao` | Dois primeiros dígitos da CNAE. |
| `idade` | Idade informada em anos, tratada no pipeline. |
| `horas` | Jornada contratual informada, tratada no pipeline. |

## Arquivo público agregado

O exportador `08_exportar_dados_publicos.py` produz `data_public/indicadores_agregados.parquet`, com linhas agregadas por **território × CBO** e mínimo de 30 vínculos por célula.

| Coluna | Interpretação |
|---|---|
| `territorio_id` / `territorio_nome` | Identificador e rótulo do polígono agregado. |
| `grupo_ocupacional` / `cbo` | Grupo profissional e CBO da célula. |
| `n` | Número de vínculos de teste na célula. |
| `soma_obs` | Soma das remunerações observadas. |
| `soma_prev_familias` / `soma_prev_cbos` | Soma das previsões em reais, por modelo. |
| `soma_abs_familias` / `soma_abs_cbos` | Soma dos erros absolutos em reais. |
| `soma_sqlog_familias` / `soma_sqlog_cbos` | Soma dos erros quadráticos em log. |

Para um grupo com `n > 0`, o MAE é `soma_abs_... / n`, a remuneração observada média é `soma_obs / n` e o RMSE log é `sqrt(soma_sqlog_... / n)`.

**Importante:** esta base pública agregada não oferece o filtro de município individual; ele depende do dataset local mais detalhado. O `app.py` atual ainda não foi adaptado para publicação pública. A supressão de células com `n < 30` é uma proteção inicial, não uma garantia completa de confidencialidade ou proteção contra inferência por diferenças.
