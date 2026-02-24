#!/usr/bin/env python3
"""
Script de extração de dados do JIRA Cloud.
Extrai issues e dados de filtros personalizados via JIRA REST API v3.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()


def _normalize_jira_url(url: str) -> str:
    """Extrai apenas a base da URL (scheme + host) para a API."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    parsed = urlparse(url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc or parsed.path.split('/')[0]}"
    return base.rstrip("/")


# Configuração
JIRA_URL = _normalize_jira_url(os.getenv("JIRA_URL", ""))
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_FILTER_IDS = os.getenv("JIRA_FILTER_IDS", "")
# Jira Cloud = api/3, Jira Server/Data Center = api/2
JIRA_API_VERSION = os.getenv("JIRA_API_VERSION", "3")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_auth():
    """Retorna tupla (email, token) para Basic Auth."""
    return (JIRA_EMAIL, JIRA_API_TOKEN)


def fetch_all_issues(jql: str = "order by updated DESC", max_results: int = 1000) -> list:
    """Busca issues do JIRA usando JQL com paginação."""
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("Erro: Configure JIRA_URL, JIRA_EMAIL e JIRA_API_TOKEN no .env")
        sys.exit(1)

    url = f"{JIRA_URL}/rest/api/{JIRA_API_VERSION}/search"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    all_issues = []
    start_at = 0
    max_per_page = 100

    while True:
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_per_page,
            "fields": "summary,status,issuetype,priority,assignee,project,created,updated",
        }
        resp = requests.get(
            url,
            params=params,
            headers=headers,
            auth=get_auth(),
            timeout=30,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print(f"Erro: a API do JIRA retornou algo que não é JSON.")
            print(f"Status HTTP: {resp.status_code}")
            print(f"Resposta (início): {resp.text[:300]!r}")
            print("Dica: Verifique JIRA_URL (ex: https://sua-empresa.atlassian.net) e credenciais.")
            raise
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("total", 0)
        if start_at + len(issues) >= total or len(issues) == 0:
            break
        start_at += len(issues)
        if len(all_issues) >= max_results:
            break

    return all_issues[:max_results]


def get_filter_jql(filter_id: str) -> str | None:
    """Obtém a JQL de um filtro pelo ID."""
    url = f"{JIRA_URL}/rest/api/{JIRA_API_VERSION}/filter/{filter_id}"
    headers = {"Accept": "application/json"}
    resp = requests.get(url, headers=headers, auth=get_auth(), timeout=30)
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get("jql")


def fetch_filter_issues(filter_id: str) -> list:
    """Busca issues de um filtro personalizado."""
    jql = get_filter_jql(filter_id)
    if not jql:
        return []
    return fetch_all_issues(jql=jql, max_results=500)


def normalize_issue(issue: dict) -> dict:
    """Normaliza uma issue para o formato do dashboard."""
    fields = issue.get("fields", {})
    status = fields.get("status") or {}
    issuetype = fields.get("issuetype") or {}
    priority = fields.get("priority") or {}
    assignee = fields.get("assignee") or {}
    project = fields.get("project") or {}

    return {
        "key": issue.get("key", ""),
        "summary": fields.get("summary", ""),
        "status": status.get("name", "Unknown"),
        "issuetype": issuetype.get("name", "Unknown"),
        "priority": priority.get("name", "None"),
        "assignee": assignee.get("displayName", "Unassigned"),
        "project": project.get("key", ""),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "url": f"{JIRA_URL}/browse/{issue.get('key', '')}",
    }


def aggregate_for_dashboard(issues: list) -> dict:
    """Agrega issues para os gráficos do dashboard."""
    by_status = {}
    by_type = {}
    by_assignee = {}
    by_priority = {}

    for issue in issues:
        status = issue.get("status", "Unknown")
        issuetype = issue.get("issuetype", "Unknown")
        assignee = issue.get("assignee", "Unassigned")
        priority = issue.get("priority", "None")

        by_status[status] = by_status.get(status, 0) + 1
        by_type[issuetype] = by_type.get(issuetype, 0) + 1
        by_assignee[assignee] = by_assignee.get(assignee, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1

    return {
        "by_status": by_status,
        "by_type": by_type,
        "by_assignee": by_assignee,
        "by_priority": by_priority,
        "total": len(issues),
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Buscar issues gerais (últimas atualizadas)
    print("Extraindo issues do JIRA...")
    issues = fetch_all_issues()

    # 2. Buscar issues de filtros personalizados
    filter_ids = [fid.strip() for fid in JIRA_FILTER_IDS.split(",") if fid.strip()]
    filter_results = {}
    for fid in filter_ids:
        print(f"Extraindo filtro {fid}...")
        filter_issues = fetch_filter_issues(fid)
        filter_results[fid] = [normalize_issue(i) for i in filter_issues]

    # 3. Normalizar e agregar
    normalized = [normalize_issue(i) for i in issues]
    aggregates = aggregate_for_dashboard(normalized)

    # 4. Salvar JSONs
    output = {
        "issues": normalized,
        "aggregates": aggregates,
        "last_updated": issues[0].get("fields", {}).get("updated", "") if issues else datetime.utcnow().isoformat() + "Z",
    }
    issues_path = DATA_DIR / "issues.json"
    with open(issues_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Salvo: {issues_path} ({len(normalized)} issues)")

    filters_output = {
        "filters": {fid: {"issues": data, "count": len(data)} for fid, data in filter_results.items()},
    }
    filters_path = DATA_DIR / "filters.json"
    with open(filters_path, "w", encoding="utf-8") as f:
        json.dump(filters_output, f, ensure_ascii=False, indent=2)
    print(f"Salvo: {filters_path}")


if __name__ == "__main__":
    main()
