import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.security import validate_safe_path, SecurityViolation
from app.core.vector_store import VectorIndex
from app.core.indexer import RepositoryIndexer
from app.core.git_manager import GitManager
from app.core.assistant_engine import AssistantEngine
from app.models.schemas import (
    OpenRepoRequest,
    SearchRequest,
    TestSuggestionRequest,
    PatchProposeRequest,
    PatchApplyRequest,
    CodeReviewRequest,
    SettingsUpdateRequest
)

# Global instances
vector_store = VectorIndex()
indexer = RepositoryIndexer(vector_index=vector_store)
git_mgr = GitManager(settings.DEFAULT_REPO_PATH)
engine = AssistantEngine(indexer=indexer, git_mgr=git_mgr)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: auto-index default sample repo if it exists
    default_path = Path(settings.DEFAULT_REPO_PATH)
    if default_path.exists():
        try:
            indexer.index_repository(default_path)
            git_mgr.repo_path = default_path
            git_mgr._init_repo()
        except Exception as e:
            print(f"Startup auto-index warning: {e}")
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Repository-Aware Coding Assistant with Code RAG, AST Parsing, Git, and Safety Sandboxing",
    lifespan=lifespan
)

# Enable CORS for local dev flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def root():
    """Serves the Glassmorphic Single Page Application."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Welcome to RepoPulse API", "docs": "/docs"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "is_indexed": indexer.is_indexed,
        "repo_path": str(indexer.repo_path) if indexer.repo_path else None
    }

@app.post("/api/repo/open")
async def open_repository(req: OpenRepoRequest):
    """Opens and indexes a repository directory safely."""
    try:
        p = Path(req.repo_path).resolve()
        if not p.exists() or not p.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Directory '{req.repo_path}' does not exist or is not a directory."
            )

        # Update Git manager
        git_mgr.repo_path = p
        git_mgr._init_repo()

        # Run indexer
        summary = indexer.index_repository(p)
        git_status = git_mgr.get_repo_status()
        summary["git_status"] = git_status

        return summary
    except SecurityViolation as sv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sv))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/repo/index")
async def reindex_repository():
    """Triggers re-indexing of the currently open repository."""
    if not indexer.repo_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No repository currently loaded.")

    try:
        summary = indexer.index_repository(indexer.repo_path)
        return summary
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/repo/tree")
async def get_repository_tree():
    """Returns the directory tree of the open repository."""
    if not indexer.repo_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No repository currently loaded.")

    tree = indexer.get_file_tree(indexer.repo_path)
    return tree

@app.get("/api/repo/file")
async def get_repository_file(path: str = Query(..., description="Repository-relative file path")):
    """Safely reads file contents with secret masking and line metadata."""
    if not indexer.repo_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No repository currently loaded.")

    try:
        file_data = indexer.read_file_safe(path)
        return file_data
    except SecurityViolation as sv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(sv))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.post("/api/search")
async def search_code(req: SearchRequest):
    """Executes hybrid vector and symbol code search."""
    if not indexer.is_indexed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository not indexed yet.")

    results = engine.search_code(
        query=req.query,
        top_k=req.top_k,
        symbol_type=req.symbol_type,
        file_filter=req.file_filter
    )
    return {"query": req.query, "count": len(results), "results": results}

@app.get("/api/dependencies")
async def get_dependencies():
    """Returns dependency explanations and the intra-repository call graph."""
    if not indexer.is_indexed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository not indexed yet.")

    return engine.explain_dependencies()

@app.post("/api/tests/suggest")
async def suggest_tests(req: TestSuggestionRequest):
    """Suggests unit test cases with exact file and line references."""
    if not indexer.is_indexed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository not indexed yet.")

    return engine.suggest_tests(file_path=req.file_path, symbol_name=req.symbol_name)

@app.post("/api/patch/propose")
async def propose_patch(req: PatchProposeRequest):
    """Proposes a code patch with unified diff and line references."""
    return engine.propose_patch(issue_description=req.issue_description, target_file=req.target_file)

@app.post("/api/patch/apply")
async def apply_patch(req: PatchApplyRequest):
    """Applies or dry-runs a unified diff patch."""
    return git_mgr.apply_patch(patch_content=req.patch_content, dry_run=req.dry_run)

@app.post("/api/review")
async def review_code(req: CodeReviewRequest):
    """Performs automated code review with exact file and line references."""
    if not indexer.is_indexed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository not indexed yet.")

    return engine.review_code(file_path=req.file_path)

@app.get("/api/git/status")
async def get_git_status():
    """Returns current git branch, dirty status, and changed files."""
    return git_mgr.get_repo_status()

@app.get("/api/git/diff")
async def get_git_diff(staged: bool = False, file: Optional[str] = None):
    """Returns git diff."""
    diff_text = git_mgr.get_diff(staged=staged, file_path=file)
    return {"diff": diff_text}

@app.get("/api/git/history")
async def get_git_history(limit: int = 15):
    """Returns recent git commit history."""
    return {"commits": git_mgr.get_commit_history(max_count=limit)}

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Configures LLM provider and API keys."""
    engine.set_api_key(req.provider, req.api_key or "")
    return {
        "status": "success",
        "provider": req.provider,
        "has_key": bool(req.api_key and len(req.api_key) > 5)
    }
