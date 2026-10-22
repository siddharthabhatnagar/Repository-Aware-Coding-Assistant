from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class OpenRepoRequest(BaseModel):
    repo_path: str = Field(..., description="Absolute or relative path to the local repository directory")

class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language or code symbol search query")
    top_k: int = Field(8, ge=1, le=50, description="Maximum number of code snippets to return")
    symbol_type: Optional[str] = Field("all", description="Filter by symbol type (function, class, method, import, all)")
    file_filter: Optional[str] = Field(None, description="Optional path substring filter")

class TestSuggestionRequest(BaseModel):
    file_path: str = Field(..., description="Repository-relative path of the target code file")
    symbol_name: Optional[str] = Field(None, description="Optional specific function or class name")

class PatchProposeRequest(BaseModel):
    issue_description: str = Field(..., description="Description of the bug or improvement")
    target_file: Optional[str] = Field(None, description="Target file name or path")

class PatchApplyRequest(BaseModel):
    patch_content: str = Field(..., description="Unified diff patch text")
    dry_run: bool = Field(True, description="When true, only verifies whether the patch applies cleanly without modifying files")

class CodeReviewRequest(BaseModel):
    file_path: Optional[str] = Field(None, description="Specific file to review, or omit to review all indexed repository files")

class SettingsUpdateRequest(BaseModel):
    provider: str = Field(..., description="LLM provider name: 'openai', 'groq', 'gemini', or 'local'")
    api_key: Optional[str] = Field(None, description="Optional API key for the provider")
