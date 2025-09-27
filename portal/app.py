import os
import time
from functools import wraps
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, abort
import requests
import socket
from pathlib import Path
import json

app = Flask(__name__)

PORTAL_AUTH_TOKEN = os.environ.get("PORTAL_AUTH_TOKEN", "")

JIRA_URL = (os.environ.get("JIRA_URL") or "").rstrip("/")
JIRA_USER = os.environ.get("JIRA_USER", "")
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "OPS")
JIRA_ISSUE_TYPE = os.environ.get("JIRA_ISSUE_TYPE", "Task")

GITLAB_URL = (os.environ.get("GITLAB_URL") or "").rstrip("/")
GITLAB_PROJECT_ID = os.environ.get("GITLAB_PROJECT_ID", "")
GITLAB_REF = os.environ.get("GITLAB_REF", "main")
GITLAB_TRIGGER_TOKEN = os.environ.get("GITLAB_TRIGGER_TOKEN", "")
GITLAB_API_TOKEN = os.environ.get("GITLAB_API_TOKEN", "")

GRAFANA_URL = (os.environ.get("GRAFANA_URL") or "https://grafana.feebee.ru").rstrip("/")

MONITOR_TARGETS = os.environ.get("MONITOR_TARGETS", "").strip()

ENV_NAME = os.environ.get("ENV_NAME", "Prod")
APP_VERSION = os.environ.get("APP_VERSION") or os.environ.get("CI_COMMIT_SHORT_SHA") or "dev"

STARTED_AT = datetime.now(timezone.utc)

REPORTS_DIR = Path("/opt/portal/static/reports")


def require_token(f):
    @wraps(f)
    def w(*a, **kw):
        sent = request.headers.get("X-Portal-Token") or request.args.get("token")
        if PORTAL_AUTH_TOKEN and sent != PORTAL_AUTH_TOKEN:
            return jsonify({"error": "unauthorized: bad token"}), 401
        return f(*a, **kw)
    return w


def ensure_gitlab_config():
    missing = []
    if not GITLAB_URL:
        missing.append("GITLAB_URL")
    if not GITLAB_PROJECT_ID:
        missing.append("GITLAB_PROJECT_ID")
    if not GITLAB_TRIGGER_TOKEN:
        missing.append("GITLAB_TRIGGER_TOKEN")
    if missing:
        raise RuntimeError(f"GitLab is not configured: missing {', '.join(missing)}")


def create_jira(summary: str, desc: str) -> str:
    if not (JIRA_URL and JIRA_TOKEN and JIRA_PROJECT):
        return "JIRA_DISABLED"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT},
            "summary": summary,
            "description": desc,
            "issuetype": {"name": JIRA_ISSUE_TYPE},
        }
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JIRA_TOKEN}"
    }

    try:
        r = requests.post(
            f"{JIRA_URL}/rest/api/2/issue",
            json=payload,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()

        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json().get("key") or "JIRA_OK"
        return "JIRA_OK"

    except requests.exceptions.RequestException as e:
        print(f"JIRA API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return "JIRA_ERROR"


def trigger_pipeline(action: str, extra: dict | None = None) -> tuple[int | None, str | None]:
    ensure_gitlab_config()
    url = f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/trigger/pipeline"
    data = {"token": GITLAB_TRIGGER_TOKEN, "ref": GITLAB_REF, "variables[PORTAL_ACTION]": action}
    for k, v in (extra or {}).items():
        data[f"variables[{k}]"] = v
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    try:
        js = r.json()
    except Exception:
        js = {}
    return js.get("id"), js.get("web_url")


def parse_targets() -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if MONITOR_TARGETS:
        for raw in MONITOR_TARGETS.split(","):
            if "|" in raw:
                name, target = raw.split("|", 1)
                items.append((name.strip(), target.strip()))
        if JIRA_URL:
            items.append(("Jira", JIRA_URL))
        if GITLAB_URL:
            items.append(("GitLab", GITLAB_URL))
        items.append(("Grafana", "https://grafana.feebee.ru"))
        items.append(("Portal API", "https://portal.feebee.ru/health"))
    else:
        if JIRA_URL:
            items.append(("Jira", JIRA_URL))
        if GITLAB_URL:
            items.append(("GitLab", GITLAB_URL))
        items.append(("Grafana", "https://grafana.feebee.ru"))
        items.append(("Portal API", "https://portal.feebee.ru/health"))
    return items


def ping_http(url: str, timeout: float = 3.0) -> dict:
    t0 = time.perf_counter()
    try:
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True)
            code = r.status_code
            if code >= 400:
                r = requests.get(url, timeout=timeout, allow_redirects=True)
                code = r.status_code
        except requests.RequestException:
            r = requests.get(url, timeout=timeout, allow_redirects=True)
            code = r.status_code

        ms = int((time.perf_counter() - t0) * 1000)
        return {"up": code < 500, "status": code, "ms": ms}
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return {"up": False, "status": str(e), "ms": ms}


def ping_tcp(host: str, port: int, timeout: float = 2.0) -> dict:
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = int((time.perf_counter() - t0) * 1000)
            return {"up": True, "status": "open", "ms": ms}
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return {"up": False, "status": str(e), "ms": ms}


@app.get("/api/status")
def api_status():
    services = []
    for name, target in parse_targets():
        result = {"up": False, "status": "n/a", "ms": None}
        if target.startswith("tcp://"):
            u = urlparse(target)
            host = u.hostname or ""
            port = u.port or 0
            result = ping_tcp(host, port)
        elif target.startswith("http://") or target.startswith("https://"):
            result = ping_http(target)
        else:
            if ":" in target and target.split(":")[-1].isdigit():
                host, p = target.rsplit(":", 1)
                result = ping_tcp(host, int(p))
            else:
                result = ping_http("http://" + target)

        services.append({"name": name, "target": target, **result})

    gl = None
    if GITLAB_API_TOKEN and GITLAB_URL and GITLAB_PROJECT_ID:
        try:
            headers = {"PRIVATE-TOKEN": GITLAB_API_TOKEN}
            url = f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/pipelines?per_page=1"
            r = requests.get(url, headers=headers, timeout=5)
            if r.ok and isinstance(r.json(), list) and r.json():
                p = r.json()[0]
                gl = {
                    "id": p.get("id"),
                    "status": p.get("status"),
                    "ref": p.get("ref"),
                    "sha": p.get("sha"),
                    "web_url": p.get("web_url"),
                }
        except Exception:
            gl = {"error": "gitlab_api_unavailable"}

    return jsonify({
        "ok": True,
        "env": ENV_NAME,
        "version": APP_VERSION,
        "services": services,
        "gitlab": gl
    })


@app.get("/")
def index():
    return render_template(
        "index.html",
        title="DevOps Portal",
        env_name=ENV_NAME,
        gitlab_url=GITLAB_URL,
        gitlab_project_id=GITLAB_PROJECT_ID,
        version=APP_VERSION,
    )


@app.get("/health")
def health():
    now = datetime.now(timezone.utc)
    return jsonify({
        "ok": True,
        "env": ENV_NAME,
        "version": APP_VERSION,
        "now": now.isoformat(),
        "started": STARTED_AT.isoformat(),
        "uptime_sec": int((now - STARTED_AT).total_seconds()),
    })


@app.get("/ops/disk")
def ops_disk():
    files = sorted(REPORTS_DIR.glob("check_disk_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)

    if request.args.get("check"):
        return ("", 200) if files else abort(404, "Report not ready")

    if not files:
        abort(404, "Report not found yet. Run the check first")

    data = json.loads(files[0].read_text(encoding="utf-8"))
    df_text = data.get("df", "")
    docker_text = data.get("docker_df", "")
    ts = data.get("generated_at", "")

    headers, rows = [], []
    lines = df_text.splitlines()
    if lines:
        headers = lines[0].split()
        for line in lines[1:]:
            if line.strip():
                rows.append(line.split())

    return render_template("ops_disk.html",
                           ts=ts, headers=headers, rows=rows,
                           docker_info=docker_text, raw_df=df_text)


@app.post("/run/<action>")
@require_token
def run_action(action):
    actions = {
        "restart_jira":      ("Restart Jira",    "Перезапуск контейнера Jira",     {"HOST": "jira.feebee.ru"}),
        "restart_portal":    ("Restart Portal",  "Перезапуск контейнера портала",  {"HOST": "portal.feebee.ru"}),
        "backup_portal":     ("Backup Portal",   "Запрошен бэкап портала",         {"HOST": "portal.feebee.ru"}),
        "check_disk":        ("Check Disk Portal", "Проверка места на портале",     {"HOST": "portal.feebee.ru"}),
    }
    item = actions.get(action)
    if not item:
        return jsonify({"error": "unknown action"}), 400

    summary, desc, extra = item

    issue = "N/A"
    try:
        issue = create_jira(summary, desc)
    except Exception:
        issue = "JIRA_FAILED"

    try:
        pid, web = trigger_pipeline(action, extra)
    except Exception as e:
        return jsonify({"error": f"gitlab trigger failed: {e}", "jira": issue}), 500

    return jsonify({"ok": True, "jira": issue, "pipeline_id": pid, "pipeline_url": web})


if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)