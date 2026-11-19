"""Pipeline de ingestão e tratamento das despesas de viagem do BNDES.

Uso: python -m src.etl   (a partir da raiz do repositório)

Etapas:
1. baixa as bases brutas do portal de dados abertos do BNDES (requests);
2. lê o CSV de viagens (latin-1, separador ";") e converte números e datas,
   tratando os dois formatos que convivem no arquivo (2009-2019 e 2020+);
3. agrega os trechos em viagens (o valor total se repete em cada trecho);
4. corrige os valores pela inflação (IPCA, API do Banco Central);
5. enriquece cada viagem com a profissão (base de empregados) e a área
   (organograma), cruzando pelo nome normalizado;
6. remove nomes e CPFs, sinaliza outliers e grava data/processed/viagens.csv.gz
   junto com um log de cada etapa (data/processed/etl_log.json).

Nenhuma linha é apagada em silêncio: cada filtro ou correção fica no log.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
RAW_DIR = RAIZ / "data" / "raw"
PROCESSED_DIR = RAIZ / "data" / "processed"

# links permanentes dos recursos no portal (CKAN) do BNDES
FONTES = {
    "despesas-viagens.csv": (
        "https://dadosabertos.bndes.gov.br/dataset/14696402-52a2-4238-89f0-c9fcf821f0a4/"
        "resource/d117404f-092b-435d-a229-dc72c9b27dad/download/despesas-viagens.csv"
    ),
    "empregados.csv": (
        "https://dadosabertos.bndes.gov.br/dataset/9ec8cc31-5aa5-440d-b867-14330e3d3213/"
        "resource/0f9b0b80-897a-40e2-8bcb-4431b771a9c1/download/empregados-e-estagiarios-do-bndes.csv"
    ),
    "organograma.csv": (
        "https://dadosabertos.bndes.gov.br/dataset/53f53f9a-eb85-443c-ae3e-b563727640c0/"
        "resource/c609ce7b-ed0e-4b28-9986-d224a223b722/download/organograma.csv"
    ),
}

# IPCA mensal (variação %), série 433 do Sistema Gerenciador de Séries Temporais do Banco Central
URL_IPCA = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2009"

# tabela oficial de cargos do Portal da Transparência (PDF anexo ao dataset, versão de 26/08/2010)
CARGOS = {
    0: "Não se aplica", 3: "CCD-I", 4: "CCD-II", 5: "CCT-III", 6: "CCT-IV", 7: "CCT-V",
    8: "DAS-1011 (Assessoramento)", 9: "DAS-1012 (Assessoramento)",
    10: "DAS-1021 (Assessoramento)", 11: "DAS-1022 (Assessoramento)",
    19: "DAS-1013 (Coordenação)", 20: "DAS-1014 (Coordenação)",
    21: "DAS-1023 (Coordenação)", 22: "DAS-1024 (Coordenação)",
    23: "DAS-1015 (Direção)", 24: "DAS-1025 (Direção)", 29: "DAS-1016 (Cargo Superior)",
    30: "CNE-0001 (Natureza Especial)", 31: "Nível Auxiliar", 32: "Nível Intermediário",
    33: "Nível Médio", 34: "Nível Superior", 9001: "Assessor", 9002: "Assessor-Sênior",
    9003: "Gerente Executivo", 9004: "Superintendente Executivo", 9005: "Chefe de Auditoria",
    9006: "Chefe de Gabinete", 9007: "Consultor Jurídico", 9008: "Diretor",
    9009: "Diretor Presidente", 9010: "Conselheiro",
}

# motivos que mudaram de nome junto com o formato de registro de 2020 (mesma atividade, rótulo novo)
MOTIVOS_EQUIVALENTES = {
    "TREINAMENTO CENTRALIZADO": "TREINAMENTO NACIONAL",
    "TREINAMENTO NO BRASIL": "TREINAMENTO NACIONAL",
}

# Estrutura de áreas do BNDES, digitada à mão. O portal de dados abertos não tem uma tabela de setores:
# o organograma.csv traz só a sigla da lotação de cada dirigente. Os nomes das áreas e a diretoria a que
# cada uma pertence foram transcritos do Organograma Geral e da página "Quem é quem no BNDES"
# (atualização de 13/10/2026). Se o banco reestruturar as áreas, este dicionário precisa ser revisto.
DIRETORIAS = {
    "PRESI": "Presidência",
    "DIR1": "DIR1 · Pessoas, TI e Operações",
    "DIR2": "DIR2 · Socioambiental",
    "DIR3": "DIR3 · Financeira e de Mercado de Capitais",
    "DIR4": "DIR4 · Crédito Digital para MPMEs e Gestão do Fundo Rio Doce",
    "DIR5": "DIR5 · Infraestrutura e Mudança Climática",
    "DIR6": "DIR6 · Jurídica",
    "DIR7": "DIR7 · Desenvolvimento Produtivo, Inovação e Comércio Exterior",
    "DIR8": "DIR8 · Planejamento e Relações Institucionais",
    "DIR9": "DIR9 · Risco e Compliance",
    "CA": "Conselho de Administração",
}
AREAS = {  # sigla: (nome da área, chave da diretoria)
    "PRESI": ("Presidência", "PRESI"),
    "ARMC": ("Área de Relacionamento, Marketing e Cultura", "PRESI"),
    "DIR1": ("Diretoria 1", "DIR1"),
    "ARH": ("Área de Recursos Humanos", "DIR1"),
    "ATI": ("Área de Tecnologia da Informação", "DIR1"),
    "ASN": ("Área de Suporte ao Negócio", "DIR1"),
    "DIR2": ("Diretoria 2", "DIR2"),
    "AS": ("Área de Desenvolvimento Social e Gestão Pública", "DIR2"),
    "AMA": ("Área de Meio Ambiente", "DIR2"),
    "DIR3": ("Diretoria 3", "DIR3"),
    "AF": ("Área Financeira", "DIR3"),
    "ACO": ("Área de Controladoria", "DIR3"),
    "AMC": ("Área de Mercado de Capitais, Investimentos e Participações", "DIR3"),
    "DIR4": ("Diretoria 4", "DIR4"),
    "ADIG": ("Área de Operações e Canais Digitais", "DIR4"),
    "ARD": ("Área de Enfrentamento de Eventos Extremos e Gestão do Fundo Rio Doce", "DIR4"),
    "DIR5": ("Diretoria 5", "DIR5"),
    "AINFRA": ("Área de Infraestrutura", "DIR5"),
    "AEC": ("Área de Transição Energética e Clima", "DIR5"),
    "DIR6": ("Diretoria 6", "DIR6"),
    "AJI": ("Área Jurídica Institucional", "DIR6"),
    "AJN": ("Área Jurídica de Negócios", "DIR6"),
    "DIR7": ("Diretoria 7", "DIR7"),
    "AI": ("Área de Desenvolvimento Produtivo e Inovação", "DIR7"),
    "AEX": ("Área de Comércio Exterior", "DIR7"),
    "DIR8": ("Diretoria 8", "DIR8"),
    "ASC": ("Área de Soluções para Cidades", "DIR8"),
    "ASI": ("Área de Soluções de Infraestrutura", "DIR8"),
    "AP": ("Área de Planejamento e Pesquisa Econômica", "DIR8"),
    "AINT": ("Área Internacional e de Captação de Recursos", "DIR8"),
    "DIR9": ("Diretoria 9", "DIR9"),
    "AGR": ("Área de Gestão de Riscos", "DIR9"),
    "AIC": ("Área de Integridade e Compliance", "DIR9"),
    "AT": ("Auditoria Interna", "CA"),  # ligada ao Conselho de Administração, não a uma diretoria
}

COLUNAS_VALOR = [
    "valorpassagem", "numerodiarias", "valordiariastrecho", "valortotalviagemptpbndes",
    "valoracrescimosdeducoes", "valortotalhospedagem", "valortotallocacao",
]

# janela da pandemia nas análises: da declaração de pandemia pela OMS (11/03/2020) até o fim de 2021
INICIO_PANDEMIA = pd.Timestamp("2020-03-01")
FIM_PANDEMIA = pd.Timestamp("2021-12-31")


# ---------------------------------------------------------------- aquisição
def baixar_dados(destino: Path = RAW_DIR, forcar: bool = False) -> dict[str, Path]:
    """Baixa os CSVs brutos. Pula o arquivo se ele já existe (a menos que forcar=True)."""
    destino.mkdir(parents=True, exist_ok=True)
    caminhos = {}
    for nome, url in FONTES.items():
        caminho = destino / nome
        if forcar or not caminho.exists():
            resposta = requests.get(url, timeout=300)
            resposta.raise_for_status()
            caminho.write_bytes(resposta.content)
        caminhos[nome] = caminho

    caminho_ipca = destino / "ipca_mensal.json"
    if forcar or not caminho_ipca.exists():
        # sem o Accept a API do BCB devolve uma página HTML de erro em vez do JSON
        resposta = requests.get(URL_IPCA, headers={"Accept": "application/json"}, timeout=60)
        resposta.raise_for_status()
        caminho_ipca.write_text(json.dumps(resposta.json(), ensure_ascii=False))
    caminhos["ipca_mensal.json"] = caminho_ipca
    return caminhos


# ---------------------------------------------------------------- utilidades
def normalizar_texto(valor) -> str:
    """Maiúsculas, sem acento e com espaços simples: base para comparar nomes e motivos."""
    if pd.isna(valor):
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def pseudonimo(nome_normalizado: str) -> str:
    """Identificador estável da pessoa sem expor o nome (primeiros 12 caracteres do SHA-256)."""
    return hashlib.sha256(nome_normalizado.encode()).hexdigest()[:12]


def _numero_brasileiro(serie: pd.Series) -> pd.Series:
    """'3.902,57' -> 3902.57"""
    texto = serie.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(texto, errors="coerce")


# ---------------------------------------------------------------- trechos
def ler_viagens(caminho: Path) -> pd.DataFrame:
    """Lê o CSV bruto como texto: a conversão de tipos é feita depois, com regras explícitas."""
    return pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str)


def tratar_trechos(bruto: pd.DataFrame, log: dict) -> pd.DataFrame:
    """Converte datas e valores de cada trecho.

    O arquivo mistura dois formatos de registro:
    - 2009-2019: datas ISO ('2019-12-30 16:30:00') e números com ponto decimal ('358.62');
      o número de diárias vem multiplicado por 100 ('300' = 3 diárias), como diz o dicionário.
    - 2020+: datas 'dd/mm/aaaa hh:mm' e números no padrão brasileiro ('3.902,57').
    """
    df = bruto.copy()
    legado = df["datapartidaorigem"].str.contains("-", na=False)
    df["formato_registro"] = np.where(legado, "2009-2019", "2020+")

    for coluna in COLUNAS_VALOR:
        convertido = pd.Series(np.nan, index=df.index)
        convertido[legado] = pd.to_numeric(df.loc[legado, coluna], errors="coerce")
        convertido[~legado] = _numero_brasileiro(df.loc[~legado, coluna])
        df[coluna] = convertido
    df.loc[legado, "numerodiarias"] = df.loc[legado, "numerodiarias"] / 100

    for coluna in ["datapartidaorigem", "datachegadadestino"]:
        df[coluna] = pd.to_datetime(df[coluna], format="mixed", dayfirst=True, errors="coerce")

    df["cargo"] = pd.to_numeric(df["cargo"], errors="coerce").astype("Int64")
    df["motivo"] = df["motivoviagem"].map(normalizar_texto).replace("", "NAO INFORMADO")
    df["nome_normalizado"] = df["nomeservidor"].map(normalizar_texto)
    df["internacional"] = (df["paisdestino"] != "1") | (df["paisorigem"] != "1")

    log["trechos_lidos"] = int(len(df))
    log["trechos_por_formato"] = df["formato_registro"].value_counts().to_dict()
    log["nulos_apos_conversao"] = {
        c: int(n) for c, n in df[COLUNAS_VALOR + ["datapartidaorigem", "datachegadadestino"]].isna().sum().items() if n
    }
    df["motivo_principal"] = df["motivo"].map(motivo_principal)
    log["motivos_distintos"] = {
        "bruto": int(bruto["motivoviagem"].nunique()),
        "normalizado": int(df["motivo"].nunique()),
        "principal": int(df["motivo_principal"].nunique()),
    }
    log["trechos_com_motivo_composto"] = int(df["motivo"].str.contains(" / ", regex=False).sum())
    return df


def motivo_principal(motivo: str) -> str:
    """Primeiro motivo listado ('FOMENTO / ANALISE DE PROJETO' -> 'FOMENTO') com rótulos equivalentes unificados."""
    primeiro = motivo.split(" / ")[0].strip()
    return MOTIVOS_EQUIVALENTES.get(primeiro, primeiro)


# ---------------------------------------------------------------- viagens
def agregar_viagens(trechos: pd.DataFrame, log: dict) -> pd.DataFrame:
    """Uma linha por viagem.

    Valor total, acréscimos, hospedagem e locação são da viagem e se repetem em cada trecho:
    usa-se o maior valor do grupo (igual ao primeiro em quase todos os casos) para não somar em dobro.
    Passagens e diárias são por trecho: essas sim são somadas.
    """
    viagens = trechos.groupby("codigoviagem").agg(
        data_partida=("datapartidaorigem", "min"),
        data_retorno=("datachegadadestino", "max"),
        formato_registro=("formato_registro", "first"),
        nome_normalizado=("nome_normalizado", "first"),
        cargo_codigo=("cargo", "first"),
        motivo=("motivo", "first"),
        motivo_principal=("motivo_principal", "first"),
        internacional=("internacional", "any"),
        n_trechos=("codigoviagem", "size"),
        n_diarias=("numerodiarias", "sum"),
        valor_passagens=("valorpassagem", "sum"),
        valor_diarias=("valordiariastrecho", "sum"),
        valor_acrescimos=("valoracrescimosdeducoes", "max"),
        valor_hospedagem=("valortotalhospedagem", "max"),
        valor_locacao=("valortotallocacao", "max"),
        valor_total=("valortotalviagemptpbndes", "max"),
        valores_total_distintos=("valortotalviagemptpbndes", "nunique"),
    ).reset_index()

    viagens["ano"] = viagens["data_partida"].dt.year.astype("Int64")
    viagens["mes"] = viagens["data_partida"].dt.to_period("M").dt.to_timestamp()
    viagens["cargo"] = viagens["cargo_codigo"].map(CARGOS).fillna("Código não documentado")
    viagens["periodo_covid"] = np.select(
        [viagens["data_partida"] < INICIO_PANDEMIA, viagens["data_partida"] <= FIM_PANDEMIA],
        ["pré-pandemia", "pandemia"],
        default="pós-pandemia",
    )

    log["viagens"] = int(len(viagens))
    log["viagens_total_divergente_entre_trechos"] = int((viagens["valores_total_distintos"] > 1).sum())
    log["viagens_valor_total_zero"] = int((viagens["valor_total"] <= 0).sum())
    return viagens.drop(columns="valores_total_distintos")


def _tabela_por_nome(df: pd.DataFrame, coluna_nome: str, colunas: dict[str, str]) -> pd.DataFrame:
    """Uma linha por nome normalizado. Em homônimos, prefere a linha com cargo de formação informado."""
    t = df.copy()
    t["nome_normalizado"] = t[coluna_nome].map(normalizar_texto)
    t["_sem_cargo"] = t["cargo"].map(normalizar_texto).eq("NAO SE APLICA")
    t = t.sort_values(["nome_normalizado", "_sem_cargo"]).drop_duplicates("nome_normalizado")
    return t[["nome_normalizado", *colunas]].rename(columns=colunas)


def enriquecer(viagens: pd.DataFrame, empregados: pd.DataFrame, organograma: pd.DataFrame, log: dict) -> pd.DataFrame:
    """Junta profissão/função (empregados) e área (organograma) pelo nome normalizado (left join)."""
    emp = _tabela_por_nome(empregados, "nome", {"cargo": "profissao", "funcao": "funcao"})
    org = _tabela_por_nome(organograma, "nome", {"lotacao": "area_sigla", "funcao": "funcao_dirigente"})

    log["homonimos_empregados"] = int(empregados["nome"].map(normalizar_texto).duplicated().sum())
    df = viagens.merge(emp, on="nome_normalizado", how="left", validate="many_to_one")
    df = df.merge(org, on="nome_normalizado", how="left", validate="many_to_one")
    df["profissao"] = df["profissao"].replace("Não se Aplica", np.nan)

    log["cobertura_profissao"] = round(float(df["profissao"].notna().mean()), 4)
    log["cobertura_area_organograma"] = round(float(df["area_sigla"].notna().mean()), 4)

    # nome da área e diretoria vêm do mapeamento manual AREAS (não há tabela de setores no portal)
    siglas_sem_mapa = sorted(set(organograma["lotacao"]) - set(AREAS))
    if siglas_sem_mapa:
        raise ValueError(f"Siglas do organograma sem entrada em AREAS: {siglas_sem_mapa}. Atualize o mapeamento.")
    df["area_nome"] = df["area_sigla"].map(lambda s: AREAS[s][0] if s in AREAS else np.nan)
    df["diretoria"] = df["area_sigla"].map(lambda s: DIRETORIAS[AREAS[s][1]] if s in AREAS else np.nan)
    log["areas_mapeadas_manualmente"] = len(AREAS)

    # dado pessoal sai aqui: depois do cruzamento só fica um pseudônimo
    df["pessoa_id"] = df["nome_normalizado"].map(pseudonimo)
    log["pessoas_distintas"] = int(df["pessoa_id"].nunique())
    return df.drop(columns="nome_normalizado")


def corrigir_ipca(df: pd.DataFrame, caminho_ipca: Path, log: dict) -> pd.DataFrame:
    """Adiciona valor_total_real: valor nominal levado a preços do último mês com IPCA publicado.

    Viagens de meses posteriores ao último IPCA divulgado ficam com o próprio valor nominal (fator 1).
    """
    ipca = pd.DataFrame(json.loads(caminho_ipca.read_text()))
    ipca["mes"] = pd.to_datetime(ipca["data"], format="%d/%m/%Y")
    ipca["indice"] = (1 + pd.to_numeric(ipca["valor"]) / 100).cumprod()
    base = ipca["indice"].iloc[-1]
    fator = ipca.set_index("mes")["indice"].rdiv(base)

    df = df.copy()
    df["fator_ipca"] = df["mes"].map(fator).fillna(1.0)
    df["valor_total_real"] = (df["valor_total"] * df["fator_ipca"]).round(2)
    log["ipca_mes_base"] = ipca["mes"].iloc[-1].strftime("%Y-%m")
    return df.drop(columns="fator_ipca")


def marcar_outliers(df: pd.DataFrame, log: dict) -> pd.DataFrame:
    """Sinaliza (sem remover) viagens fora de Q3 + 1,5·IQR do valor total, separado por formato de registro."""
    df = df.copy()
    df["outlier_valor"] = False
    for formato, grupo in df.groupby("formato_registro"):
        q1, q3 = grupo["valor_total"].quantile([0.25, 0.75])
        limite = q3 + 1.5 * (q3 - q1)
        df.loc[grupo.index, "outlier_valor"] = grupo["valor_total"] > limite
        log.setdefault("limite_outlier_valor", {})[formato] = round(float(limite), 2)
    log["viagens_outlier_valor"] = int(df["outlier_valor"].sum())
    return df


ORDEM_COLUNAS = [
    "codigoviagem", "pessoa_id", "data_partida", "data_retorno", "ano", "mes", "periodo_covid",
    "formato_registro", "cargo_codigo", "cargo", "profissao", "funcao", "area_sigla", "area_nome", "diretoria", "funcao_dirigente",
    "motivo", "motivo_principal", "internacional", "n_trechos", "n_diarias", "valor_passagens", "valor_diarias",
    "valor_acrescimos", "valor_hospedagem", "valor_locacao", "valor_total", "valor_total_real", "outlier_valor",
]


def executar_pipeline(baixar: bool = True) -> pd.DataFrame:
    log: dict = {}
    if baixar:
        baixar_dados()

    trechos = tratar_trechos(ler_viagens(RAW_DIR / "despesas-viagens.csv"), log)
    viagens = agregar_viagens(trechos, log)

    empregados = pd.read_csv(RAW_DIR / "empregados.csv", sep=";", encoding="latin-1", dtype=str)
    organograma = pd.read_csv(RAW_DIR / "organograma.csv", sep=";", encoding="latin-1", dtype=str)
    viagens = enriquecer(viagens, empregados, organograma, log)
    viagens = corrigir_ipca(viagens, RAW_DIR / "ipca_mensal.json", log)
    viagens = marcar_outliers(viagens, log)[ORDEM_COLUNAS].sort_values(["data_partida", "codigoviagem"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    viagens.to_csv(PROCESSED_DIR / "viagens.csv.gz", index=False, compression="gzip", date_format="%Y-%m-%d %H:%M")
    (PROCESSED_DIR / "etl_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2))
    return viagens


def carregar_processado(caminho: Path = PROCESSED_DIR / "viagens.csv.gz") -> pd.DataFrame:
    """Lê a base tratada com os tipos corretos (para o notebook e outras análises)."""
    df = pd.read_csv(caminho, parse_dates=["data_partida", "data_retorno", "mes"])
    df["cargo_codigo"] = df["cargo_codigo"].astype("Int64")
    return df


if __name__ == "__main__":
    resultado = executar_pipeline()
    print(f"{len(resultado):,} viagens gravadas em {PROCESSED_DIR / 'viagens.csv.gz'}")
