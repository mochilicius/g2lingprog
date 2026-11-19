# Dicionário de dados

Metadados das bases usadas e geradas pelo projeto. Toda a base tratada é produzida por `src/etl.py` (`python -m src.etl`), e cada decisão do tratamento fica registrada em `processed/etl_log.json`.

## 1. Fontes brutas (`data/raw/`)

| Arquivo | Origem | Licença | Granularidade | Observações |
|---|---|---|---|---|
| `despesas-viagens.csv` | [BNDES, Despesas viagens](https://dadosabertos.bndes.gov.br/dataset/despesas-viagens) | ODbL 1.0 | 1 linha por **trecho** de viagem (303.868 linhas) | ~73 MB, não versionado (`.gitignore`); baixado pelo pipeline. Codificação latin-1, separador `;`. |
| `empregados.csv` | [BNDES, Empregados e Estagiários](https://dadosabertos.bndes.gov.br/dataset/empregados) | ODbL 1.0 | 1 linha por empregado ou estagiário **atual** (3.419 linhas) | Colunas: matrícula, nome, função, cargo de formação. Não tem lotação. |
| `organograma.csv` | [BNDES, Organograma](https://dadosabertos.bndes.gov.br/dataset/organograma/resource/c609ce7b-ed0e-4b28-9986-d224a223b722) | ODbL 1.0 | 1 linha por dirigente **atual** (34 linhas) | Única base pública com a lotação (sigla da área); cobre só diretores, superintendentes e presidente. |
| `ipca_mensal.json` | [Banco Central, SGS série 433](https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2009) | dado público | 1 linha por mês | Variação mensal do IPCA (%), usada para a correção monetária. |

### Particularidades do arquivo de viagens

O arquivo mistura **dois formatos de registro**, identificados pelo formato da data de partida:

| | 2009–2019 | 2020 em diante |
|---|---|---|
| Data | `2019-12-30 16:30:00` | `31/12/2020 07:00` |
| Números | ponto decimal: `358.62` | padrão brasileiro: `3.902,57` |
| Nº de diárias | multiplicado por 100: `300` = 3 diárias | `3,00` |
| Componentes do custo | passagens + diárias + acréscimos = total em 100% das viagens | fecham o total em ~32% das viagens |
| Códigos de cargo | predominam 34 (Nível Superior) e 9003 (Gerente Executivo) | predominam códigos DAS (8, 19, 20, 23, 29) |
| Viagens internacionais | não registradas | 1,5–4% das viagens por ano |

Os campos de valor total, acréscimos, hospedagem e locação são **da viagem** e se repetem em cada trecho. Somá-los por linha infla o gasto em 144%; o pipeline agrega por viagem antes de somar.

## 2. Base tratada (`data/processed/viagens.csv.gz`)

CSV UTF-8 comprimido com gzip, separador `,`, decimal `.`, datas `AAAA-MM-DD HH:MM`. Uma linha por **viagem** (144.930 linhas). Leitura recomendada: `src.etl.carregar_processado()`.

| Variável | Tipo | Formato / domínio | Significado | Origem |
|---|---|---|---|---|
| `codigoviagem` | inteiro | ex.: `202020010` | Identificador único da viagem atribuído pelo BNDES | viagens: `codigoviagem` |
| `pessoa_id` | texto | 12 caracteres hexadecimais | Pseudônimo da pessoa (SHA-256 do nome normalizado). Substitui nome e CPF, que não são publicados na base tratada | derivado |
| `data_partida` | data-hora | `AAAA-MM-DD HH:MM` | Partida do primeiro trecho | viagens: mínimo de `datapartidaorigem` |
| `data_retorno` | data-hora | `AAAA-MM-DD HH:MM`; pode ser vazio | Chegada do último trecho (2.916 trechos sem data de chegada na fonte) | viagens: máximo de `datachegadadestino` |
| `ano` | inteiro | 2009–2026 | Ano da partida | derivado |
| `mes` | data | `AAAA-MM-01` | Mês da partida (primeiro dia do mês) | derivado |
| `periodo_covid` | categoria | `pré-pandemia` (até fev/2020), `pandemia` (mar/2020 a dez/2021), `pós-pandemia` | Janela usada na RQ3 | derivado |
| `formato_registro` | categoria | `2009-2019`, `2020+` | Formato de registro do arquivo de origem (ver seção 1) | derivado |
| `cargo_codigo` | inteiro | código da tabela de cargos | Código do cargo de quem viajou | viagens: `cargo` |
| `cargo` | texto | ex.: `Nível Superior`, `DAS-1011 (Assessoramento)` | Descrição do código pela tabela oficial de cargos (PDF anexo ao dataset); `Código não documentado` para 9999 | derivado |
| `profissao` | texto | ex.: `Engenheiro`; vazio se não encontrado | Cargo de formação, quando a pessoa está na base atual de empregados (75,8% das viagens) | empregados: `cargo` |
| `funcao` | texto | ex.: `Gerente`; vazio se não houver | Função executiva atual da pessoa | empregados: `funcao` |
| `area_sigla` | texto | ex.: `ASC`, `DIR7`; vazio se não for dirigente | Sigla da área do dirigente atual (3,7% das viagens) | organograma: `lotacao` |
| `area_nome` | texto | ex.: `Área de Soluções para Cidades`; vazio se não for dirigente | Nome completo da área, do mapeamento manual `AREAS` em `src/etl.py` | derivado (manual) |
| `diretoria` | texto | ex.: `DIR8 · Planejamento e Relações Institucionais`, `Presidência`, `Conselho de Administração` | Diretoria a que a área pertence, do mapeamento manual `DIRETORIAS` | derivado (manual) |
| `funcao_dirigente` | texto | `Superintendente`, `Diretor`, `Presidente` | Função no organograma | organograma: `funcao` |
| `motivo` | texto | maiúsculas sem acento | Motivo da viagem normalizado (215 grafias viram 214 categorias) | viagens: `motivoviagem` |
| `motivo_principal` | texto | maiúsculas sem acento (94 categorias) | Primeiro motivo listado quando há vários (`A / B` → `A`) e rótulos equivalentes unificados: `TREINAMENTO CENTRALIZADO` (até 2019) e `TREINAMENTO NO BRASIL` (2020+) → `TREINAMENTO NACIONAL` | derivado |
| `internacional` | booleano | `True`/`False` | Algum trecho com origem ou destino fora do Brasil | viagens: `paisorigem`, `paisdestino` |
| `n_trechos` | inteiro | ≥ 1 | Número de trechos da viagem | derivado |
| `n_diarias` | decimal | ≥ 0 | Total de diárias recebidas | viagens: soma de `numerodiarias` |
| `valor_passagens` | decimal | R$ nominais | Soma das passagens dos trechos | viagens: soma de `valorpassagem` |
| `valor_diarias` | decimal | R$ nominais | Soma das diárias dos trechos | viagens: soma de `valordiariastrecho` |
| `valor_acrescimos` | decimal | R$ nominais | Adicionais de embarque menos descontos | viagens: `valoracrescimosdeducoes` |
| `valor_hospedagem` | decimal | R$ nominais | Hospedagens contratadas | viagens: `valortotalhospedagem` |
| `valor_locacao` | decimal | R$ nominais | Locações de veículo contratadas | viagens: `valortotallocacao` |
| `valor_total` | decimal | R$ nominais | Valor total oficial da viagem | viagens: `valortotalviagemptpbndes` |
| `valor_total_real` | decimal | R$ de out/2026 | `valor_total` corrigido pelo IPCA acumulado até o último mês divulgado | derivado (IPCA) |
| `outlier_valor` | booleano | `True`/`False` | Valor total acima de Q3 + 1,5·IQR, calculado dentro de cada `formato_registro`. Sinalizado, nunca removido | derivado |

## 3. Log do pipeline (`data/processed/etl_log.json`)

Contagens de cada etapa: trechos lidos por formato, nulos após conversão, viagens com total divergente entre trechos (152), viagens com valor zero (780), homônimos resolvidos na base de empregados (4), cobertura de cada cruzamento, limites de outlier e mês-base do IPCA.

## 4. Regras de cruzamento

- As bases são cruzadas pelo **nome normalizado** (maiúsculas, sem acento, espaços simples), porque a base de viagens não traz matrícula.
- Em homônimos da base de empregados, prevalece a linha com cargo de formação informado (as duplicatas são diretores que aparecem também com "Não se Aplica").
- As bases de empregados e organograma são retratos **atuais**: quem saiu do banco não é encontrado, e a área de um dirigente é a de hoje, não a da época da viagem.

## 5. Setor: mapeamento manual

O portal de dados abertos do BNDES **não tem uma tabela de setores**. O `organograma.csv` traz só a sigla da lotação de cada dirigente, e as bases de viagens e de empregados não informam setor nenhum. Por isso a classificação por setor foi feita **manualmente, no código**: os dicionários `AREAS` e `DIRETORIAS` em `src/etl.py` associam cada uma das 34 siglas ao nome completo da área e à diretoria a que ela pertence, transcritos do Organograma Geral do BNDES e da página [Quem é quem no BNDES](https://www.bndes.gov.br/wps/portal/site/home/quem-somos/quem-e-quem) (atualização de 13/10/2026).

- O pipeline interrompe a execução se o organograma trouxer uma sigla que não esteja no mapeamento, para que uma reestruturação do banco não passe despercebida.
- A Auditoria Interna (AT) responde ao Conselho de Administração, não a uma diretoria, e aparece como `Conselho de Administração`.
- A classificação vale só para as viagens dos 34 dirigentes atuais (3,7% do total), porque não existe base pública que ligue os demais empregados a uma área.

## 6. Licenças

- Dados de origem: [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/), conforme o portal do BNDES. A base tratada é uma obra derivada e é distribuída sob a mesma licença.
- Código: MIT (arquivo `LICENSE`).
- Texto do artigo e figuras: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
