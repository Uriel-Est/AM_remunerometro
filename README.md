# Remunerômetro | RAIS 2025

**Projeto individual de Aprendizagem de Máquina Supervisionada — UFPB/CCSA, 2026.2**

O Remunerômetro investiga a remuneração nominal de dezembro de 2025 de vínculos formais em 35 ocupações selecionadas, ligadas à Estatística, áreas quantitativas, tecnologia, dados e profissões relacionadas. O projeto compara duas formas de representar a ocupação em modelos supervisionados e disponibiliza resultados territoriais em um painel interativo.

**[Acessar o dashboard público](https://am-renumorometro-est.streamlit.app/)** · **[Notebook do projeto](notebook/remunerometro.ipynb)** · **[Metodologia](docs/metodologia.md)** · **[Resultados detalhados](docs/resultados_modelo.md)** · **[Dicionário de variáveis](docs/dic_var.md)**

> O painel público apresenta **indicadores agregados do conjunto de teste**, não salários individuais nem novas previsões para perfis informados pelo usuário. A visualização municipal funciona como localizador territorial, e não como estimativa específica de um município.

## Pergunta de pesquisa

Em que medida o detalhamento da ocupação melhora a predição da remuneração dos vínculos formais? Para responder, foram comparadas duas especificações com os mesmos preditores, exceto pela representação ocupacional:

| Elemento | Modelo A — Famílias | Modelo B — 35 CBOs |
|---|---|---|
| Ocupação | Três grupos profissionais | 35 códigos CBO de seis dígitos |
| Demais atributos | UF do estabelecimento, tipologia IBGE, escolaridade, idade, jornada e divisão CNAE | Os mesmos |
| Alvo | Log da remuneração nominal de dezembro de 2025 | O mesmo |
| Modelo selecionado por validação cruzada | Lasso (`alpha=0.001`) | Lasso (`alpha=0.001`) |

Os grupos profissionais são **Estatística formal e quantitativas**, **TI e dados** e **Expansão profissional**. Os códigos CBO utilizados para aproximar ocupações associadas a BI, UX ou engenharia de dados não constituem equivalências exatas com esses títulos de mercado.

## Dados e recorte

A fonte principal é a **RAIS pública de 2025**, complementada pela tipologia rural-urbana municipal do IBGE. A unidade de análise é o **vínculo empregatício**, não a pessoa trabalhadora: uma pessoa pode ter mais de um vínculo. O município e a UF referem-se ao estabelecimento registrado, não necessariamente à residência do trabalhador ou ao local de prestação de serviço remoto.

A seleção analítica considera vínculos nas 35 CBOs escolhidas, ativos em **31/12/2025**, com remuneração nominal de dezembro positiva. O processamento identificou **1.173.463 vínculos elegíveis**. Os microdados não são distribuídos neste repositório.

A remuneração de dezembro na base de origem utiliza ponto decimal, como `2715.58`. O processamento preserva essa escala, sem multiplicar ou dividir arbitrariamente os valores por 100.

## Estratégia de treinamento e avaliação

A população elegível foi dividida em **80% para treinamento e 20% para teste**. Foram sorteados **2.000 vínculos somente da parcela de treinamento**, com semente registrada `5327`. A escolha de algoritmo e hiperparâmetros usou **validação cruzada com cinco dobras** e comparação entre baseline, regressão linear, Ridge e Lasso.

O pré-processamento e a codificação one-hot foram incorporados aos pipelines, para evitar vazamento de informações do teste. O conjunto de teste, com **234.693 vínculos**, foi usado na avaliação final após a seleção dos modelos; não foi empregado para novas decisões de ajuste.

### Resultados da avaliação final

| Métrica | Modelo A — Famílias | Modelo B — 35 CBOs |
|---|---:|---:|
| Algoritmo escolhido | Lasso | Lasso |
| `alpha` | 0,001 | 0,001 |
| MAE da validação cruzada | R$ 4.444,33 | R$ 4.197,62 |
| **MAE no teste** | **R$ 4.338,33** | **R$ 4.115,23** |
| RMSE no teste (escala log) | 0,6171 | 0,5865 |
| Remuneração média observada no teste | R$ 9.230,74 | R$ 9.230,74 |
| Remuneração média prevista no teste | R$ 7.672,44 | R$ 7.784,68 |

A especificação de 35 CBOs apresentou MAE aproximadamente **R$ 223,11 menor**, redução de **5,14%** em relação à especificação por famílias, na avaliação de teste. Isso representa uma comparação preditiva, não um efeito causal do código ocupacional sobre a remuneração. A transformação de previsões em log de volta para reais pode contribuir para subestimação das médias em reais.

Os resultados completos e diagnósticos por grupos estão descritos em [`docs/resultados_modelo.md`](docs/resultados_modelo.md) e no [`notebook/remunerometro.ipynb`](notebook/remunerometro.ipynb).

## Dashboard interativo

**[Abrir o Remunerômetro no Streamlit](https://am-renumorometro-est.streamlit.app/)**

O dashboard público permite navegar por **modelo, grupo ocupacional, CBO, grande região, UF e tipologia municipal**, além de comparar remuneração observada, remuneração prevista, MAE, viés e quantidade de vínculos nas agregações publicadas. O mapa coroplético, os gráficos e as tabelas são construídos a partir dos arquivos em `data_public/`.

Para melhorar o desempenho, a interface pública abre inicialmente uma visão geral e **carrega a cartografia sob demanda**. O arquivo cartográfico leve é utilizado quando presente; caso contrário, o aplicativo utiliza `territorios.geojson`.

**Diferença entre as versões:** a versão **local**, executada com os dados analíticos externos ao GitHub, permite consultas mais detalhadas por município. A versão **pública** usa apenas resultados agregados por território e CBO: selecionar um município serve para localizar seu território, **não** para divulgar um salário ou erro individualizado para aquela cidade.

Os agregados públicos foram preparados com supressão de células território × CBO com **menos de 30 vínculos**. Essa proteção inicial não garante, isoladamente, ausência de risco de inferência por combinação de filtros. Os totais apresentados no painel público podem diferir dos resultados completos do conjunto de teste, pois refletem somente as células publicadas.

## Estrutura do repositório

```text
AM_remunerometro/
├── README.md
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── code/
│   ├── 01_preparar_rais.py
│   ├── 02_preparar_modelagem.py
│   ├── 03_auditar_base.py
│   ├── 04_treinamento.py
│   ├── 05_avaliar.py
│   ├── 06_cartografia.py
│   ├── 07_prep_data.py
│   └── 08_exportar_public_data.py
├── dashboard/
│   └── app.py
├── notebook/
│   ├── remunerometro.ipynb
│   └── artefatos/
├── data_public/
│   ├── indicadores_agregados.parquet
│   ├── municipios_catalogo.csv
│   └── territorios.geojson
└── docs/
    ├── metodologia.md
    ├── resultados_modelo.md
    └── dic_var.md
```

O repositório também contém a planilha de tipologia municipal do IBGE. Os nomes acima refletem a organização efetivamente adotada no GitHub; em particular, as pastas são `code/` e `notebook/`, no singular.

## Executar o dashboard público localmente

Requer Python e acesso aos arquivos desta cópia do repositório.

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

O `dashboard/app.py` do GitHub usa arquivos relativos à raiz do repositório, sem exigir `C:\Users\uriel\data`. Esse `requirements.txt` atende à **aplicação publicada**. Para executar os scripts de treinamento e o notebook analítico, são necessárias também as dependências científicas correspondentes e os dados/artefatos locais.

### Reproduzir o processamento e a modelagem

O fluxo de scripts é `01` → `02` → `03` → `04` → `05` → `06` → `07` → `08`, conforme os nomes atuais de `code/`. A preparação utiliza os arquivos RAIS 2025 e a tipologia IBGE; as etapas seguintes realizam auditoria, treinamento, avaliação, preparação geográfica e exportação dos resultados públicos. As saídas de análise e os modelos treinados são mantidos fora do GitHub, sob a raiz de dados local `C:\Users\uriel\data`, separada da pasta do código.

**Atenção:** os resultados registrados neste README correspondem à execução já encerrada. Reexecutar scripts com dados, bibliotecas ou partições diferentes pode gerar resultados distintos; não se deve escolher um novo modelo usando o teste anteriormente consultado.

## Limitações e interpretação

- A RAIS descreve **emprego formal**, não cobre de forma integral trabalho autônomo, prestação de serviços ou ocupações informais.
- A variável prevista é a remuneração nominal de um mês específico, dezembro de 2025, sem ajuste inflacionário.
- Os modelos são **preditivos**, não estimativas causais de retornos salariais.
- A amostra de treinamento de 2.000 vínculos limita a precisão em CBOs pouco frequentes, especialmente no grupo de Estatística.
- As métricas do painel público referem-se às **células divulgadas**, e não necessariamente ao conjunto de teste integral.
- A geografia identifica o estabelecimento vinculado ao registro; o município não entra como um efeito fixo individual no modelo.

## Documentação

- [Metodologia](docs/metodologia.md)
- [Resultados dos modelos](docs/resultados_modelo.md)
- [Dicionário de variáveis](docs/dic_var.md)
- [Notebook de análise](notebook/remunerometro.ipynb)

Projeto desenvolvido no contexto da disciplina de Aprendizagem de Máquina Supervisionada, UFPB/CCSA, semestre 2026.2.
