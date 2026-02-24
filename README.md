# Dashboard JIRA - GitHub Pages

Dashboard estático para visualização de dados extraídos do JIRA, hospedado no GitHub Pages.

## Estrutura

- `scripts/extract_jira.py` - Script de extração de dados do JIRA
- `dashboard/` - Dashboard estático (HTML + Chart.js)
- `data/` - Dados JSON gerados pela extração

## Configuração

1. Copie `.env.example` para `.env`
2. Preencha as variáveis com suas credenciais do JIRA:
   - `JIRA_URL` - URL do JIRA Cloud (ex: https://sua-empresa.atlassian.net)
   - `JIRA_EMAIL` - Email da conta Atlassian
   - `JIRA_API_TOKEN` - Token em [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)

## Execução

```bash
pip install -r requirements.txt
python scripts/extract_jira.py
```

## GitHub Actions

O workflow agendado executa a extração diariamente. Configure os secrets no repositório:
- `JIRA_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

## GitHub Pages

Configure o GitHub Pages nas Settings do repositório:
1. **Settings** > **Pages**
2. **Source**: Deploy from a branch
3. **Branch**: main, pasta **/ (root)**
4. Salvar

O dashboard ficará em `https://<usuario>.github.io/<repositorio>/` (redireciona para `/dashboard/`)
