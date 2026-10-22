import pytest
from pathlib import Path
from app.config import settings
from app.core.security import validate_safe_path, mask_secrets, is_safe_file_to_read, SecurityViolation
from app.core.parser import CodeParser
from app.core.vector_store import VectorIndex, CodeChunk
from app.core.indexer import RepositoryIndexer
from app.core.git_manager import GitManager
from app.core.dependency_analyzer import DependencyAnalyzer
from app.core.assistant_engine import AssistantEngine

def test_security_path_traversal():
    base = Path(__file__).resolve().parent.parent / "sample_repo"
    
    # Valid path
    valid = validate_safe_path(base, "calculator.py")
    assert valid.exists()
    
    # Malicious path traversal
    with pytest.raises(SecurityViolation):
        validate_safe_path(base, "../../Windows/System32/cmd.exe")

    with pytest.raises(SecurityViolation):
        validate_safe_path(base, "../../../etc/passwd")

def test_security_secret_masking():
    raw_code = 'OPENAI_API_KEY = "sk-1234567890abcdef1234567890abcdef"\npwd = "password:secret_password_123"'
    masked, count = mask_secrets(raw_code)
    assert count >= 1
    assert "sk-" not in masked or "[REDACTED" in masked

def test_tree_sitter_and_ast_parser():
    parser = CodeParser()
    code = """
def calculate_metric(a: int, b: int) -> int:
    \"\"\"Calculates test metric.\"\"\"
    return a * b + 10

class AnalyticsEngine:
    def run_job(self):
        return calculate_metric(2, 4)
"""
    res = parser.parse_code(code, "analytics.py")
    assert res.syntax_valid is True
    sym_names = [s.name for s in res.symbols]
    assert any("calculate_metric" in s for s in sym_names)
    assert any("AnalyticsEngine" in s for s in sym_names)

def test_indexer_and_vector_search():
    sample_dir = Path(__file__).resolve().parent.parent / "sample_repo"
    assert sample_dir.exists()

    indexer = RepositoryIndexer()
    summary = indexer.index_repository(sample_dir)
    assert summary["status"] == "success"
    assert summary["files_indexed"] >= 3
    assert summary["total_chunks"] >= 3

    # Test hybrid vector search
    results = indexer.vector_index.search("token authentication JWT", top_k=5)
    assert len(results) > 0
    top_file = results[0]["chunk"]["file_path"]
    assert "auth_service.py" in top_file

def test_dependency_analyzer():
    sample_dir = Path(__file__).resolve().parent.parent / "sample_repo"
    analyzer = DependencyAnalyzer(sample_dir)
    manifests = analyzer.analyze_manifests()
    assert "python_requirements" in manifests
    assert any(p["name"] == "fastapi" for p in manifests["python_requirements"])
    assert "node_package" in manifests

def test_patch_proposal_and_review():
    sample_dir = Path(__file__).resolve().parent.parent / "sample_repo"
    indexer = RepositoryIndexer()
    indexer.index_repository(sample_dir)
    git_mgr = GitManager(sample_dir)
    engine = AssistantEngine(indexer=indexer, git_mgr=git_mgr)

    # Propose patch
    patch = engine.propose_patch("Fix divide by zero in calculator.py")
    assert "diff --git" in patch["unified_diff"]
    assert "ValueError" in patch["unified_diff"] or "divide" in patch["unified_diff"]

    # Verify code review flags critical issues
    review = engine.review_code()
    assert review["total_findings"] >= 3
    assert review["critical_count"] >= 2  # SQLi, Secret, Token Exp
    titles = [f["title"] for f in review["findings"]]
    assert any("Hardcoded" in t for t in titles)
    assert any("SQL Injection" in t for t in titles)
