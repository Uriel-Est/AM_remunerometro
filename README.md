# Remunerômetro | RAIS 2025

Projeto individual de Aprendizagem de Máquina Supervisionada — UFPB/CCSA, 2026.2.

O **Remunerômetro** investiga a remuneração nominal de dezembro de 2025 de vínculos formais em 35 ocupações selecionadas nas áreas de Estatística, métodos quantitativos, tecnologia, dados e profissões relacionadas. Compara duas formas de representação ocupacional em modelos preditivos e apresenta indicadores territoriais agregados em um painel interativo.

**[Dashboard público](https://am-renumorometro-est.streamlit.app/)** · **[Notebook](notebook/remunerometro.ipynb)** · **[Metodologia](docs/metodologia.md)** · **[Resultados](docs/resultados_modelo.md)** · **[Dicionário de variáveis](docs/dic_var.md)**

> O dashboard público apresenta indicadores agregados do conjunto de teste. Não oferece previsão salarial individual. A seleção de um município serve para identificar seu território de agregação, e não para divulgar uma estimativa específica do município.

## Pergunta de pesquisa

Em que medida representar a ocupação por CBO de seis dígitos, em vez de três grupos profissionais amplos, melhora a predição da remuneração de vínculos formais?

| Elemento | Modelo A — Grupos ocupacionais | Modelo B — 35 CBOs |
|---|---|---|
| Ocupação | Três grupos profissionais | Código CBO de seis dígitos |
| Demais preditores | UF do estabelecimento, tipologia IBGE, escolaridade, divisão CNAE, idade e jornada | Os mesmos |
| Variável-alvo | Logaritmo natural da remuneração nominal de dezembro | A mesma |
| Modelo selecionado | Ridge (`alpha=10`) | Ridge (`alpha=10`) |

Os três grupos são **Estatística formal e quantitativas**, **TI e dados** e **Expansão profissional**. As associações entre certos códigos CBO e títulos de mercado, como BI, engenharia de dados e UX/UI, são aproximações analíticas; não representam equivalências ocupacionais exatas.

## Dados e população elegível

A fonte principal é a **RAIS pública de 2025**, complementada pela tipologia rural-urbana municipal do IBGE. A unidade de análise é o **vínculo empregatício**, e não a pessoa única; uma pessoa pode possuir mais de um vínculo. A localização geográfica corresponde ao estabelecimento informado na RAIS, que pode diferir da residência do trabalhador ou de seu local efetivo de trabalho remoto.

Foram selecionados vínculos nas 35 CBOs definidas, ativos em **31/12/2025**, com remuneração nominal positiva em dezembro. A população analítica elegível possui **1.173.463 vínculos**. Os microdados e os modelos treinados não são publicados neste repositório.

Os valores monetários foram interpretados na escala decimal da fonte. O processamento não aplica conversões arbitrárias por 100.

## Desenho de treinamento e validação

A população elegível foi particionada aleatoriamente em **80% para treinamento e 20% para teste**, usando a semente numérica **`45327`**, correspondente aos seis últimos dígitos de matrícula **`045327`**. Dos vínculos da parcela de treinamento, foram selecionados aleatoriamente **2.000 vínculos** para ajustar e comparar os modelos. Os **234.693 vínculos** reservados ao teste foram mantidos fora do ajuste e da escolha de hiperparâmetros.

Foram comparados um modelo de referência pela média (`DummyRegressor`), regressão linear por mínimos quadrados ordinários (MQO), Ridge e Lasso. A seleção utilizou o menor **MAE médio em reais** numa validação cruzada com **cinco dobras**, realizada apenas na amostra de treinamento. A imputação de valores ausentes, a codificação *one-hot* e a padronização numérica foram incorporadas a pipelines, evitando que essas transformações fossem ajustadas com os dados de validação ou teste.

A remuneração é modelada em logaritmo e as previsões são exponenciadas para calcular o MAE em reais. O RMSE secundário é calculado na escala logarítmica. A exponenciação da previsão do log não necessariamente recupera a remuneração média condicional em reais, o que pode contribuir para viés de subestimação.

## Resultados finais

| Indicador | Modelo A — Grupos | Modelo B — 35 CBOs |
|---|---:|---:|
| Algoritmo selecionado | Ridge | Ridge |
| `alpha` | 10 | 10 |
| Atributos após transformação | 107 | 137 |
| MAE médio da validação cruzada | R$ 4.432,37 | R$ 4.230,23 |
| **MAE no teste** | **R$ 4.337,18** | **R$ 4.143,41** |
| RMSE no teste (escala log) | 0,6173 | 0,5891 |
| Remuneração média observada no teste | R$ 9.211,01 | R$ 9.211,01 |
| Remuneração média prevista no teste | R$ 7.541,63 | R$ 7.660,02 |
| Viés médio (previsto − observado) | −R$ 1.669,38 | −R$ 1.550,99 |

O modelo por 35 CBOs apresentou **MAE R$ 193,77 menor**, uma redução de aproximadamente **4,47%** em comparação com o modelo por grupos no conjunto de teste. Essa vantagem é descritiva e preditiva; não demonstra efeito causal da ocupação sobre a remuneração nem garante desempenho superior em toda subpopulação.

A seleção de Ridge para as duas especificações decorreu exclusivamente da validação cruzada. Os resultados do teste não foram utilizados para retreinar os modelos nem para alterar seus hiperparâmetros. Diagnósticos por sexo, escolaridade, grande região, tipologia, grupo ocupacional e CBO constam em [resultados detalhados](docs/resultados_modelo.md) e no [notebook](notebook/remunerometro.ipynb).

## Dashboard e divulgação de dados

O [dashboard público](https://am-renumorometro-est.streamlit.app/) permite consultar indicadores agregados de remuneração observada, remuneração prevista, erros e quantidade de vínculos por ocupação e recortes territoriais. O mapa apresenta agrupamentos geográficos, não previsões individualizadas de municípios.

O arquivo publicado `data_public/indicadores_agregados.parquet` contém **391 células território × CBO**, com **mínimo de 30 vínculos por célula**. Essas células representam **228.263 vínculos** do teste. Entre os 234.693 vínculos de teste, um não encontrou correspondência cartográfica e outros 6.429 ficaram fora do arquivo público em razão da supressão de células pequenas.

A supressão constitui uma precaução inicial de divulgação, **não** uma garantia completa de anonimização ou ausência de inferência por combinação de filtros. Por isso, os totais e métricas do dashboard podem divergir da avaliação sobre o conjunto completo de teste.

## Organização do repositório

```text
AM_remunerometro/
├── README.md
├── requirements.txt
├── Tipologia_municipal_rural_urbano.xlsx
├── .streamlit/
│   └── config.toml
├── code/
│   ├── caminhos.py
│   ├── 01_preparar_rais.py
│   ├── 02_preparar_modelagem.py
│   ├── 03_auditar_base.py
│   ├── 04_treinamento.py
│   ├── 05_avaliar.py
│   ├── 06_cartografia.py
│   ├── 07_prep_data.py
│   └── 08_exportar_public_data.py
├── notebook/
│   ├── remunerometro.ipynb
│   └── artefatos/                  # métricas agregadas, tabelas e metadados
├── dashboard/
│   └── app.py
├── data_public/                  # indicadores públicos e cartografia
└── docs/
    ├── metodologia.md
    ├── resultados_modelo.md
    └── dic_var.md
```

As bases de entrada, bases intermediárias, partições e modelos ajustados ficam **fora do repositório**, no diretório externo definido pelo usuário. Os únicos resultados tabulares versionados são aqueles selecionados para apresentação e divulgação agregada.

## Como executar

### Painel público

Após instalar as dependências listadas em `requirements.txt`, execute a partir da raiz do repositório:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

O painel público utiliza arquivos de `data_public/` e **não depende dos microdados da RAIS**.

### Processamento completo e modelagem

Para reproduzir as etapas analíticas, é necessário ter acesso às bases de entrada e às bibliotecas científicas utilizadas pelos scripts. Configure a variável de ambiente `REMUNEROMETRO_DATA` para apontar para a pasta externa que contém as subpastas `bronze/`, `analysis/` e `external/`:

```powershell
$env:REMUNEROMETRO_DATA = "CAMINHO_DA_PASTA_DE_DADOS"
```

O arquivo `code/caminhos.py` resolve os caminhos a partir dessa variável. **O diretório absoluto de dados não é gravado nos scripts versionados.** A pasta do repositório contém a planilha de tipologia municipal utilizada na preparação cartográfica.

O fluxo completo está organizado nos scripts `01` a `08`: seleção e consolidação da RAIS; preparação da base de modelagem; auditoria; treinamento e validação; avaliação final; cartografia; agregação territorial; e exportação dos indicadores públicos.

A etapa 05 impede a sobrescrita de uma avaliação final existente. Os resultados publicados correspondem à execução com semente `45327`; não é apropriado escolher novos algoritmos ou hiperparâmetros com base no teste já observado.

### Notebook

O notebook `notebook/remunerometro.ipynb` utiliza as tabelas e os metadados agregados em `notebook/artefatos/`. Abra a raiz do repositório como projeto e execute o notebook com essa raiz como diretório de trabalho. Dessa forma, a apresentação dos resultados independe dos microdados e dos objetos `joblib` locais.

O notebook **reproduz a apresentação dos resultados já calculados**. A reprodução integral do treinamento exige executar os scripts com acesso à base analítica original.

## Limitações

- A RAIS descreve vínculos de **emprego formal** e não cobre integralmente trabalho autônomo e informal.
- O alvo é a remuneração **nominal de dezembro de 2025**, sem deflação e sem interpretação causal.
- A amostra efetiva de **2.000 vínculos para modelagem** restringe a representação de ocupações raras e pode gerar sensibilidade à partição aleatória.
- As previsões em reais obtidas pela exponenciação de previsões em log podem apresentar viés de retrans formação.
- Os erros por subgrupo são diagnósticos descritivos, não provas de discriminação ou efeito causal.
- A geografia refere-se ao estabelecimento registrado e não é utilizada como efeito fixo municipal individual no modelo.
- O dashboard divulga somente células agregadas selecionadas; seus totais não equivalem necessariamente aos do teste integral.

## Documentação complementar

- [Metodologia](docs/metodologia.md)
- [Resultados detalhados](docs/resultados_modelo.md)
- [Dicionário de variáveis](docs/dic_var.md)
- [Notebook analítico](notebook/remunerometro.ipynb)

Projeto desenvolvido no contexto da disciplina de Aprendizagem de Máquina Supervisionada, UFPB/CCSA, semestre 2026.2.