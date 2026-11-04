"""Remunerômetro — versão PÚBLICA para Streamlit Community Cloud.

Lê exclusivamente os agregados revisados em data_public/ no repositório.
Não depende do caminho C:/Users/uriel/data nem usa modelos joblib.
Não produz resultados específicos de municípios: apenas apresenta o território
agregado ao qual o município pertence.
"""
from __future__ import annotations

import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.colormap import linear

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data_public"
PARQUET = PUBLIC / "indicadores_agregados.parquet"
CATALOG = PUBLIC / "municipios_catalogo.csv"
MAP = (PUBLIC / "territorios_leve.geojson") if (PUBLIC / "territorios_leve.geojson").exists() else (PUBLIC / "territorios.geojson")
MIN_N = 30
REGIONS = {
    "Norte": ["RO", "AC", "AM", "RR", "PA", "AP", "TO"],
    "Nordeste": ["MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA"],
    "Sudeste": ["MG", "ES", "RJ", "SP"],
    "Sul": ["PR", "SC", "RS"],
    "Centro-Oeste": ["MS", "MT", "GO", "DF"],
}
METRICS = {
    "Erro absoluto médio (MAE)": "mae",
    "Remuneração observada": "observado",
    "Remuneração prevista": "previsto",
    "Viés médio": "vies",
    "Quantidade de vínculos": "n",
}
REQUIRED = ["territorio_id", "territorio_nome", "grupo_ocupacional", "cbo",
            "n", "soma_obs", "soma_prev_familias", "soma_abs_familias",
            "soma_sqlog_familias", "soma_prev_cbos", "soma_abs_cbos", "soma_sqlog_cbos"]

st.set_page_config(page_title="Remunerômetro | RAIS 2025", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1580px;}
[data-testid="stMetric"] {border: 1px solid rgba(130,130,130,.25); border-radius: 12px; padding: .8rem 1rem;}
</style>
""", unsafe_allow_html=True)


def brl(value):
    if pd.isna(value):
        return "—"
    return "R$ " + f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


@st.cache_data(show_spinner="Carregando indicadores públicos...")
def load_tables():
    agg = pd.read_parquet(PARQUET)
    missing = sorted(set(REQUIRED).difference(agg.columns))
    if missing:
        raise ValueError(f"Parquet público não tem as colunas esperadas: {missing}")
    for key in ["territorio_id", "territorio_nome", "grupo_ocupacional", "cbo"]:
        agg[key] = agg[key].astype("string").str.strip()
    for key in REQUIRED[4:]:
        agg[key] = pd.to_numeric(agg[key], errors="raise")
    if agg[REQUIRED[4:]].isna().any().any() or (agg["n"] < MIN_N).any():
        raise ValueError("O exportador público contém nulos ou células abaixo do limiar de 30.")
    if agg.duplicated(["territorio_id", "grupo_ocupacional", "cbo"]).any():
        raise ValueError("Há chaves agregadas repetidas no arquivo público.")
    cat = pd.read_csv(CATALOG, sep=";", encoding="utf-8-sig", dtype="string")
    required_cat = {"code_muni", "municipio_nome", "uf_sigla", "tipologia_ibge", "territorio_id"}
    if required_cat - set(cat):
        raise ValueError(f"Colunas ausentes no catálogo: {sorted(required_cat - set(cat))}")
    for c in required_cat:
        cat[c] = cat[c].astype("string").str.strip()
    cat = cat.drop_duplicates("code_muni")
    return agg, cat


@st.cache_data(show_spinner="Carregando polígonos geográficos...")
def load_geojson():
    with MAP.open("r", encoding="utf-8") as fp:
        obj = json.load(fp)
    if obj.get("type") != "FeatureCollection":
        raise ValueError("territorios.geojson não é uma FeatureCollection")
    return obj


def summarize(df, grouping, variant):
    cols = ["n", "soma_obs", f"soma_prev_{variant}", f"soma_abs_{variant}", f"soma_sqlog_{variant}"]
    if df.empty:
        out = pd.DataFrame(columns=grouping + cols) if grouping else pd.DataFrame([{c: 0. for c in cols}])
    elif grouping:
        out = df.groupby(grouping, dropna=False, as_index=False)[cols].sum()
    else:
        out = pd.DataFrame([df[cols].sum()])
    n = out["n"].astype(float)
    denom = n.replace(0, np.nan)
    out["observado"] = out["soma_obs"] / denom
    out["previsto"] = out[f"soma_prev_{variant}"] / denom
    out["mae"] = out[f"soma_abs_{variant}"] / denom
    out["vies"] = out["previsto"] - out["observado"]
    out["rmse_log"] = np.sqrt(out[f"soma_sqlog_{variant}"] / denom)
    out.loc[n < MIN_N, ["observado", "previsto", "mae", "vies", "rmse_log"]] = np.nan
    return out


def draw_map(geo, values_df, metric, allowed_ids, selected_id):
    values = dict(zip(values_df["territorio_id"].astype(str), values_df[metric]))
    numeric = [float(v) for v in values.values() if pd.notna(v) and np.isfinite(v)]
    fmap = folium.Map(location=[-15.7, -52.5], zoom_start=4, tiles="OpenStreetMap", control_scale=True)
    if not numeric:
        st.info("Não há células publicadas com cobertura suficiente para esta seleção.")
        return
    low, high = min(numeric), max(numeric)
    if low == high:
        low -= .5
        high += .5
    palette = linear.YlOrRd_09.scale(low, high)
    palette.caption = next((k for k,v in METRICS.items() if v == metric), metric)
    palette.add_to(fmap)
    ids_present = set(values)
    features = [f for f in geo["features"] if str(f.get("properties", {}).get("territorio_id", "")) in allowed_ids and str(f.get("properties", {}).get("territorio_id", "")) in ids_present]
    if not features:
        st.info("Não há polígonos para a combinação territorial selecionada.")
        return

    def style(feature):
        key = str(feature.get("properties", {}).get("territorio_id", ""))
        val = values.get(key)
        is_selected = bool(selected_id and key == selected_id)
        return {"color": "#17456f" if is_selected else "#666666", "weight": 3 if is_selected else .65,
                "fillOpacity": .84 if pd.notna(val) else .20,
                "fillColor": palette(float(val)) if pd.notna(val) else "#cccccc"}

    layer = folium.GeoJson(
        {"type":"FeatureCollection", "features":features}, style_function=style,
        highlight_function=lambda _: {"weight": 2.5, "color": "#222"},
        tooltip=folium.GeoJsonTooltip(fields=["territorio_nome"], aliases=["Território:"]),
    ).add_to(fmap)
    bounds = layer.get_bounds()
    if bounds and all(np.isfinite(v) for p in bounds for v in p):
        fmap.fit_bounds(bounds, padding=(12, 12))
    # Importação tardia: o componente JS de mapa não entra na tela inicial.
    from streamlit_folium import st_folium
    st_folium(fmap, height=490, use_container_width=True, returned_objects=[])


st.title("Remunerômetro · RAIS 2025")
st.caption("Dashboard público · avaliação territorial de dois modelos congelados · dados agregados do conjunto de teste")
missing_files = [str(p.relative_to(ROOT)) for p in (PARQUET, CATALOG) if not p.exists()]
if missing_files:
    st.error("Faltam arquivos no GitHub: " + ", ".join(missing_files))
    st.stop()
try:
    data, catalog = load_tables()
except Exception as error:
    st.exception(error)
    st.stop()

# Relação território–UF/tipologia obtida do catálogo, nunca inventada.

with st.sidebar:
    st.header("Filtros")
    selected_model = st.radio("Modelo", ["Famílias", "35 CBOs"], horizontal=True)
    variant = "familias" if selected_model == "Famílias" else "cbos"
    families = sorted(data["grupo_ocupacional"].dropna().unique().tolist())
    family = st.selectbox("Família profissional", ["Todas"] + families)
    cbos = sorted(data.loc[data["grupo_ocupacional"].eq(family), "cbo"].dropna().unique()) if family != "Todas" else sorted(data["cbo"].dropna().unique())
    cbo = st.selectbox("CBO (6 dígitos)", ["Todos"] + list(cbos))
    region = st.selectbox("Grande região", ["Todas"] + list(REGIONS))
    all_ufs = sorted(catalog["uf_sigla"].dropna().unique().tolist())
    ufs = [u for u in all_ufs if region == "Todas" or u in REGIONS[region]]
    uf = st.selectbox("UF", ["Todas"] + ufs)
    possible = catalog.copy()
    if region != "Todas":
        possible = possible[possible["uf_sigla"].isin(REGIONS[region])]
    if uf != "Todas":
        possible = possible[possible["uf_sigla"].eq(uf)]
    types = sorted(possible["tipologia_ibge"].dropna().unique().tolist())
    typology = st.selectbox("Tipologia IBGE", ["Todas"] + types)
    if typology != "Todas":
        possible = possible[possible["tipologia_ibge"].eq(typology)]
    use_locator = st.checkbox("Localizar município", value=False)
    options = {}
    municipality = "Todos"
    if use_locator:
        options = {f"{r.municipio_nome} · {r.uf_sigla} ({r.code_muni})": r.territorio_id
                   for r in possible[["municipio_nome", "uf_sigla", "code_muni", "territorio_id"]].dropna().itertuples(index=False)}
        municipality = st.selectbox("Município (localizador)", ["Todos"] + sorted(options))
    metric_name = st.selectbox("Indicador do mapa", list(METRICS))
    st.caption("O município apenas localiza um território agregado.")

if family != "Todas":
    data = data[data["grupo_ocupacional"].eq(family)]
if cbo != "Todos":
    data = data[data["cbo"].eq(cbo)]
allowed_ids = set(possible["territorio_id"].dropna().astype(str))
selected_id = str(options[municipality]) if municipality != "Todos" else None
if selected_id:
    allowed_ids = {selected_id}
filtered = data[data["territorio_id"].isin(allowed_ids)]

if municipality != "Todos":
    st.info(f"Município selecionado: **{municipality}**. Os números exibidos correspondem ao **território agregado** que o contém, e NÃO a uma estimativa municipal.")
if typology != "Todas" and possible["territorio_id"].isin(catalog.loc[catalog["tipologia_ibge"].ne(typology), "territorio_id"]).any():
    st.caption("Alguns territórios podem abranger mais de uma tipologia (por exemplo, agrupamentos metropolitanos); o filtro seleciona territórios que contêm municípios da tipologia desejada, não um recorte exato de vínculos por tipologia.")
st.caption("Supressão: células território × CBO com menos de 30 vínculos foram excluídas antes da publicação; totais podem ser inferiores aos do teste completo.")

summary = summarize(filtered, [], variant).iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vínculos publicados", f"{int(summary['n']):,}".replace(",", "."))
c2.metric("Remuneração observada", brl(summary["observado"]))
c3.metric("Remuneração prevista", brl(summary["previsto"]))
c4.metric("MAE", brl(summary["mae"]))

# IMPORTANTE: st.tabs executa todos os painéis mesmo quando não visíveis.
# st.radio permite executar somente o painel escolhido, reduzindo o tempo inicial.
page = st.radio(
    "Navegação", ["Visão geral", "Mapa e territórios", "Comparar modelos", "Localizar município"],
    index=0, horizontal=True, label_visibility="collapsed",
)
territory = summarize(filtered, ["territorio_id", "territorio_nome"], variant)

if page == "Visão geral":
    st.subheader("Territórios com maior número de vínculos publicados")
    ranked = territory.dropna(subset=["mae"]).sort_values("n", ascending=False).head(15)
    if ranked.empty:
        st.info("Não há áreas elegíveis para o gráfico.")
    else:
        fig = px.bar(
            ranked.sort_values("mae"), x="mae", y="territorio_nome", orientation="h",
            hover_data=["n", "observado", "previsto"],
            labels={"mae": "MAE (R$)", "territorio_nome": "Território"},
        )
        fig.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    st.subheader("Indicadores por território")
    st.dataframe(
        territory[["territorio_nome", "n", "observado", "previsto", "mae", "vies", "rmse_log"]]
        .rename(columns={"territorio_nome":"Território", "n":"Vínculos publicados", "observado":"Observado (R$)",
                         "previsto":"Previsto (R$)", "mae":"MAE (R$)", "vies":"Viés (R$)", "rmse_log":"RMSE (log)"})
        .sort_values("Vínculos publicados", ascending=False),
        hide_index=True, width="stretch",
    )

elif page == "Mapa e territórios":
    st.subheader("Cartograma de territórios agregados")
    st.caption("O mapa é carregado sob demanda para reduzir o tempo de abertura do dashboard.")
    if not MAP.exists():
        st.error(f"Arquivo cartográfico ausente: {MAP.name}")
    else:
        try:
            with st.spinner("Preparando a cartografia..."):
                geo = load_geojson()
                draw_map(geo, territory, METRICS[metric_name], allowed_ids, selected_id)
        except Exception as error:
            st.exception(error)

elif page == "Comparar modelos":
    st.subheader("Duas especificações, mesma seleção publicada")
    rows = []
    for variant_, label in [("familias", "Famílias"), ("cbos", "35 CBOs")]:
        v = summarize(filtered, [], variant_).iloc[0]
        rows.append({"Modelo":label, "Vínculos publicados":int(v["n"]), "MAE (R$)":v["mae"],
                     "RMSE (log)":v["rmse_log"], "Viés (R$)":v["vies"],
                     "Observado (R$)":v["observado"], "Previsto (R$)":v["previsto"]})
    comparison = pd.DataFrame(rows)
    st.dataframe(comparison, hide_index=True, width="stretch")
    if comparison["MAE (R$)"].notna().all():
        st.plotly_chart(px.bar(comparison, x="Modelo", y="MAE (R$)", title="MAE no recorte publicado"), width="stretch")
    st.caption("Métricas da amostra publicada; não representam obrigatoriamente o teste completo de 234.693 vínculos.")

elif page == "Localizar município":
    st.subheader("Localizador de municípios")
    st.write("Ative 'Localizar município' na barra lateral para selecionar uma cidade. Não há estatísticas municipais nesta base pública.")
    if municipality != "Todos":
        st.write("Território:", selected_id)
    st.dataframe(
        possible[["code_muni", "municipio_nome", "uf_sigla", "tipologia_ibge", "territorio_id"]]
        .rename(columns={"code_muni":"IBGE (6 dígitos)", "municipio_nome":"Município", "uf_sigla":"UF",
                         "tipologia_ibge":"Tipologia IBGE", "territorio_id":"Território agregado"}),
        hide_index=True, width="stretch",
    )

with st.expander("Metodologia e limitações"):
    st.markdown("""
- RAIS 2025: vínculos formais ativos em 31/12 e remuneração nominal positiva de dezembro.
- Dois modelos Lasso congelados: grupos profissionais e 35 CBOs; avaliações calculadas no conjunto de teste.
- Indicadores são **agregados de células território × CBO** com n ≥ 30; somas aditivas permitem recalcular MAE, RMSE e médias.
- Por desenho, a versão pública **não** contém valores individuais ou células municipais.
- Município é apenas um filtro **localizador**; previsões municipais, comparação exata por tipologia dentro de RM e simulação de novos perfis exigiriam outra base ou os pipelines.
- A seleção de 35 CBOs inclui aproximações de títulos de mercado (por exemplo BI, UX e engenharia de dados).
- `exp(log previsto)` não representa necessariamente o salário médio condicional em reais. Região refere-se à localização do estabelecimento, não à residência.
""")
