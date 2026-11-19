"""Dashboard interativo das despesas de viagem do BNDES (2009-2026).

Uso: streamlit run app.py   (a partir da raiz do repositório)
Lê a base tratada por src/etl.py; se ela não existir, roda o pipeline antes.
"""

import pandas as pd
import streamlit as st

from src import etl

st.set_page_config(page_title="Viagens do BNDES", page_icon="🎀", layout="wide")

# paleta kawaii usada nos gráficos (a mesma do .streamlit/config.toml)
ROSA, LILAS, MENTA, PESSEGO, CINZA_ROSADO = "#ff8fc3", "#b48cf0", "#7fd8c0", "#ffb38a", "#d9c2d6"

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
    "INTERNACIONAL SERVICO GVIG": "Viagem internacional a serviço",
    "INTERNACIONAL TREINAMENTO GVIG": "Treinamento internacional",
}


# ---------------- DADOS ----------------
CAMINHO_DADOS = etl.PROCESSED_DIR / "viagens.csv.gz"


def versao_dos_dados() -> str:
    """Identifica a versão do arquivo tratado: quando ele muda (novo deploy), o cache abaixo é refeito."""
    if not CAMINHO_DADOS.exists():
        return "ausente"
    info = CAMINHO_DADOS.stat()
    return f"{info.st_size}-{info.st_mtime_ns}"


@st.cache_data
def carregar(versao: str):  # 'versao' entra na chave do cache: sem ela, um deploy novo reaproveitaria a tabela antiga
    if not CAMINHO_DADOS.exists():
        etl.executar_pipeline()
    df = etl.carregar_processado(CAMINHO_DADOS)
    # área e diretoria vêm do mapeamento manual do etl; recalcular aqui garante as colunas mesmo numa base antiga
    df["area_nome"] = df["area_sigla"].map(lambda s: etl.AREAS[s][0] if s in etl.AREAS else None)
    df["diretoria"] = df["area_sigla"].map(lambda s: etl.DIRETORIAS[etl.AREAS[s][1]] if s in etl.AREAS else None)
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
    return singular if abs(round(valor, 2)) < 2 else plural_  # decide pelo número que aparece na tela


df = carregar(versao_dos_dados())

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
# acabamento que o tema do config.toml não cobre: fundo de bolinhas, cartões dos KPIs e abas em pílula
st.markdown("""
<style>
  @import url("https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;700;800&display=swap");
  .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp h1, .stApp h2, .stApp h3,
  .stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"], .stApp [data-baseweb="tab"],
  .stApp [data-baseweb="select"] div, .kawaii-topo, .kawaii-topo * {
    font-family: "M PLUS Rounded 1c", sans-serif !important;
  }
  .stApp {
    background-image: radial-gradient(#ffe3f0 2.5px, transparent 2.5px), radial-gradient(#f1e8ff 2.5px, transparent 2.5px);
    background-size: 36px 36px; background-position: 0 0, 18px 18px;
  }
  .kawaii-topo {
    position: relative; overflow: hidden; text-align: center; border-radius: 32px; padding: 26px 20px 30px;
    background: linear-gradient(135deg, #ffd1e6 0%, #e8d9ff 55%, #d6f5ec 100%);
    border: 3px solid #fff; box-shadow: 0 8px 0 #ffe3f0; margin-bottom: 18px;
  }
  .kawaii-topo h1 { color: #5b2a63; margin: 6px 0 4px; padding: 0; font-size: clamp(1.7rem, 4vw, 2.6rem); }
  .kawaii-topo p { color: #6d4a72; margin: 2px 0; }
  .kawaii-topo .etiqueta {
    display: inline-block; background: #fff; color: #e94f9a; border: 2px dashed #ff8fc3; border-radius: 999px;
    padding: 2px 14px; font-size: .78rem; font-weight: 800; letter-spacing: 1.5px;
  }
  .kawaii-topo svg.mascote { width: 120px; height: auto; animation: voa 3.4s ease-in-out infinite; }
  .kawaii-topo .brilho { position: absolute; animation: pisca 2.4s ease-in-out infinite; }
  @keyframes voa { 50% { transform: translateY(-7px) rotate(-4deg); } }
  @keyframes pisca { 50% { transform: scale(.7); opacity: .5; } }
  @media (prefers-reduced-motion: reduce) { .kawaii-topo svg.mascote, .kawaii-topo .brilho { animation: none; } }
  [data-testid="stMetric"] {
    background: #fff; border: 3px solid #ffe3f0; border-radius: 24px; padding: 12px 14px;
    box-shadow: 0 6px 0 rgba(233, 79, 154, .15);
  }
  [data-testid="stMetricValue"] { color: #5b2a63; }
  h3::after { content: " ♡"; color: #ff8fc3; }
  [data-testid="stSidebar"] h1::before { content: "🎀 "; }
</style>
""", unsafe_allow_html=True)

MASCOTE = """
<svg class="mascote" viewBox="0 0 160 110" role="img" aria-label="Aviãozinho sorridente com um laço, mascote do dashboard">
  <path d="M20 58 Q16 40 34 40 L112 40 Q146 40 150 58 Q146 76 112 76 L34 76 Q16 76 20 58 Z" fill="#fff" stroke="#e94f9a" stroke-width="4"/>
  <path d="M30 40 L18 16 Q16 10 24 12 L52 40 Z" fill="#c7a8f5" stroke="#8e6ad8" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M70 72 L54 102 Q52 108 60 106 L96 72 Z" fill="#ff8fc3" stroke="#e94f9a" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M70 44 L60 22 Q58 16 66 18 L92 44 Z" fill="#ff8fc3" stroke="#e94f9a" stroke-width="3.5" stroke-linejoin="round"/>
  <circle cx="118" cy="54" r="5" fill="#4a2d4f"/><circle cx="136" cy="54" r="5" fill="#4a2d4f"/>
  <circle cx="119.6" cy="52.2" r="1.7" fill="#fff"/><circle cx="137.6" cy="52.2" r="1.7" fill="#fff"/>
  <ellipse cx="111" cy="64" rx="6" ry="3.8" fill="#ff9fc9" opacity=".85"/><ellipse cx="143" cy="64" rx="5" ry="3.5" fill="#ff9fc9" opacity=".85"/>
  <path d="M122 63 Q127 68 132 63" fill="none" stroke="#4a2d4f" stroke-width="2.8" stroke-linecap="round"/>
  <circle cx="58" cy="58" r="6" fill="#bfe3ff" stroke="#6aa8e8" stroke-width="2.5"/><circle cx="80" cy="58" r="6" fill="#bfe3ff" stroke="#6aa8e8" stroke-width="2.5"/>
  <g transform="translate(126 34) rotate(18)">
    <path d="M0 0 L-13 -8 Q-16 0 -13 8 Z" fill="#ff8fc3" stroke="#e94f9a" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M0 0 L13 -8 Q16 0 13 8 Z" fill="#ff8fc3" stroke="#e94f9a" stroke-width="2.5" stroke-linejoin="round"/>
    <circle r="3.8" fill="#e94f9a"/>
  </g>
</svg>"""


def brilho(svg_path, cor, estilo):
    return f'<svg class="brilho" style="{estilo}" viewBox="0 0 40 40" aria-hidden="true"><path d="{svg_path}" fill="{cor}"/></svg>'


ESTRELA = "M20 2 C22 14 26 18 38 20 C26 22 22 26 20 38 C18 26 14 22 2 20 C14 18 18 14 20 2 Z"
CORACAO = "M20 36 C6 26 2 18 2 12 a9 9 0 0 1 18 -2 a9 9 0 0 1 18 2 C38 18 34 26 20 36 Z"
enfeites = (
    brilho(ESTRELA, "#fff", "top:18px;left:7%;width:30px;")
    + brilho(CORACAO, "#ff8fc3", "top:26px;right:9%;width:26px;animation-delay:.6s;")
    + brilho(ESTRELA, "#c7a8f5", "bottom:20px;left:14%;width:22px;animation-delay:1.1s;")
    + brilho(CORACAO, "#c7a8f5", "bottom:24px;right:16%;width:20px;animation-delay:1.6s;")
)

# ---------------- TEMAS SECRETOS ----------------
# Os botões com o nome das autoras (logo abaixo do cabeçalho) trocam o tema. O clique roda o callback antes
# do rerun, então aqui o tema escolhido já está no session_state.
if "tema" not in st.session_state:
    st.session_state.tema = None


def alternar_tema(tema):
    st.session_state.tema = None if st.session_state.tema == tema else tema


TEMA = st.session_state.tema

# desenhos originais em SVG
CEREJA = """<svg viewBox="0 0 64 64"><path d="M30 6c-2 10-8 20-16 28M30 6c4 12 10 20 18 26" fill="none" stroke="#3f8f52" stroke-width="3.5" stroke-linecap="round"/><path d="M30 6c8-6 20-4 24 4-9 3-17 1-24-4z" fill="#7fd08a" stroke="#3f8f52" stroke-width="2.5"/><circle cx="16" cy="44" r="13" fill="#e8336d" stroke="#8e1840" stroke-width="3"/><circle cx="46" cy="42" r="13" fill="#e8336d" stroke="#8e1840" stroke-width="3"/><ellipse cx="11" cy="39" rx="3.5" ry="2.5" fill="#fff" opacity=".75"/><ellipse cx="41" cy="37" rx="3.5" ry="2.5" fill="#fff" opacity=".75"/><circle cx="13" cy="46" r="1.6" fill="#4a1026"/><circle cx="20" cy="46" r="1.6" fill="#4a1026"/><circle cx="43" cy="44" r="1.6" fill="#4a1026"/><circle cx="50" cy="44" r="1.6" fill="#4a1026"/></svg>"""
MORCEGO = """<svg viewBox="0 0 80 40"><path d="M40 14c-3-5-8-6-8-6s1 5 3 7c-6-4-14-10-30-8 6 3 8 8 8 13 4-3 9-3 12 0 1-3 5-4 7-2 2 3 5 5 8 5s6-2 8-5c2-2 6-1 7 2 3-3 8-3 12 0 0-5 2-10 8-13-16-2-24 4-30 8 2-2 3-7 3-7s-5 1-8 6z" fill="#120a1c"/><circle cx="36" cy="18" r="1.8" fill="#ff7ac6"/><circle cx="44" cy="18" r="1.8" fill="#ff7ac6"/></svg>"""
COELHO = """<svg viewBox="0 0 64 72"><path d="M20 30C14 14 16 2 22 2s9 12 8 26M44 30c6-16 4-28-2-28s-9 12-8 26" fill="#fff" stroke="#e8508f" stroke-width="3"/><ellipse cx="32" cy="46" rx="24" ry="21" fill="#fff" stroke="#e8508f" stroke-width="3"/><ellipse cx="23" cy="45" rx="3.5" ry="4.5" fill="#5a2a45"/><ellipse cx="41" cy="45" rx="3.5" ry="4.5" fill="#5a2a45"/><ellipse cx="16" cy="53" rx="5" ry="3" fill="#ffb3d1"/><ellipse cx="48" cy="53" rx="5" ry="3" fill="#ffb3d1"/><path d="M29 52q3 3 6 0" stroke="#5a2a45" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>"""
MORANGO = """<svg viewBox="0 0 48 56"><path d="M24 14C10 14 4 22 6 32c2 12 12 21 18 22 6-1 16-10 18-22 2-10-4-18-18-18z" fill="#ff6f9f" stroke="#c23d6c" stroke-width="2.5"/><path d="M24 16c-4-6-12-6-14-3 5 0 7 3 8 5-5-1-9 1-10 4 7-2 12-2 16-2 4 0 9 0 16 2-1-3-5-5-10-4 1-2 3-5 8-5-2-3-10-3-14 3z" fill="#7fd08a" stroke="#3f8f52" stroke-width="2"/><g fill="#ffe9a8"><ellipse cx="17" cy="28" rx="1.5" ry="2"/><ellipse cx="27" cy="26" rx="1.5" ry="2"/><ellipse cx="33" cy="33" rx="1.5" ry="2"/><ellipse cx="20" cy="37" rx="1.5" ry="2"/></g></svg>"""
FLOR = """<svg viewBox="0 0 48 48"><g fill="#fff" stroke="#ff9cc2" stroke-width="2.5"><circle cx="24" cy="11" r="9"/><circle cx="37" cy="21" r="9"/><circle cx="32" cy="36" r="9"/><circle cx="16" cy="36" r="9"/><circle cx="11" cy="21" r="9"/></g><circle cx="24" cy="25" r="7" fill="#ffd36e" stroke="#e8a83a" stroke-width="2"/></svg>"""
CORACAO_SVG = lambda cor: f'<svg viewBox="0 0 40 36"><path d="M20 34C6 24 2 17 2 11a9 9 0 0 1 18-3 9 9 0 0 1 18 3c0 6-4 13-18 23z" fill="{cor}"/></svg>'

ENFEITES_TEMA = {
    "gotico": [(CEREJA, "top:14%;left:1.5%;width:52px"), (MORCEGO, "top:30%;right:1.5%;width:76px;animation-delay:-2s"),
               (CORACAO_SVG("#ff7ac6"), "top:52%;left:1.2%;width:26px;animation-delay:-1s"),
               (CEREJA, "bottom:12%;right:1.5%;width:48px;animation-delay:-4s"), (MORCEGO, "bottom:28%;left:1.2%;width:62px;animation-delay:-3s"),
               (CORACAO_SVG("#b08cff"), "top:72%;right:2%;width:22px;animation-delay:-2s")],
    "rosa": [(COELHO, "top:14%;left:1.5%;width:52px"), (MORANGO, "top:30%;right:1.5%;width:40px;animation-delay:-2s"),
             (FLOR, "top:52%;left:1.2%;width:34px;animation-delay:-1s"), (COELHO, "bottom:12%;right:1.5%;width:48px;animation-delay:-4s"),
             (MORANGO, "bottom:28%;left:1.2%;width:36px;animation-delay:-3s"), (CORACAO_SVG("#ff9cc2"), "top:72%;right:2%;width:24px;animation-delay:-2s")],
}
CARTINHA = {
    "gotico": ("https://www.sanrio.co.jp/wp-content/uploads/2022/06/gallery-kuromi1.png", "Kuromi", "🦇 tema da Giovanna",
               "Kuromi, personagem da Sanrio, piscando o olho ao lado de um bichinho de pelúcia, em fundo preto com estrelas"),
    "rosa": ("https://www.sanrio.co.jp/wp-content/uploads/2022/06/gallery-mymelody1.png", "My Melody", "🍓 tema da Juliana",
             "My Melody, personagem da Sanrio, dançando balé numa moldura de rosas em fundo rosa"),
}

CSS_TEMA = {
    "gotico": """
  .stApp { background-color: #1c1129 !important;
    background-image: radial-gradient(#3a2252 2.5px, transparent 2.5px), radial-gradient(#2e1a42 2.5px, transparent 2.5px) !important; }
  [data-testid="stSidebar"] { background: #2a1638 !important; }
  [data-testid="stSidebar"] h1, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #f2e6ff !important; }
  [data-testid="stSidebar"] [data-baseweb="select"] p, [data-testid="stSidebar"] [data-baseweb="select"] span { color: #4a2d4f !important; }
  .kawaii-topo { background: linear-gradient(135deg, #2b173f 0%, #4b2370 55%, #8a3a8f 100%) !important; box-shadow: 0 8px 0 #120a1c !important; }
  .kawaii-topo h1, .kawaii-topo p { color: #fbefff !important; }
  .kawaii-topo .etiqueta { background: #2a1638 !important; color: #ff9fd4 !important; }
  .cartinha-st { background: #2a1638 !important; } .cartinha-st figcaption { color: #e7d4f7 !important; }
""",
    "rosa": """
  .stApp { background-color: #fff0f6 !important;
    background-image: radial-gradient(#ffd3e4 2.5px, transparent 2.5px), radial-gradient(#ffe6ef 2.5px, transparent 2.5px) !important; }
  [data-testid="stSidebar"] { background: #ffe3ef !important; }
  .kawaii-topo { background: linear-gradient(135deg, #ffd6e7 0%, #ffb3d1 50%, #ffe3ec 100%) !important; box-shadow: 0 8px 0 #ffc4dc !important; }
""",
}

if TEMA:
    decor = "".join(f'<div class="enfeite-st" style="{estilo}">{svg}</div>' for svg, estilo in ENFEITES_TEMA[TEMA])
    st.markdown(f"""
<style>
  {CSS_TEMA[TEMA]}
  [data-testid="stHeader"] {{ background: transparent !important; }}
  /* o conteúdo vira um painel claro: gráficos e tabelas do Streamlit não mudam de cor com o tema */
  .block-container {{ position: relative; z-index: 1; background: rgba(255, 250, 253, .97); border-radius: 32px;
    padding: 2rem 2.2rem 3rem !important; margin-top: 3.2rem; margin-bottom: 2rem; box-shadow: 0 20px 60px rgba(30, 10, 50, .25); }}
  .enfeite-st {{ position: fixed; z-index: 0; pointer-events: none; animation: flutua-st 7s ease-in-out infinite; }}
  .enfeite-st svg {{ width: 100%; height: auto; display: block; }}
  @keyframes flutua-st {{ 50% {{ transform: translateY(-14px) rotate(6deg); }} }}
  @media (prefers-reduced-motion: reduce) {{ .enfeite-st {{ animation: none; }} }}
  @media (max-width: 760px) {{ .enfeite-st {{ display: none; }} .block-container {{ padding: 1.2rem .9rem 2rem !important; border-radius: 22px; }} }}
</style>
<div aria-hidden="true">{decor}</div>
""", unsafe_allow_html=True)

cartinha_html = ""
if TEMA:
    url, nome, legenda, alt = CARTINHA[TEMA]
    cartinha_html = f"""<figure class="cartinha-st"><img src="{url}" alt="{alt}" referrerpolicy="no-referrer">
    <figcaption><strong>{nome}</strong> {legenda}<br>© Sanrio · imagem de sanrio.co.jp</figcaption></figure>"""

st.markdown(f"""
<style>
  .cartinha-st {{ position: absolute; right: 22px; bottom: 18px; width: 128px; margin: 0; padding: 7px 7px 5px; background: #fff;
    border-radius: 14px; box-shadow: 0 14px 30px rgba(40, 10, 60, .28); transform: rotate(5deg); animation: chega-st .6s cubic-bezier(.2, 1.4, .5, 1); }}
  .cartinha-st img {{ display: block; width: 100%; height: auto; border-radius: 9px; }}
  .cartinha-st figcaption {{ margin-top: 3px; font-size: .62rem; line-height: 1.25; color: #6b5a78; text-align: center; }}
  @keyframes chega-st {{ from {{ opacity: 0; transform: translateY(20px) rotate(-6deg) scale(.85); }} }}
  .kawaii-topo:has(.cartinha-st) {{ padding-left: 165px; padding-right: 165px; }}
  @media (max-width: 760px) {{
    .cartinha-st {{ position: static; margin: 14px auto 0; transform: none; }}
    .kawaii-topo:has(.cartinha-st) {{ padding-left: 20px; padding-right: 20px; }}
  }}
</style>
<div class="kawaii-topo">
  {enfeites}
  {MASCOTE}
  <div><span class="etiqueta">LINGUAGEM DE PROGRAMAÇÃO · PROJETO G2</span></div>
  <h1>Despesas de viagem do BNDES (2009–2026)</h1>
  <p>Quem viaja, quem gasta e o efeito da pandemia de COVID-19.</p>
  <p><strong>Giovanna Poggi e Juliana Neto</strong> · Prof. Alexandre Neves Louzada<br>
  Linguagem de Programação (Análise e Visualização de Dados com Python) · UniLaSalle-RJ · 2026.2</p>
  {cartinha_html}
</div>
""", unsafe_allow_html=True)

col_g, col_j, col_dica = st.columns([1, 1, 2.4], vertical_alignment="center")
col_g.button("🦇 Giovanna Poggi", on_click=alternar_tema, args=("gotico",),
             type="primary" if TEMA == "gotico" else "secondary", help="Tema secreto da Giovanna")
col_j.button("🍓 Juliana Neto", on_click=alternar_tema, args=("rosa",),
             type="primary" if TEMA == "rosa" else "secondary", help="Tema secreto da Juliana")
col_dica.caption({
    None: "✨ Clique no nome de uma autora para descobrir um tema secreto.",
    "gotico": "Tema secreto da Giovanna: kawaii gótico 🦇 Clique de novo no nome para voltar.",
    "rosa": "Tema secreto da Juliana: kawaii rosa 🍓 Clique de novo no nome para voltar.",
}[TEMA])

if d.empty:
    st.warning("Nenhuma viagem com esses filtros. Tente ampliar o período ou limpar algum filtro.")
    st.stop()

pessoas = d["pessoa_id"].nunique()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Viagens", numero(len(d)))
c2.metric("Pessoas que viajaram", numero(pessoas))
c3.metric("Gasto total", reais(d[COL_VALOR].sum()))
c4.metric("Viagem típica", reais(d[COL_VALOR].median()), help="Custo mediano de uma viagem")
c5.metric("Viagens por pessoa", numero(len(d) / pessoas, 1))

if anos[0] <= 2019 < 2020 <= anos[1]:
    st.info(
        "O período escolhido atravessa 2020, quando o BNDES mudou o formato do registro: os códigos de cargo mudam "
        "e o total passa a incluir itens não detalhados. Compare custos entre os dois períodos com cautela.",
        icon="ℹ️",
    )

# ---------------- DESTAQUES ----------------
# frases montadas a partir da seleção atual: mudam junto com os filtros da barra lateral
def resumo_por(base, chave, minimo_viagens):
    """Viagens, pessoas e gasto por grupo, só com grupos que têm viagens suficientes para comparar."""
    g = base.groupby(chave).agg(viagens=("codigoviagem", "size"), pessoas=("pessoa_id", "nunique"),
                                gasto=(COL_VALOR, "sum"), custo_medio=(COL_VALOR, "mean"))
    g = g[g["viagens"] >= minimo_viagens]
    g["gasto_por_pessoa"] = g["gasto"] / g["pessoas"]
    g["viagens_por_pessoa"] = g["viagens"] / g["pessoas"]
    return g


destaques = []

# área da liderança (só superintendências: as siglas DIRn e PRESI são as próprias diretorias e entram no destaque seguinte)
lider = d.dropna(subset=["area_sigla"])
superint = lider[~lider["area_sigla"].str.match(r"^(DIR\d|PRESI)$")]
areas = resumo_por(superint, ["area_sigla", "area_nome", "diretoria"], 20)
if len(areas) >= 2:
    mais_viaja = areas["viagens"].idxmax()
    mais_cara = areas["custo_medio"].idxmax()
    frase = (f"**A área que mais viaja é {mais_viaja[0]}** ({mais_viaja[1]}, {mais_viaja[2]}): "
             f"{numero(areas.loc[mais_viaja, 'viagens'])} viagens dos seus dirigentes, que somam {reais(areas.loc[mais_viaja, 'gasto'])}.")
    if mais_cara != mais_viaja:
        frase += (f" **Porém, a viagem mais cara é a de {mais_cara[0]}** ({mais_cara[1]}): "
                  f"{reais(areas.loc[mais_cara, 'custo_medio'])} em média, contra {reais(areas.loc[mais_viaja, 'custo_medio'])} na {mais_viaja[0]}.")
    destaques.append(("🏢", frase))

# diretoria
dirs = resumo_por(lider, "diretoria", 20)
if len(dirs) >= 2:
    mais_gasta, menos_viaja = dirs["gasto"].idxmax(), dirs["viagens_por_pessoa"].idxmin()
    frase = (f"**A diretoria que mais gasta é a {mais_gasta}**, com {reais(dirs.loc[mais_gasta, 'gasto'])} "
             f"e {numero(dirs.loc[mais_gasta, 'viagens_por_pessoa'])} viagens por dirigente.")
    if menos_viaja != mais_gasta:
        frase += (f" **Já a {menos_viaja} é a que menos viaja:** {numero(dirs.loc[menos_viaja, 'viagens_por_pessoa'])} "
                  f"viagens por dirigente.")
    destaques.append(("🧭", frase))

# cargo (um destaque por período, porque os códigos mudam em 2020)
for formato in sorted(d["formato_registro"].unique()):
    base_cargo = d[(d["formato_registro"] == formato) & (d[COL_VALOR] > 0) & ~d["cargo"].isin(SEM_CARGO)]
    cargos = resumo_por(base_cargo, "cargo", 100)
    if len(cargos) < 2:
        continue
    total = cargos["gasto"].idxmax()
    # no "por pessoa", só cargos com 5+ pessoas: com 1 ou 2 pessoas a média vira retrato individual
    comparaveis = cargos[cargos["pessoas"] >= 5]
    por_pessoa = comparaveis["gasto_por_pessoa"].idxmax() if not comparaveis.empty else total
    frase = (f"**{formato}: o cargo que mais gasta no total é {total}** ({reais(cargos.loc[total, 'gasto'])}, "
             f"com {numero(cargos.loc[total, 'pessoas'])} pessoas viajando).")
    if por_pessoa != total:
        razao_pessoa = cargos.loc[por_pessoa, "gasto_por_pessoa"] / cargos.loc[total, "gasto_por_pessoa"]
        razao_viagem = cargos.loc[por_pessoa, "custo_medio"] / cargos.loc[total, "custo_medio"]
        razao_freq = cargos.loc[por_pessoa, "viagens_por_pessoa"] / cargos.loc[total, "viagens_por_pessoa"]
        frase += (f" **Porém, por pessoa quem mais gasta é {por_pessoa}:** {reais(cargos.loc[por_pessoa, 'gasto_por_pessoa'])} cada, "
                  f"{numero(razao_pessoa, 1)} {plural(razao_pessoa, 'vez', 'vezes')} o de {total}. "
                  f"Uma viagem de {por_pessoa} vale {numero(razao_viagem, 2)} {plural(razao_viagem, 'viagem', 'viagens')} de {total}, ")
        if razao_freq > razao_viagem:
            frase += (f"mas o que mais pesa é a frequência: {numero(cargos.loc[por_pessoa, 'viagens_por_pessoa'], 1)} viagens por pessoa, "
                      f"contra {numero(cargos.loc[total, 'viagens_por_pessoa'], 1)}.")
        else:
            frase += (f"e é esse preço mais alto que pesa mais do que a frequência "
                      f"({numero(cargos.loc[por_pessoa, 'viagens_por_pessoa'], 1)} viagens por pessoa, "
                      f"contra {numero(cargos.loc[total, 'viagens_por_pessoa'], 1)}).")
    destaques.append(("💼", frase))

# profissão
profs = resumo_por(d[d["profissao"] != "Não identificada"], "profissao", 100)
profs = profs[profs["pessoas"] >= 5]
if len(profs) >= 2:
    mais_viaja, mais_pp = profs["viagens"].idxmax(), profs["viagens_por_pessoa"].idxmax()
    frase = (f"**A profissão que mais viaja é {mais_viaja}:** {numero(profs.loc[mais_viaja, 'viagens'])} viagens, "
             f"{numero(profs.loc[mais_viaja, 'gasto'] / profs['gasto'].sum() * 100)}% do gasto das profissões identificadas.")
    if mais_pp != mais_viaja:
        frase += (f" **Por pessoa, porém, quem mais viaja é {mais_pp}**, com {numero(profs.loc[mais_pp, 'viagens_por_pessoa'], 1)} "
                  f"viagens cada, contra {numero(profs.loc[mais_viaja, 'viagens_por_pessoa'], 1)}.")
    else:
        frase += f" Também lidera por pessoa: {numero(profs.loc[mais_viaja, 'viagens_por_pessoa'], 1)} viagens cada."
    destaques.append(("👷", frase))

# motivo
mots = resumo_por(d, "motivo_exibicao", 100)
if len(mots) >= 2:
    freq, caro = mots["viagens"].idxmax(), mots["custo_medio"].idxmax()
    minuscula = lambda t: t[0].lower() + t[1:]
    frase = (f"**O motivo mais comum é {minuscula(freq)}** ({numero(mots.loc[freq, 'viagens'] / len(d) * 100)}% das viagens).")
    if caro != freq:
        frase += (f" **Porém, o mais caro por viagem é {minuscula(caro)}:** {reais(mots.loc[caro, 'custo_medio'])} em média, "
                  f"contra {reais(mots.loc[freq, 'custo_medio'])}.")
    destaques.append(("🎯", frase))

# pandemia (só quando 2019 e 2021 estão na seleção)
por_ano_sel = d.groupby("ano").size()
if {2019, 2021}.issubset(por_ano_sel.index):
    queda = (por_ano_sel[2021] / por_ano_sel[2019] - 1) * 100
    frase = f"**Na pandemia, as viagens caíram {numero(abs(queda))}%** de 2019 para 2021."
    if 2025 in por_ano_sel.index:
        rec = (por_ano_sel[2025] / por_ano_sel[2019] - 1) * 100
        frase += f" Em 2025 o volume está {numero(abs(rec))}% {'abaixo' if rec < 0 else 'acima'} de 2019."
    destaques.append(("🦠", frase))

if destaques:
    st.markdown("### Destaques")
    st.caption("Calculados a partir dos filtros atuais. Comparações exigem pelo menos 100 viagens por grupo (20 nas áreas da liderança).")
    with st.container(border=True):
        for icone, frase in destaques:
            st.markdown(f"{icone} {frase}")

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
    st.bar_chart(anual, y_label="R$ milhões", color=ROSA)

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
        st.bar_chart(top[medida], horizontal=True, color=LILAS, sort=f"-{medida}")
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
            st.bar_chart(cargos[col_custo], horizontal=True, color=ROSA, sort=f"-{col_custo}", x_label="R$ por viagem")
        with g2:
            st.markdown("**Gasto de uma pessoa no período**")
            st.bar_chart(cargos["gasto_por_pessoa"], horizontal=True, color=LILAS, sort="-gasto_por_pessoa", x_label="R$ por pessoa")

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
        "cerca de 4% do total. Como o portal não tem tabela de setores, o nome de cada área e a sua diretoria foram "
        "mapeados manualmente no código a partir do organograma oficial. As viagens de cada dirigente cobrem toda a "
        "série, inclusive antes do cargo atual."
    )
    lider = d.dropna(subset=["area_sigla"])
    if lider.empty:
        st.info("Nenhuma viagem de dirigente nesta seleção.")
    else:
        visao = st.radio("Agrupar por", ["Diretoria", "Área"], horizontal=True)
        chave = ["diretoria"] if visao == "Diretoria" else ["area_sigla", "area_nome", "diretoria"]
        grupo = lider.groupby(chave).agg(
            viagens=("codigoviagem", "size"), dirigentes=("pessoa_id", "nunique"),
            gasto=(COL_VALOR, "sum"), custo_mediano=(COL_VALOR, "median"),
        ).reset_index()
        grupo["viagens_por_dirigente"] = grupo["viagens"] / grupo["dirigentes"]
        grupo = grupo.sort_values("gasto", ascending=False)
        rotulo = "diretoria" if visao == "Diretoria" else "area_sigla"
        st.bar_chart(grupo.set_index(rotulo)["gasto"].head(15), horizontal=True, color=LILAS, sort="-gasto",
                     x_label="Gasto")
        st.dataframe(
            grupo.rename(columns={"area_sigla": "sigla", "area_nome": "área", "diretoria": "diretoria"})
                 .style.format({"gasto": reais, "custo_mediano": reais, "viagens_por_dirigente": "{:.0f}"}),
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
    st.bar_chart(mot["viagens"].head(12), horizontal=True, color=ROSA, sort="-viagens")
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
    st.bar_chart(por_ano["viagens"], y_label="Viagens no ano", color=PESSEGO)
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
                          color=["#ffc9a8", "#c9b3f5"]),
            width="stretch",
        )

    st.caption("Custos depois de 2020 são afetados pela mudança no formato de registro, além da pandemia.")

# ---------------- DADOS ----------------
with abas[6]:
    st.subheader("Base tratada (filtrada)")
    colunas = ["codigoviagem", "data_partida", "ano", "cargo", "profissao", "area_sigla", "area_nome", "diretoria", "motivo_principal",
               "internacional", "n_trechos", "n_diarias", "valor_total", "valor_total_real", "outlier_valor"]
    st.dataframe(d[colunas], hide_index=True, width="stretch")
    st.download_button("Baixar CSV filtrado", d[colunas].to_csv(index=False).encode("utf-8"),
                       file_name="viagens_bndes_filtrado.csv", mime="text/csv")
    st.caption("Nomes e CPFs não são publicados: cada pessoa aparece só por um pseudônimo (pessoa_id) na base completa.")

st.divider()
st.caption("Código, dados e artigo: github.com/mochilicius/g2lingprog · código MIT · dados ODbL 1.0 · texto CC BY 4.0")
