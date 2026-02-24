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
# JQL padrão: Jira Cloud exige consultas limitadas (ex: updated >= -90d)
JIRA_JQL_DEFAULT = os.getenv("JIRA_JQL_DEFAULT", "updated >= -90d ORDER BY updated DESC")
# Jira Cloud = api/3, Jira Server/Data Center = api/2
JIRA_API_VERSION = os.getenv("JIRA_API_VERSION", "3")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_auth():
    """Retorna tupla (email, token) para Basic Auth."""
    return (JIRA_EMAIL, JIRA_API_TOKEN)


def fetch_all_issues(jql: str | None = None, max_results: int = 1000) -> list:
    """Busca issues do JIRA usando JQL com paginação.
    Usa /rest/api/3/search/jql (novo endpoint - /search foi descontinuado e retorna 410).
    Jira Cloud exige JQL limitada (ex: updated >= -90d).
    """
    if jql is None:
        jql = JIRA_JQL_DEFAULT
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print("Erro: Configure JIRA_URL, JIRA_EMAIL e JIRA_API_TOKEN no .env")
        sys.exit(1)

    fields = "summary,status,issuetype,priority,assignee,project,created,updated"
    all_issues = []
    max_per_page = 100
    next_page_token = None

    # Jira Cloud: novo endpoint /search/jql (GET - mais estável que POST).
    # Ref: https://confluence.atlassian.com/jirakb/run-jql-search-query-using-jira-cloud-rest-api-1289424308.html
    if JIRA_API_VERSION == "3":
        url = f"{JIRA_URL}/rest/api/3/search/jql"
        while len(all_issues) < max_results:
            params = {
                "jql": jql,
                "maxResults": min(max_per_page, max_results - len(all_issues)),
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token
            resp = requests.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                auth=get_auth(),
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"Erro JIRA API: status {resp.status_code}")
                print(f"Resposta: {resp.text[:500]}")
                resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError:
                print(f"Resposta não é JSON: {resp.text[:200]!r}")
                raise
            issues = data.get("issues", [])
            all_issues.extend(issues)
            next_page_token = data.get("nextPageToken")
            if not next_page_token or not issues:
                break
    else:
        # Jira Server/Data Center: endpoint antigo /rest/api/2/search
        url = f"{JIRA_URL}/rest/api/2/search"
        start_at = 0
        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_per_page,
                "fields": fields,
            }
            resp = requests.get(url, params=params, headers=headers, auth=get_auth(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            issues = data.get("issues", [])
            all_issues.extend(issues)
            total = data.get("total", 0)
            if start_at + len(issues) >= total or len(issues) == 0 or len(all_issues) >= max_results:
                break
            start_at += len(issues)

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


def _ensure_bounded_jql(jql: str) -> str:
    """Adiciona restrição de data se a JQL for ilimitada (exigência do Jira Cloud)."""
    jql_lower = jql.lower()
    if any(x in jql_lower for x in ("updated", "created", "resolved")):
        return jql  # Já tem restrição de data
    return f"({jql}) AND updated >= -90d"


def fetch_filter_issues(filter_id: str) -> list:
    """Busca issues de um filtro personalizado."""
    jql = get_filter_jql(filter_id)
    if not jql:
        return []
    return fetch_all_issues(jql=_ensure_bounded_jql(jql), max_results=500)


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
