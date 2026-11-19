"""Dashboard interativo das despesas de viagem do BNDES (2009-2026).

Uso: streamlit run app.py   (a partir da raiz do repositório)
Lê a base tratada por src/etl.py; se ela não existir, roda o pipeline antes.
"""

import pandas as pd
import streamlit as st

from src import etl

st.set_page_config(page_title="Viagens do BNDES", page_icon="✈️", layout="wide")

REFERENCIA_PADRAO = {"2009-2019": "Nível Superior", "2020+": "DAS-1011 (Assessoramento)"}
SEM_CARGO = ["Não se aplica", "Código não documentado"]

# a base guarda os motivos sem acento (normalizados); aqui eles ganham a grafia correta para exibir
ROTULO_MOTIVO = {
    "ACOMPANHAMENTO DE PROJETO": "Acompanhamento de projeto",
    "REUNIAO EM ORGAOS GOVERNAMENTAIS": "Reunião em órgãos governamentais",
    "PARTICIPACAO EM CONGRESSOS, FEIRAS E SEMINARIOS": "Congressos, feiras e seminários",
    "FOMENTO": "Fomento",
    "TREINAMENTO NACIONAL": "Treinamento nacional",
    "ANALISE DE PROJETO": "Análise de projeto",
    "OUTROS": "Outros",
    "REUNIAO NOS ESCRITORIOS REGIONAIS": "Reunião nos escritórios regionais",
    "REPRESENTACAO EM COLEGIADOS": "Representação em colegiados",
    "AVALIACAO DE BENS": "Avaliação de bens",
    "PARTICIPACAO EM SEMINARIO PROMOVIDO PELO BANCO": "Seminário promovido pelo banco",
    "MEDIDA JUDICIAL": "Medida judicial",
    "PRE-ANALISE": "Pré-análise",
}


# ---------------- DADOS ----------------
@st.cache_data
def carregar():
    caminho = etl.PROCESSED_DIR / "viagens.csv.gz"
    if not caminho.exists():
        etl.executar_pipeline()
    df = etl.carregar_processado(caminho)
    df["profissao"] = df["profissao"].fillna("Não identificada")
    df["motivo_exibicao"] = df["motivo_principal"].map(lambda m: ROTULO_MOTIVO.get(m, m.capitalize()))
    return df


def reais(valor: float) -> str:
    """R$ no padrão brasileiro, abreviando milhões."""
    if abs(valor) >= 1e6:
        return f"R$ {valor / 1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor:,.0f}".replace(",", ".")


def numero(valor: float, casas: int = 0) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def plural(valor: float, singular: str, plural_: str) -> str:
    """Em português, valores abaixo de 2 pedem singular: '1,18 viagem', '1,5 vez'."""
    return singular if abs(valor) < 2 else plural_


df = carregar()

# ---------------- FILTROS ----------------
st.sidebar.title("Filtros")

ano_min, ano_max = int(df["ano"].min()), int(df["ano"].max())
anos = st.sidebar.slider("Período", ano_min, ano_max, (ano_min, ano_max))

motivos_top = df["motivo_exibicao"].value_counts().index[:12].tolist()
motivos = st.sidebar.multiselect("Motivos (vazio = todos)", motivos_top, placeholder="Todos os motivos")

profissoes_top = df.loc[df["profissao"] != "Não identificada", "profissao"].value_counts().index[:10].tolist()
profissoes = st.sidebar.multiselect("Profissões (vazio = todas)", profissoes_top, placeholder="Todas as profissões")

escopo = st.sidebar.radio("Destino", ["Todos", "Só nacionais", "Só internacionais"], horizontal=False)

tipo_valor = st.sidebar.radio(
    "Valores", ["Reais (corrigidos pelo IPCA)", "Nominais"],
    help="Reais = levados a preços do último mês com IPCA publicado; nominais = como registrados.",
)
COL_VALOR = "valor_total_real" if tipo_valor.startswith("Reais") else "valor_total"

# filtros comuns (sem o ano), reaproveitados na aba da pandemia, que compara todos os anos com 2019
filtro_base = pd.Series(True, index=df.index)
if motivos:
    filtro_base &= df["motivo_exibicao"].isin(motivos)
if profissoes:
    filtro_base &= df["profissao"].isin(profissoes)
if escopo == "Só nacionais":
    filtro_base &= ~df["internacional"]
elif escopo == "Só internacionais":
    filtro_base &= df["internacional"]
d = df[filtro_base & df["ano"].between(*anos)]

st.sidebar.caption(f"{numero(len(d))} de {numero(len(df))} viagens")
st.sidebar.caption("Fonte: Portal de Dados Abertos do BNDES (ODbL 1.0) e IPCA/BCB.")

# ---------------- CABEÇALHO ----------------
st.title("Despesas de viagem do BNDES (2009–2026)")
st.markdown(
    "Quem viaja, quem gasta e o efeito da pandemia de COVID-19.  \n"
    "**Giovanna Poggi e Juliana Neto** · Linguagem de Programação (Análise e Visualização de Dados com Python) · "
    "Prof. Alexandre Neves Louzada · 2026.2"
)

if d.empty:
    st.warning("Nenhuma viagem com esses filtros. Tente ampliar o período ou limpar algum filtro.")
    st.stop()

pessoas = d["pessoa_id"].nunique()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Viagens", numero(len(d)))
c2.metric("Pessoas que viajaram", numero(pessoas))
c3.metric("Gasto total", reais(d[COL_VALOR].sum()))
c4.metric("Custo mediano de 1 viagem", reais(d[COL_VALOR].median()))
c5.metric("Viagens por pessoa", numero(len(d) / pessoas, 1))

if anos[0] <= 2019 < 2020 <= anos[1]:
    st.info(
        "O período escolhido atravessa 2020, quando o BNDES mudou o formato do registro: os códigos de cargo mudam "
        "e o total passa a incluir itens não detalhados. Compare custos entre os dois períodos com cautela.",
        icon="ℹ️",
    )

abas = st.tabs(["Visão geral", "Profissões", "Cargos", "Áreas da liderança", "Motivos", "Pandemia", "Dados"])

# ---------------- VISÃO GERAL ----------------
with abas[0]:
    st.subheader("Viagens por mês")
    mensal = d.groupby("mes").size().rename("viagens")
    mensal = mensal.reindex(pd.date_range(mensal.index.min(), mensal.index.max(), freq="MS"), fill_value=0)
    st.line_chart(mensal, y_label="Viagens iniciadas no mês")
    st.caption("A queda de 2020 é a pandemia: entre abril e junho de 2020 não há nenhuma viagem registrada.")

    st.subheader("Gasto por ano")
    anual = d.groupby("ano")[COL_VALOR].sum().rename("gasto") / 1e6
    st.bar_chart(anual, y_label="R$ milhões", color="#1e3a8a")

    st.subheader("Concentração do gasto")
    gasto_pessoa = d.groupby("pessoa_id")[COL_VALOR].sum().sort_values(ascending=False)
    top10 = gasto_pessoa.head(max(1, int(len(gasto_pessoa) * 0.1))).sum() / gasto_pessoa.sum()
    st.markdown(
        f"Os **10% que mais gastam** respondem por **{top10:.0%}** do gasto da seleção "
        f"({numero(len(gasto_pessoa))} pessoas)."
    )

# ---------------- PROFISSÕES ----------------
with abas[1]:
    st.subheader("Quem viaja e quem gasta, por profissão")
    st.caption(
        "Profissão vem da base atual de empregados (cruzamento pelo nome); quem já saiu do banco aparece como "
        "'Não identificada'."
    )
    prof = d[d["profissao"] != "Não identificada"].groupby("profissao").agg(
        viagens=("codigoviagem", "size"),
        pessoas=("pessoa_id", "nunique"),
        gasto=(COL_VALOR, "sum"),
        custo_mediano=(COL_VALOR, "median"),
    )
    prof = prof[prof["pessoas"] >= 5]
    if prof.empty:
        st.info("Nenhuma profissão identificada com 5 ou mais viajantes nesta seleção.")
    else:
        prof["viagens_por_pessoa"] = prof["viagens"] / prof["pessoas"]
        prof["gasto_por_pessoa"] = prof["gasto"] / prof["pessoas"]
        medida = st.radio(
            "Ordenar e mostrar por", ["viagens", "viagens_por_pessoa", "gasto", "gasto_por_pessoa"], horizontal=True,
            format_func=lambda m: {"viagens": "Viagens", "viagens_por_pessoa": "Viagens por pessoa",
                                   "gasto": "Gasto total", "gasto_por_pessoa": "Gasto por pessoa"}[m],
        )
        top = prof.sort_values(medida, ascending=False).head(10)
        st.bar_chart(top[medida], horizontal=True, color="#3b82f6", sort=f"-{medida}")
        st.dataframe(
            top.style.format({"gasto": reais, "gasto_por_pessoa": reais, "custo_mediano": reais,
                              "viagens_por_pessoa": "{:.1f}"}),
            width="stretch",
        )

# ---------------- CARGOS ----------------
with abas[2]:
    st.subheader("Uma viagem e uma pessoa, por cargo")
    st.markdown(
        "O total por cargo depende de quantas pessoas ocupam o cargo. Aqui a comparação é de igual para igual: "
        "quanto custa **uma viagem** e quanto gasta **uma pessoa** de cada cargo, em múltiplos de um cargo de referência."
    )
    formatos_disponiveis = sorted(d["formato_registro"].unique())
    formato = st.radio(
        "Período de registro (os códigos de cargo mudam em 2020)", formatos_disponiveis, horizontal=True,
        index=len(formatos_disponiveis) - 1,
    )
    base = d[(d["formato_registro"] == formato) & (d[COL_VALOR] > 0) & ~d["cargo"].isin(SEM_CARGO)]
    cargos = base.groupby("cargo").agg(
        viagens=("codigoviagem", "size"),
        pessoas=("pessoa_id", "nunique"),
        gasto=(COL_VALOR, "sum"),
        custo_medio=(COL_VALOR, "mean"),
        custo_mediano=(COL_VALOR, "median"),
    )
    cargos = cargos[cargos["viagens"] >= 30]
    if cargos.empty:
        st.info("Poucas viagens por cargo nesta seleção. Amplie o período ou limpe os filtros.")
    else:
        cargos["viagens_por_pessoa"] = cargos["viagens"] / cargos["pessoas"]
        cargos["gasto_por_pessoa"] = cargos["gasto"] / cargos["pessoas"]

        opcoes = cargos.sort_values("viagens", ascending=False).index.tolist()
        padrao = REFERENCIA_PADRAO.get(formato)
        ref = st.selectbox("Cargo de referência", opcoes, index=opcoes.index(padrao) if padrao in opcoes else 0)
        estatistica = st.radio("Custo de uma viagem pela", ["média", "mediana"], horizontal=True,
                               help="A média é puxada por viagens muito caras (ex.: internacionais); a mediana mostra a viagem típica.")
        col_custo = "custo_medio" if estatistica == "média" else "custo_mediano"

        cargos["1_viagem_equivale_a"] = cargos[col_custo] / cargos.loc[ref, col_custo]
        cargos["1_pessoa_equivale_a"] = cargos["gasto_por_pessoa"] / cargos.loc[ref, "gasto_por_pessoa"]
        cargos = cargos.sort_values(col_custo, ascending=False)

        comparar = st.selectbox("Comparar com a referência", [c for c in opcoes if c != ref] or opcoes)
        x, r = cargos.loc[comparar], cargos.loc[ref]
        st.success(
            f"Uma viagem de **{comparar}** custa {reais(x[col_custo])} ({estatistica}) e equivale a "
            f"**{numero(x['1_viagem_equivale_a'], 2)} {plural(x['1_viagem_equivale_a'], 'viagem', 'viagens')}** de {ref} ({reais(r[col_custo])}). "
            f"Cada pessoa de {comparar} fez {numero(x['viagens_por_pessoa'], 1)} viagens e gastou {reais(x['gasto_por_pessoa'])}, "
            f"**{numero(x['1_pessoa_equivale_a'], 1)} {plural(x['1_pessoa_equivale_a'], 'vez', 'vezes')}** o gasto de uma pessoa de {ref}."
        )

        g1, g2 = st.columns(2)
        with g1:
            st.markdown(f"**Custo de uma viagem ({estatistica})**")
            st.bar_chart(cargos[col_custo], horizontal=True, color="#1e3a8a", sort=f"-{col_custo}", x_label="R$ por viagem")
        with g2:
            st.markdown("**Gasto de uma pessoa no período**")
            st.bar_chart(cargos["gasto_por_pessoa"], horizontal=True, color="#ea580c", sort="-gasto_por_pessoa", x_label="R$ por pessoa")

        st.dataframe(
            cargos[["viagens", "pessoas", col_custo, "1_viagem_equivale_a", "viagens_por_pessoa", "gasto_por_pessoa",
                    "1_pessoa_equivale_a"]].style.format({
                col_custo: reais, "gasto_por_pessoa": reais, "1_viagem_equivale_a": "{:.2f}×",
                "viagens_por_pessoa": "{:.1f}", "1_pessoa_equivale_a": "{:.1f}×",
            }),
            width="stretch",
        )
        st.caption("Cargos com 30 ou mais viagens na seleção; viagens de valor zero excluídas. "
                   "Quem mudou de cargo no período conta em cada cargo que ocupou.")

# ---------------- ÁREAS ----------------
with abas[3]:
    st.subheader("Áreas da liderança (organograma)")
    st.caption(
        "O BNDES só publica a lotação dos 34 dirigentes atuais (diretores e superintendentes), cujas viagens são "
        "cerca de 4% do total. O portal informa apenas a sigla da área."
    )
    area = d.dropna(subset=["area_sigla"]).groupby(["area_sigla", "funcao_dirigente"]).agg(
        viagens=("codigoviagem", "size"), gasto=(COL_VALOR, "sum"), custo_mediano=(COL_VALOR, "median"),
    ).reset_index()
    if area.empty:
        st.info("Nenhuma viagem de dirigente nesta seleção.")
    else:
        area = area.sort_values("viagens", ascending=False)
        st.bar_chart(area.set_index("area_sigla")["viagens"].head(15), horizontal=True, color="#3b82f6", sort="-viagens")
        st.dataframe(
            area.rename(columns={"area_sigla": "área", "funcao_dirigente": "função"})
                .style.format({"gasto": reais, "custo_mediano": reais}),
            hide_index=True, width="stretch",
        )

# ---------------- MOTIVOS ----------------
with abas[4]:
    st.subheader("Para que se viaja")
    mot = d.groupby("motivo_exibicao").agg(viagens=("codigoviagem", "size"), gasto=(COL_VALOR, "sum"),
                                           custo_mediano=(COL_VALOR, "median"))
    mot = mot.sort_values("viagens", ascending=False)
    mot["% das viagens"] = mot["viagens"] / mot["viagens"].sum() * 100
    mot.index.name = "Motivo"
    st.bar_chart(mot["viagens"].head(12), horizontal=True, color="#1e3a8a", sort="-viagens")
    st.dataframe(mot.head(20).style.format({"gasto": reais, "custo_mediano": reais, "% das viagens": "{:.1f}%"}),
                 width="stretch")
    st.caption("Motivo principal = primeiro motivo listado; 'Treinamento centralizado' (até 2019) e "
               "'Treinamento no Brasil' (2020+) foram unificados como 'Treinamento nacional'.")

# ---------------- PANDEMIA ----------------
with abas[5]:
    st.subheader("Antes, durante e depois da pandemia")
    st.caption("Esta aba usa todos os anos (ignora o filtro de período) para comparar com 2019; os outros filtros valem.")
    p = df[filtro_base]

    por_ano = p[p["ano"].between(2016, 2025)].groupby("ano").agg(
        viagens=("codigoviagem", "size"), pessoas=("pessoa_id", "nunique"),
        gasto=(COL_VALOR, "sum"), custo_mediano=(COL_VALOR, "median"),
    )
    if 2019 in por_ano.index and por_ano.loc[2019, "viagens"] > 0:
        por_ano["viagens_vs_2019_%"] = (por_ano["viagens"] / por_ano.loc[2019, "viagens"] - 1) * 100
        b2020, b2021, b2025 = (por_ano["viagens_vs_2019_%"].get(a) for a in (2020, 2021, 2025))
        m1, m2, m3 = st.columns(3)
        if b2020 is not None:
            m1.metric("2020 vs 2019", f"{numero(b2020, 0)}%")
        if b2021 is not None:
            m2.metric("2021 vs 2019", f"{numero(b2021, 0)}%")
        if b2025 is not None:
            m3.metric("2025 vs 2019", f"{numero(b2025, 0)}%")
    st.bar_chart(por_ano["viagens"], y_label="Viagens no ano", color="#ea580c")
    tabela_ano = por_ano.rename(columns={"viagens": "Viagens", "pessoas": "Pessoas", "gasto": "Gasto",
                                         "custo_mediano": "Custo mediano", "viagens_vs_2019_%": "Viagens vs 2019"})
    tabela_ano.index.name = "Ano"
    st.dataframe(
        tabela_ano.style.format({
            "Viagens": numero, "Pessoas": numero, "Gasto": reais, "Custo mediano": reais,
            "Viagens vs 2019": lambda v: ("+" if v > 0 else "") + numero(v, 1) + "%",
        }),
        width="stretch",
    )

    st.markdown("**Motivos: viagens em 2019, na média anual de 2020–21 e em 2023**")
    janela = p[p["ano"].isin([2019, 2020, 2021, 2023])].copy()
    janela["janela"] = janela["ano"].map({2019: "2019", 2020: "2020–21", 2021: "2020–21", 2023: "2023"})
    tab = pd.crosstab(janela["motivo_exibicao"], janela["janela"])
    if not tab.empty and "2019" in tab:
        if "2020–21" in tab:
            tab["2020–21"] = tab["2020–21"] / 2
        tab = tab.loc[tab["2019"].sort_values(ascending=False).index[:10]]
        # tabela em vez de gráfico agrupado: dá para ler os três valores lado a lado e a variação de cada motivo
        if "2020–21" in tab:
            tab["queda na pandemia"] = (tab["2020–21"] / tab["2019"] - 1) * 100
        if "2023" in tab:
            tab["2023 vs 2019"] = (tab["2023"] / tab["2019"] - 1) * 100
        pct = lambda v: ("+" if v > 0 else "") + numero(v, 0) + "%"
        tab.index.name = "Motivo"
        tab.columns.name = None
        st.dataframe(
            tab.style.format({"2019": numero, "2020–21": numero, "2023": numero,
                              "queda na pandemia": pct, "2023 vs 2019": pct})
                     .bar(subset=[c for c in ["queda na pandemia", "2023 vs 2019"] if c in tab], align="zero",
                          color=["#fdba74", "#93c5fd"]),
            width="stretch",
        )

    st.caption("Custos depois de 2020 são afetados pela mudança no formato de registro, além da pandemia.")

# ---------------- DADOS ----------------
with abas[6]:
    st.subheader("Base tratada (filtrada)")
    colunas = ["codigoviagem", "data_partida", "ano", "cargo", "profissao", "area_sigla", "motivo_principal",
               "internacional", "n_trechos", "n_diarias", "valor_total", "valor_total_real", "outlier_valor"]
    st.dataframe(d[colunas], hide_index=True, width="stretch")
    st.download_button("Baixar CSV filtrado", d[colunas].to_csv(index=False).encode("utf-8"),
                       file_name="viagens_bndes_filtrado.csv", mime="text/csv")
    st.caption("Nomes e CPFs não são publicados: cada pessoa aparece só por um pseudônimo (pessoa_id) na base completa.")

st.divider()
st.caption("Código, dados e artigo: github.com/mochilicius/g2lingprog · código MIT · dados ODbL 1.0 · texto CC BY 4.0")
