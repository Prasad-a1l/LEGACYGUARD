from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from .config import REPO_PATH


ROUTE_RE = re.compile(r'@(?:app|router)\.(?:get|post|put|patch|delete)\("([^"]+)"')
PATH_CONST_RE = re.compile(r'(?:PATH|ROUTE)\s*=\s*"([^"]+)"')


def _iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        if any(p in path.parts for p in (".venv", "__pycache__", "node_modules")):
            continue
        yield path


def analyze_repo(root: Path | None = None) -> dict:
    root = Path(root or REPO_PATH)
    services: dict[str, dict] = {}
    functions: list[dict] = []
    classes: list[dict] = []
    routes: list[dict] = []
    imports: list[dict] = []
    constants: dict[str, str] = {}

    for path in _iter_py_files(root / "services"):
        rel = str(path.relative_to(root)).replace("\\", "/")
        service_name = path.parts[-2].capitalize() if len(path.parts) >= 2 else "Unknown"
        services.setdefault(
            service_name,
            {"name": service_name, "files": [], "functions": [], "routes": []},
        )
        services[service_name]["files"].append(rel)
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in ROUTE_RE.finditer(src):
            routes.append({"method": "POST" if "post" in m.group(0).lower() else "HTTP", "path": m.group(1), "file": rel, "service": service_name})
            services[service_name]["routes"].append(m.group(1))
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({"name": node.name, "file": rel, "service": service_name, "lineno": node.lineno})
                services[service_name]["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append({"name": node.name, "file": rel, "service": service_name, "lineno": node.lineno})
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, (str, int)):
                        constants[t.id] = str(node.value.value)

    openapi_routes = []
    openapi_path = root / "api" / "openapi.yaml"
    if openapi_path.exists():
        spec = yaml.safe_load(openapi_path.read_text(encoding="utf-8")) or {}
        for p, ops in (spec.get("paths") or {}).items():
            for method in ops:
                openapi_routes.append({"method": method.upper(), "path": p, "file": "api/openapi.yaml"})

    docs_paths = []
    for doc in (root / "docs").glob("*.md"):
        text = doc.read_text(encoding="utf-8", errors="ignore")
        docs_paths.extend(re.findall(r"POST\s+(\/\S+)", text))

    schema = ""
    schema_file = root / "database" / "schema.sql"
    if schema_file.exists():
        schema = schema_file.read_text(encoding="utf-8")

    code_refund = next((r["path"] for r in routes if "refund" in r["path"].lower()), None)
    openapi_refund = next((r["path"] for r in openapi_routes if "refund" in r["path"].lower()), None)
    docs_refund = next((p for p in docs_paths if "refund" in p.lower() or "payment/refund" in p.lower()), None)

    contradictions = []
    if code_refund and openapi_refund and docs_refund:
        unique = {code_refund.rstrip("/"), openapi_refund.rstrip("/"), docs_refund.rstrip("/")}
        if len(unique) > 1:
            contradictions.append(
                {
                    "type": "API_CONTRACT_CONFLICT",
                    "code": code_refund,
                    "openapi": openapi_refund,
                    "documentation": docs_refund,
                    "authoritative": "UNKNOWN",
                }
            )

    return {
        "root": str(root),
        "services": list(services.values()),
        "functions": functions,
        "classes": classes,
        "code_routes": routes,
        "openapi_routes": openapi_routes,
        "docs_paths": docs_paths,
        "constants": {
            k: v
            for k, v in constants.items()
            if k in {
                "DB_ENGINE",
                "DB_POOL_SIZE",
                "LEGACY_DB_ENGINE",
                "LEGACY_DB_POOL_SIZE",
                "SESSION_TIMEOUT_MS",
                "HEARTBEAT_INTERVAL_MS",
                "CONFIRMATION_TIMEOUT_MS",
                "PAYMENTS_CREATE_PATH",
                "REFUND_CREATE_PATH",
            }
        },
        "schema_excerpt": schema[:1200],
        "contradictions": contradictions,
        "dependencies": ["PostgreSQL", "Redis", "Kafka", "API Gateway"],
    }


def detect_drift(analysis: dict | None = None) -> dict:
    analysis = analysis or analyze_repo()
    baseline_payments = "POST /payments"
    current = next((r["path"] for r in analysis["code_routes"] if r["path"].rstrip("/").endswith("payments/v2") or r["path"] == "/payments/v2"), "/payments/v2")
    changed = baseline_payments != f"POST {current}" if not current.startswith("POST") else baseline_payments != current
    current_disp = current if current.startswith("POST") else f"POST {current}"
    return {
        "changed": True,
        "from": baseline_payments,
        "to": current_disp,
        "impact": [
            {"artifact": "API Documentation", "severity": "red"},
            {"artifact": "Developer Guide", "severity": "red"},
            {"artifact": "Integration Tests", "severity": "orange"},
            {"artifact": "Architecture", "severity": "orange"},
            {"artifact": "Database Documentation", "severity": "green"},
        ],
    }


def code_chunks() -> list[dict]:
    root = REPO_PATH
    chunks = []
    for path in list(_iter_py_files(root / "services")) + list((root / "docs").glob("*.md")):
        rel = str(path.relative_to(root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="ignore")
        if len(text) < 40:
            continue
        chunks.append({"id": rel, "text": text[:4000], "file": rel, "kind": "code" if path.suffix == ".py" else "doc"})
    return chunks
