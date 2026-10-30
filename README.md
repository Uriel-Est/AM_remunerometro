# Remunerômetro — RAIS 2025

Projeto individual de Aprendizagem de Máquina Supervisionada (UFPB/CCSA, 2026.2). O objetivo é estimar a **remuneração nominal de dezembro de 2025** de vínculos formais da RAIS para carreiras quantitativas, tecnologia, dados e áreas profissionais relacionadas. O resultado planejado é um dashboard simples com exploração ocupacional e territorial. **O projeto está na fase de preparação e auditoria; ainda não há modelos treinados ou desempenho de teste.**

## Pergunta aplicada

**Usuário-alvo:** profissional interessado em comparar referências de remuneração formal. **Decisão apoiada:** avaliar referências salariais conforme perfil ocupacional e características do vínculo e do estabelecimento. A RAIS cobre **vínculos formais**, não honorários PJ ou faturamento autônomo. A unidade estatística é o vínculo, não uma pessoa única.

## Duas especificações independentes

| | Modelo A — grupos | Modelo B — CBOs |
|---|---|---|
| Ocupação | One-hot dos **3 grupos**: Estatística formal e quantitativas, TI e dados, Expansão profissional | One-hot dos **35 CBOs** de 6 dígitos |
| Geografia | UF do **estabelecimento** e tipologia municipal IBGE 2017 | As mesmas |
| Outras candidatas | Escolaridade, idade, horas contratadas e divisão CNAE | As mesmas |
| Algoritmos a comparar | Baseline, regressão linear (MQO), Ridge e Lasso | Os mesmos |
| Resposta | `ln_rem_dez` = logaritmo da remuneração de dezembro | A mesma |

A família e o CBO são usados para **filtros encadeados no dashboard**, mas *não* entram juntos como duas codificações ocupacionais redundantes na mesma especificação. A grande região, UF, município e tipologia serão filtros de navegação e visualização. Na especificação preditiva inicial, o município identifica o estabelecimento e a tipologia; não será aplicado one-hot aos milhares de municípios. A informação territorial não identifica necessariamente o lugar de residência nem o local efetivo de trabalho remoto.

## Fontes

- Sete arquivos de vínculos da RAIS Bronze 2025, em `data/bronze/rais_publica/2025/`, `rais_vinc_pub_*_2025.parquet` (indisponíveis neste repositório) conforme a lista fechada no script 01.
- Tipologia municipal rural-urbana do IBGE, planilha `data/Tipologia_municipal_rural_urbano.xlsx`, coluna `CD_GCMUN` (7 dígitos) e `TIPO`. Para o cruzamento, usam-se os primeiros 6 dígitos.
- As famílias de CBO e cinco CBOs adicionais estão explicitados no script 01. Alguns rótulos de mercado (BI, UX, engenharia de dados) são **aproximações**, não equivalências oficiais.

Resultados anteriores, para referência e conferência depois da regeneração: **91.710.262 vínculos lidos**, **1.635.107 candidatos** e **1.173.463 vínculos elegíveis**, distribuídos entre Expansão (627.020), TI e dados (531.887) e Estatística formal e quantitativas (14.556). Esses totais são resultados de execuções prévias e não dispensam verificar os relatórios produzidos pela versão consolidada.

## Scripts oficiais

| Arquivo | Responsabilidade | Estado |
|---|---|---|
| `scripts/01_preparar_rais.py` | Lê Bronze em lotes, seleciona CBOs, cruza tipologia e cria Parquet analítico com **salários já na escala correta** | Pronto; sintaxe verificada |
| `scripts/03_preparar_modelagem.py` | Filtra ativos em 31/12 e remuneração positiva de dezembro, acrescenta três grupos e grande região, gera base elegível | Pronto; sintaxe verificada |
| `scripts/02_auditar_base.py` | Audita a **saída do 03** sem alterar os Parquet | Mantido sem alterações; sintaxe verificada |
| `notebooks/` | Amostragem, treino e comparação das duas especificações | Pendente |
| `dashboard/app.py` | Interface Streamlit e mapa | Pendente |

> **Ordem efetiva de execução: `01 → 03 → 02`.** Os nomes `02` e `03` foram mantidos conforme solicitado; o `02` audita especificamente a base gerada pelo `03`.

## Conversão salarial — correção consolidada

Na Bronze, foram observados valores como `'2715.58'`, `'14654.96'` e `'.00'` — **o ponto já é o separador decimal**. Um conversor antigo removia todos os pontos e inflava as remunerações em fator 100, corrigido provisoriamente por divisão posterior.

Nesta versão, o `01` interpreta diretamente números com ponto decimal e também aceita vírgula decimal simples; interrompe a execução quando identifica formatos com dois separadores (ambíguos), em vez de presumir fator de escala. **Não aplique nenhum script de divisão por 100 à nova saída.** A auditoria de escala passa a se chamar `auditoria_remuneracao_2025.csv`. Antes de substituir resultados locais, confira as estatísticas e valores extremos. Para campos não remuneratórios, a conversão é tratada separadamente.

## Preparação local

Use o **Positron**, abrindo a **raiz** do projeto como diretório atual (`Path.cwd()`). Scripts não usam `argparse`.

```bash
python -m pip install -r requirements.txt
```

Estrutura esperada:

```text
remunerometro/
├── README.md
├── .gitignore
├── requirements.txt
├── scripts/
│   ├── 01_preparar_rais.py
│   ├── 02_auditar_base.py
│   └── 03_preparar_modelagem.py
├── notebooks/                 # etapa futura
├── dashboard/                 # etapa futura
├── docs/                      # documentação e checklist
├── models/                    # modelos treinados, local
├── outputs/                   # figuras e tabelas
└── data/                      # não versionar microdados
    ├── Tipologia_municipal_rural_urbano.xlsx
    ├── bronze/rais_publica/2025/
    └── analysis/remunerometro/v3/
```

### Etapa 1 — preparar RAIS

Execute `scripts/01_preparar_rais.py`. Entrada: Bronze regional e planilha do IBGE. Saída em `data/analysis/remunerometro/v3/`:

- `rais_2025_candidatos_ampliados.parquet` — remuneração corretamente interpretada, **não dividido novamente**.
- `frequencia_cbo_2025.csv` — catálogo observado, usado pelo script 03.
- `auditoria_remuneracao_2025.csv`, `auditoria_2025.csv`, frequências por UF/CBO/tipologia e demais diagnósticos.

### Etapa 2 — preparar população elegível

Execute `scripts/03_preparar_modelagem.py`, que lê **diretamente** `rais_2025_candidatos_ampliados.parquet` e `frequencia_cbo_2025.csv`. Exige `ativo_3112 == '1'` e `rem_dez_nom > 0`; não descarta vínculos automaticamente por valores ausentes de idade, jornada, escolaridade ou geografia. Cria em `data/analysis/remunerometro/v3/modelagem_dupla/`:

- `rais_2025_base_modelagem_dezembro.parquet`
- `catalogo_35_cbos_3_grupos.csv`
- `auditoria_elegibilidade.csv` e frequências de grupos, CBO, grande região e código de atividade.

### Etapa 3 — auditoria final

Execute `scripts/02_auditar_base.py`, que lê a base elegível e seu catálogo. Relatórios em `data/analysis/remunerometro/v3/modelagem_dupla/auditoria_final/`; não edita bases ou faz decisões sobre amostragem.

**Observação de compatibilidade:** resultados antigos gerados a partir de `rais_2025_candidatos_ampliados_salarios_corrigidos.parquet` pertencem ao fluxo anterior. O fluxo oficial atual tem **apenas um Parquet analítico na saída do 01**; não use os dois simultaneamente.

## Próxima etapa — modelagem

A atividade requer a partição treino/teste conforme o laboratório 5 e **sorteio aleatório de 2.000 vínculos exclusivamente do treinamento**, com semente igual aos seis últimos dígitos da matrícula. O pré-processamento deve ocorrer **dentro dos pipelines** e a comparação das especificações deve utilizar os mesmos índices de treino/teste e as mesmas partições de validação cruzada (5 folds), sempre que possível. Não usar o conjunto de teste para escolher modelos ou hiperparâmetros. Métricas: **MAE em reais** e **RMSE em log**; relatar ainda `p/n`, curvas de validação e diagnósticos por sexo e escolaridade. O notebook oficial ainda será incorporado.

## Dashboard planejado

Aplicação Streamlit, com chave para alternar entre as duas especificações, filtros de grupo, CBO (quando aplicável), tipologia IBGE, grande região, UF e município, mapa e estimativa de remuneração. Previsões de combinações pouco observadas deverão ter aviso de limitação amostral. Dashboard não está implementado.

## Reprodutibilidade e privacidade

Microdados Parquet (Bronze, Silver, Gold e Analysis), tabelas de resultados potencialmente grandes e modelos binários são mantidos fora do Git por `.gitignore`. Versionar código, documentação, configurações e relatórios agregados adequados, respeitando termos das fontes. O GitHub não substitui o armazenamento dos dados originais no computador.

## Checklist

- [x] Definir objetivo e usuário-alvo.
- [x] Selecionar 35 CBOs e três agrupamentos.
- [x] Associar tipologia IBGE e UF do estabelecimento.
- [x] Consolidar extração e conversão salarial no script 01.
- [x] Preparar script 03 e preservar auditoria 02.
- [ ] Reexecutar fluxo oficial `01 → 02 → 03` e validar contagens e salários.
- [ ] Incorporar notebook modelo do professor e partição do laboratório.
- [ ] Treinar baseline, MQO, Ridge e Lasso em cada especificação.
- [ ] Avaliar validação e teste sem vazamento.
- [ ] Preparar dashboard e documentação final de uso de IA.
