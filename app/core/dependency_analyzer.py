import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from app.core.security import validate_safe_path

# Curated knowledge base of common library explanations and purposes
LIBRARY_KNOWLEDGE_BASE = {
    "fastapi": {
        "purpose": "High-performance, async web framework for building APIs with Python 3.8+ using standard Python type hints.",
        "category": "Web Framework",
        "risk_level": "Low"
    },
    "pydantic": {
        "purpose": "Data validation and settings management using Python type annotations. Enforces data contracts and serializes models.",
        "category": "Data Validation",
        "risk_level": "Low"
    },
    "pyjwt": {
        "purpose": "JSON Web Token (JWT) encode and decode library for Python. Used for stateless bearer token authentication.",
        "category": "Authentication / Security",
        "risk_level": "Medium",
        "advisory": "Ensure token expiration ('exp') is verified and cryptographic algorithms are explicitly whitelisted (e.g. HS256/RS256)."
    },
    "sqlalchemy": {
        "purpose": "Database abstraction toolkit and Object Relational Mapper (ORM) for SQL databases.",
        "category": "Database / ORM",
        "risk_level": "Low",
        "advisory": "Always use parameterized queries or the ORM layer to prevent SQL injection."
    },
    "pytest": {
        "purpose": "Industry standard Python testing framework for writing simple and scalable unit, integration, and functional tests.",
        "category": "Testing",
        "risk_level": "Low"
    },
    "express": {
        "purpose": "Fast, unopinionated, minimalist web framework for Node.js.",
        "category": "Web Framework",
        "risk_level": "Low"
    },
    "axios": {
        "purpose": "Promise-based HTTP client for the browser and Node.js for making external API requests.",
        "category": "HTTP Client",
        "risk_level": "Low"
    },
    "jsonwebtoken": {
        "purpose": "Node.js implementation of JSON Web Tokens for authentication and session verification.",
        "category": "Authentication",
        "risk_level": "Medium"
    },
    "lodash": {
        "purpose": "JavaScript utility library delivering modularity, performance, and extras for arrays, numbers, and objects.",
        "category": "Utility",
        "risk_level": "Low",
        "advisory": "Ensure prototype pollution vulnerabilities in older lodash versions (<4.17.21) are patched."
    },
    "jest": {
        "purpose": "Delightful JavaScript testing framework with a focus on simplicity and automated test runners.",
        "category": "Testing",
        "risk_level": "Low"
    }
}

class DependencyAnalyzer:
    """
    Analyzes project dependencies, package manifests, intra-repo import graphs,
    circular dependencies, and provides human-readable explanations.
    """

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()

    def analyze_manifests(self) -> Dict[str, Any]:
        """Scans for requirements.txt, package.json, and pyproject.toml."""
        manifests = {}
        
        # Check requirements.txt
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            manifests["python_requirements"] = self._parse_requirements_txt(req_file)

        # Check package.json
        pkg_file = self.repo_path / "package.json"
        if pkg_file.exists():
            manifests["node_package"] = self._parse_package_json(pkg_file)

        return manifests

    def _parse_requirements_txt(self, path: Path) -> List[Dict[str, Any]]:
        dependencies = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    # Split version specifiers: ==, >=, <=, ~=, >
                    parts = re.split(r'(==|>=|<=|~=|>|<)', line)
                    pkg_name = parts[0].strip().lower()
                    version = "".join(parts[1:]).strip() if len(parts) > 1 else "unpinned (*)"
                    
                    info = LIBRARY_KNOWLEDGE_BASE.get(pkg_name, {
                        "purpose": "General software dependency/utility.",
                        "category": "Package",
                        "risk_level": "Low"
                    })
                    
                    is_unpinned = "==" not in version
                    dependencies.append({
                        "name": pkg_name,
                        "raw_spec": line,
                        "version": version,
                        "purpose": info["purpose"],
                        "category": info["category"],
                        "risk_level": "Medium" if is_unpinned else info["risk_level"],
                        "advisory": "Unpinned or loose version might cause breaking build changes." if is_unpinned else info.get("advisory", "")
                    })
        except Exception:
            pass
        return dependencies

    def _parse_package_json(self, path: Path) -> List[Dict[str, Any]]:
        dependencies = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})

            for name, ver in deps.items():
                info = LIBRARY_KNOWLEDGE_BASE.get(name.lower(), {
                    "purpose": "Node.js application dependency.",
                    "category": "Dependency",
                    "risk_level": "Low"
                })
                dependencies.append({
                    "name": name,
                    "version": ver,
                    "is_dev": False,
                    "purpose": info["purpose"],
                    "category": info["category"],
                    "risk_level": info["risk_level"],
                    "advisory": info.get("advisory", "")
                })

            for name, ver in dev_deps.items():
                info = LIBRARY_KNOWLEDGE_BASE.get(name.lower(), {
                    "purpose": "Development/testing dependency.",
                    "category": "DevDependency",
                    "risk_level": "Low"
                })
                dependencies.append({
                    "name": name,
                    "version": ver,
                    "is_dev": True,
                    "purpose": info["purpose"],
                    "category": info["category"],
                    "risk_level": info["risk_level"],
                    "advisory": info.get("advisory", "")
                })
        except Exception:
            pass
        return dependencies

    def build_intra_repo_graph(self, symbols_map: Dict[str, List[Any]]) -> Dict[str, Any]:
        """
        Builds intra-repository dependency call and import graph.
        Detects circular dependencies and produces nodes/edges for visual rendering.
        """
        nodes = []
        edges = []
        file_to_file: Dict[str, Set[str]] = {}

        # Initialize adjacency
        for file_path in symbols_map.keys():
            file_to_file[file_path] = set()
            nodes.append({
                "id": file_path,
                "label": Path(file_path).name,
                "path": file_path,
                "symbol_count": len(symbols_map[file_path])
            })

        # Scan imports across files
        all_modules = {Path(fp).stem: fp for fp in symbols_map.keys()}

        for file_path, symbols in symbols_map.items():
            for sym in symbols:
                # If symbol is an import
                kind = getattr(sym, 'kind', '') or (sym.get('kind', '') if isinstance(sym, dict) else '')
                name = getattr(sym, 'name', '') or (sym.get('name', '') if isinstance(sym, dict) else '')
                
                if kind == "import":
                    # Check if imported module matches an internal file
                    for mod_stem, target_fp in all_modules.items():
                        if mod_stem != Path(file_path).stem and (mod_stem in name or name.endswith(mod_stem)):
                            file_to_file[file_path].add(target_fp)
                            edges.append({
                                "source": file_path,
                                "target": target_fp,
                                "label": f"imports {mod_stem}"
                            })

        # Cycle detection (DFS)
        cycles = self._detect_cycles(file_to_file)

        return {
            "nodes": nodes,
            "edges": edges,
            "circular_dependencies": cycles,
            "has_cycles": len(cycles) > 0
        }

    def _detect_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        cycles = []
        visited = set()
        stack = []

        def dfs(node):
            if node in stack:
                cycle_start = stack.index(node)
                cycles.append(stack[cycle_start:] + [node])
                return
            if node in visited:
                return

            visited.add(node)
            stack.append(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor)
            stack.pop()

        for node in graph:
            if node not in visited:
                dfs(node)

        return cycles
