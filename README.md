# PC Parts Scrapper (Google Sheets + CSV diario)

Agente para monitorar precos de pecas de computador.

Fluxo:
1. Le uma lista base de pecas no Google Sheets (coluna A).
2. Para cada peca, consulta lojas (Kabum, Pichau, Terabyte) e captura preco + URL.
3. Atualiza a planilha com os precos do dia.
4. Gera um CSV diario em `src/data/daily/YYYY_MM_DD.csv`.

## Estrutura

```
pc-parts-scrapper/
  agent.py                 # entrypoint (compat): python agent.py
  requirements.txt
  src/
    agent.py               # python -m src.agent
    config.py
    sheets.py
    storage.py
    scrapers/
      __init__.py
      base.py
      kabum.py
      pichau.py
      terabyte.py
    data/
      daily/               # gerado automaticamente
      history/             # gerado automaticamente (history.csv unico)
```

## Setup

1. Instale dependencias:

```bash
pip install -r requirements.txt
```

2. Configure Google Sheets:
  - Ative a Google Sheets API no Google Cloud Console
  - Crie uma Service Account e baixe o JSON
  - Compartilhe a planilha com o email da Service Account (Editor)

3. Configure variaveis de ambiente (recomendado):

```bash
set GOOGLE_CREDENTIALS_FILE=credentials.json
```

4. Crie um `config.json` na raiz (use `config.example.json` como base):
  - `spreadsheet_id`: ID da planilha (na URL do Google Sheets)
  - `sheet_name`: nome da aba
  - `excluded_types`: lista de valores da coluna `Tipo` a ignorar (ex: `["Gabinete"]`)
  - `storage_backend`: `"local"` (CSV) ou `"postgres"` (Supabase Postgres)
  - `postgres.dsn_env`: nome da env var que contem o DSN do Postgres do Supabase (recomendado)
  - `postgres.dsn`: alternativa: colocar o DSN diretamente no config (nao recomendado)

Quando `storage_backend` = `postgres`, a persistencia diaria vai para a tabela `price_history` (uma linha por `snapshot_date` + `part` + `store`):
- `part TEXT`
- `snapshot_date DATE`
- `store TEXT`
- `price NUMERIC`
- `url TEXT`
- PK: `(snapshot_date, part, store)`

Rodar mais de uma vez no mesmo dia atualiza a mesma linha da mesma loja (UPSERT por `(snapshot_date, part, store)`).

## Formato da planilha

Colunas (padrao):
- A: Peça
- B: Valor (menor preco do dia)
- C: Tipo
- D: URL (da loja mais barata)
- E: Observacoes/Notas

A linha 1 e tratada como cabecalho e ignorada.

## Uso

Rodar uma vez:

```bash
python agent.py
```

Dry-run (nao grava no Sheets nem gera CSV/historico):

```bash
python agent.py --dry-run
```

## Docker (Postgres + Metabase + Scraper)

Arquivos:
- `docker-compose.yml` (fixa versoes de imagem, sem `latest`)
- `Dockerfile` (container do scraper)
- `docker/postgres/init.sql` (cria o DB do Metabase na primeira subida)

Imagens usadas (ver `docker-compose.yml` para a fonte da verdade):
- Postgres: `postgres:16.4-alpine`
- Metabase: `metabase/metabase:v0.49.17`
- Scraper: build local via `Dockerfile` (base `python:3.13.2-slim-bookworm`)

### 1) Configurar `config.json` para Postgres

No seu `config.json`, use:
- `storage_backend`: `"postgres"`
- `postgres.dsn_env`: `"PCPARTS_POSTGRES_DSN"`

O `docker-compose.yml` ja exporta `PCPARTS_POSTGRES_DSN` apontando para o Postgres do compose:
`postgresql://pcparts:pcparts@postgres:5432/pcparts`

### 2) Credenciais do Google Sheets

O compose monta o arquivo `./src/credentials.json` para dentro do container e seta:
`GOOGLE_CREDENTIALS_FILE=/app/src/credentials.json`.

Se voce preferir usar outro caminho/nome, ajuste os `volumes` e/ou a env var no `docker-compose.yml`.

### 3) Subir Postgres + Metabase

```bash
docker compose up -d postgres metabase
```

Metabase: `http://localhost:3000`

No Metabase, conecte no Postgres do compose:
- host: `postgres` (ou `localhost` se estiver acessando fora da rede do compose)
- port: `5432`
- db: `pcparts`
- user/pass: `pcparts` / `pcparts`

### 4) Rodar o scraper (um-run)

Dry-run:

```bash
docker compose --profile scrape run --rm scraper --dry-run
```

Rodando de verdade:

```bash
docker compose --profile scrape run --rm scraper
```

## CSV diario

Arquivo: `src/data/daily/YYYY_MM_DD.csv`

Colunas:
- `peca`
- `kabum_valor`, `kabum_url`
- `pichau_valor`, `pichau_url`
- `terabyte_valor`, `terabyte_url`

## Historico (unico)

Arquivo: `src/data/history/history.csv`

Colunas:
- `timestamp`, `store`, `product_name`, `price`, `url`
