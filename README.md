# Despesas de viagem do BNDES (2009–2026): quem viaja, quem gasta e o efeito da pandemia

![Python](https://img.shields.io/badge/Python-3.13-1e3a8a)
![Licença do código](https://img.shields.io/badge/código-MIT-3b82f6)
![Licença dos dados](https://img.shields.io/badge/dados-ODbL_1.0-3b82f6)
![Licença do texto](https://img.shields.io/badge/texto-CC_BY_4.0-3b82f6)
![FAIR](https://img.shields.io/badge/FAIR-compliant-ea580c)

**Autoras:** Giovanna Poggi e Juliana Neto
**Curso:** Bacharelado em Sistemas de Informação, 6º período · semestre 2026.2
**Disciplina:** Linguagem de Programação (Análise e Visualização de Dados com Python)
**Professor orientador:** Alexandre Neves Louzada

📄 **Artigo:** [docs/index.html](docs/index.html), publicado no GitHub Pages
📊 **Dashboard interativo:** `app.py` (Streamlit), link de publicação abaixo

## Resumo executivo

Analisamos 144.930 viagens a serviço de 5.480 empregados e dirigentes do BNDES entre 2009 e 2026, a partir dos dados abertos do banco, cruzados com a base de empregados e o organograma. Os valores foram corrigidos pelo IPCA.

- **Quem mais viaja e gasta (RQ1 e RQ2):** engenheiros lideram nas duas medidas, com 28,8 mil viagens (67 por pessoa) e 26% do gasto real, seguidos de economistas e administradores. Entre as áreas da liderança, a superintendência ASC é a que mais viaja e mais gasta; a viagem mediana de um diretor custa 59% mais que a de um superintendente (R$ 4,8 mil contra R$ 3,0 mil).
- **Por cargo, pesa mais a frequência que o preço:** até 2019, uma viagem de diretor custava em média R$ 2.977, o equivalente a 1,18 viagem de Nível Superior (R$ 2.519), mas cada diretor fez 52 viagens contra 26,5 e gastou 2,3 vezes mais. A partir de 2020, uma viagem de DAS-1016 equivale a duas de DAS-1011, e cada pessoa nesse cargo gasta 20,8 vezes mais.
- **O gasto é concentrado:** os 10% que mais gastam respondem por 57% do total (Gini = 0,75).
- **Pandemia (RQ3):** as viagens caíram 82% em 2020 e 88% em 2021 frente a 2019, sem nenhuma viagem entre abril e junho de 2020. Congressos (−97%) e treinamentos (−95%) foram os motivos mais afetados; já as reuniões nos escritórios regionais quase dobraram em 2023 frente a 2019. Em 2025 o volume ainda está 6% abaixo de 2019, mas a viagem mediana custa 38% mais em termos reais (49% em 2023).

**Palavras-chave:** dados abertos; BNDES; despesas de viagem; COVID-19; análise exploratória de dados; princípios FAIR.

## Perguntas de pesquisa

- **RQ1.** Quais grupos de empregados (profissão, cargo e área) mais viajam?
- **RQ2.** Quais grupos concentram o maior gasto com viagens?
- **RQ3.** Como a pandemia de COVID-19 (mar/2020 a dez/2021) alterou o volume, os motivos e o custo das viagens?

## Fontes dos dados

| Base | Link permanente | Uso |
|---|---|---|
| Despesas viagens | https://dadosabertos.bndes.gov.br/dataset/despesas-viagens | base principal (trechos de viagem) |
| Empregados e Estagiários do BNDES | https://dadosabertos.bndes.gov.br/dataset/empregados | profissão e função de quem viajou |
| Organograma | https://dadosabertos.bndes.gov.br/dataset/organograma | área (lotação) dos dirigentes |
| IPCA mensal (BCB/SGS, série 433) | https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json | correção monetária |

Todas são públicas e não exigem cadastro nem chave de acesso. Detalhes de cada variável em [`data/data_dictionary.md`](data/data_dictionary.md).

## Como reproduzir

Requer Python 3.13 (as versões estão congeladas em `requirements.txt`).

```bash
git clone https://github.com/mochilicius/g2lingprog.git
cd g2lingprog
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m src.etl                    # baixa as bases e gera data/processed/viagens.csv.gz
streamlit run app.py                 # abre o dashboard interativo no navegador
jupyter nbconvert --to notebook --execute --inplace notebooks/analise_exploratoria.ipynb   # refaz a análise e as figuras
```

O pipeline leva cerca de 30 segundos e o notebook cerca de 20 segundos. O arquivo bruto de viagens (~73 MB) não é versionado: `src/etl.py` baixa ele direto do portal do BNDES.

## Estrutura

```text
g2lingprog/
├── README.md
├── LICENSE                          # MIT (código)
├── requirements.txt                 # pip freeze, versões fixas
├── .gitignore
├── app.py                           # dashboard interativo (Streamlit)
├── data/
│   ├── raw/                         # bases originais (a de viagens é baixada pelo pipeline)
│   ├── processed/
│   │   ├── viagens.csv.gz           # 1 linha por viagem, sem nomes nem CPFs
│   │   └── etl_log.json             # contagens de cada etapa do tratamento
│   └── data_dictionary.md
├── notebooks/
│   └── analise_exploratoria.ipynb   # exploração, tabelas e geração das figuras
├── src/
│   ├── __init__.py
│   └── etl.py                       # aquisição, limpeza, agregação e cruzamentos
└── docs/
    ├── index.html                   # artigo (GitHub Pages)
    └── assets/                      # figuras exportadas pelo notebook
```

## Dashboard interativo

O `app.py` usa a mesma base tratada do artigo e permite explorar os dados por conta própria:

- filtros por período, motivo, profissão, destino (nacional ou internacional) e valores reais ou nominais;
- indicadores que se recalculam a cada filtro (viagens, pessoas, gasto, custo mediano, viagens por pessoa);
- abas de visão geral, profissões, cargos, áreas da liderança, motivos, pandemia e dados (com download em CSV);
- na aba **Cargos**, a comparação "uma viagem de X equivale a quantas de Y" e "uma pessoa de X gasta quantas vezes uma de Y", com o cargo de referência escolhido por quem usa.

## Decisões do tratamento

- **Dois formatos no mesmo arquivo.** De 2009 a 2019 os números usam ponto decimal e o número de diárias vem ×100; a partir de 2020 os números seguem o padrão brasileiro. Ler tudo com uma regra só multiplica os valores antigos por 100.
- **Agregação por viagem.** O valor total se repete em cada trecho; somar por linha infla o gasto em 144%.
- **Cargo por período.** Os códigos de cargo mudam por completo em 2020, então o cargo é analisado separadamente em cada período. A profissão (base de empregados) é a dimensão comparável ao longo do tempo.
- **Nada é apagado em silêncio.** Outliers e viagens de valor zero são sinalizados, e cada contagem fica em `etl_log.json`.
- **Privacidade.** Nomes e CPFs (parcialmente mascarados na fonte) são usados só no cruzamento e substituídos por um pseudônimo (`pessoa_id`) antes de gravar a base tratada.

## Limitações

- O portal não publica a lotação de todos os empregados; a análise por **área** cobre só os 34 dirigentes atuais (3,7% das viagens).
- Empregados e organograma são retratos atuais: quem saiu do banco não é encontrado (cobertura da profissão de 59% em 2009 a 88% em 2026).
- A mudança de formato em 2020 coincide com a pandemia; comparações de custo entre os períodos devem ser lidas com cautela.

## Licenças

- Código: [MIT](LICENSE).
- Dados: os originais e a base tratada seguem a [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), licença dos dados do BNDES.
- Texto do artigo e figuras: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Como citar

POGGI, Giovanna; NETO, Juliana. **Despesas de viagem do BNDES (2009–2026): quem viaja, quem gasta e o efeito da pandemia**. 2026. Disponível em: https://github.com/mochilicius/g2lingprog.
