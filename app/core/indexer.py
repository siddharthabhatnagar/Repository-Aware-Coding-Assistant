import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.core.security import validate_safe_path, is_safe_file_to_read, mask_secrets, SecurityViolation
from app.core.parser import CodeParser, ParseResult, CodeSymbol
from app.core.vector_store import VectorIndex, CodeChunk

class RepositoryIndexer:
    """
    Code-aware repository indexer: structural AST chunking,
    safe handling of untrusted files, secret detection, and vector indexing.
    """

    def __init__(self, vector_index: Optional[VectorIndex] = None):
        self.parser = CodeParser()
        self.vector_index = vector_index or VectorIndex()
        self.indexed_files: Dict[str, Dict[str, Any]] = {}
        self.symbols_map: Dict[str, List[CodeSymbol]] = {}
        self.security_findings: List[Dict[str, Any]] = []
        self.repo_path: Optional[Path] = None
        self.is_indexed: bool = False

    def get_file_tree(self, root_path: str | Path) -> Dict[str, Any]:
        """
        Builds a safe hierarchical tree of files in the repository.
        Excludes ignored directories (.git, node_modules, etc.).
        """
        root = Path(root_path).resolve()
        
        def build_node(current_path: Path) -> Dict[str, Any]:
            rel_path = current_path.relative_to(root).as_posix() if current_path != root else ""
            if current_path.is_dir():
                children = []
                try:
                    for item in sorted(current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        if item.name in settings.IGNORE_DIRS:
                            continue
                        # Prevent traversal or symlink loops
                        try:
                            valid_p = validate_safe_path(root, item)
                            children.append(build_node(valid_p))
                        except SecurityViolation:
                            continue
                except PermissionError:
                    pass

                return {
                    "name": current_path.name if current_path != root else root.name,
                    "path": rel_path or ".",
                    "type": "directory",
                    "children": children
                }
            else:
                safe, reason = is_safe_file_to_read(current_path, settings.MAX_FILE_SIZE_BYTES)
                return {
                    "name": current_path.name,
                    "path": rel_path,
                    "type": "file",
                    "extension": current_path.suffix.lower(),
                    "size": current_path.stat().st_size if current_path.exists() else 0,
                    "is_safe": safe,
                    "safe_reason": reason
                }

        return build_node(root)

    def read_file_safe(self, rel_path: str) -> Dict[str, Any]:
        """
        Safely reads a repository file with bounds checking and secret masking.
        """
        if not self.repo_path:
            raise ValueError("Repository path not set. Index or open a repository first.")

        safe_path = validate_safe_path(self.repo_path, rel_path)
        is_safe, reason = is_safe_file_to_read(safe_path, settings.MAX_FILE_SIZE_BYTES)
        if not is_safe:
            raise SecurityViolation(f"Cannot read file '{rel_path}': {reason}")

        try:
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read(settings.MAX_FILE_LINES * 200)

            masked_content, redacted_count = mask_secrets(raw_content)
            lines = masked_content.splitlines()

            # Retrieve symbols if available
            symbols = [s.__dict__ for s in self.symbols_map.get(rel_path, [])]

            return {
                "file_path": rel_path,
                "content": masked_content,
                "total_lines": len(lines),
                "redacted_secrets": redacted_count,
                "symbols": symbols,
                "language": CodeParser.detect_language(safe_path)
            }
        except Exception as e:
            raise RuntimeError(f"Error reading file '{rel_path}': {str(e)}")

    def index_repository(self, repo_path: str | Path) -> Dict[str, Any]:
        """
        Full repository indexing pipeline:
        1. Tree walk with safety filters
        2. AST extraction of symbols & lines
        3. Structural chunking
        4. FAISS vector store embedding
        """
        self.repo_path = Path(repo_path).resolve()
        self.vector_index.clear()
        self.indexed_files.clear()
        self.symbols_map.clear()
        self.security_findings.clear()

        all_chunks: List[CodeChunk] = []
        total_loc = 0
        lang_counts: Dict[str, int] = {}
        processed_files = 0

        for root, dirs, files in os.walk(self.repo_path):
            # Exclude ignored directories in-place
            dirs[:] = [d for d in dirs if d not in settings.IGNORE_DIRS]

            for fname in files:
                if processed_files >= settings.MAX_REPO_FILES:
                    break

                file_path = Path(root) / fname
                try:
                    safe_path = validate_safe_path(self.repo_path, file_path)
                except SecurityViolation:
                    continue

                rel_path = safe_path.relative_to(self.repo_path).as_posix()
                ext = safe_path.suffix.lower()

                # Safety check
                is_safe, reason = is_safe_file_to_read(safe_path, settings.MAX_FILE_SIZE_BYTES)
                if not is_safe:
                    continue

                if ext not in settings.SUPPORTED_EXTENSIONS and fname not in ("Dockerfile", "Makefile"):
                    continue

                try:
                    with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_code = f.read()
                except Exception:
                    continue

                # Check for secrets
                masked_code, redacted_count = mask_secrets(raw_code)
                if redacted_count > 0:
                    self.security_findings.append({
                        "file_path": rel_path,
                        "type": "hardcoded_secret",
                        "severity": "CRITICAL",
                        "description": f"Found {redacted_count} potential hardcoded secret(s) / credential(s).",
                        "masked": True
                    })

                # AST Parse
                parse_res: ParseResult = self.parser.parse_code(masked_code, safe_path)
                lines = masked_code.splitlines()
                total_loc += len(lines)
                processed_files += 1

                lang = parse_res.language
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
                self.symbols_map[rel_path] = parse_res.symbols

                # Create structural chunks
                if parse_res.symbols:
                    for sym in parse_res.symbols:
                        chunk_id = f"{rel_path}#{sym.name}:{sym.start_line}-{sym.end_line}"
                        summary = f"{sym.kind.upper()} {sym.name}"
                        if sym.docstring:
                            summary += f": {sym.docstring[:150]}"
                        if sym.calls:
                            summary += f" [Calls: {', '.join(sym.calls[:5])}]"

                        all_chunks.append(CodeChunk(
                            chunk_id=chunk_id,
                            file_path=rel_path,
                            symbol_name=sym.name,
                            symbol_type=sym.kind,
                            start_line=sym.start_line,
                            end_line=sym.end_line,
                            content=sym.code,
                            summary=summary,
                            language=lang,
                            metadata={"calls": sym.calls, "parent": sym.parent}
                        ))
                else:
                    # Non-AST or text file chunking (e.g. JSON or Markdown)
                    chunk_id = f"{rel_path}#full:1-{len(lines)}"
                    preview = "\n".join(lines[:60])
                    all_chunks.append(CodeChunk(
                        chunk_id=chunk_id,
                        file_path=rel_path,
                        symbol_name=Path(rel_path).name,
                        symbol_type="file",
                        start_line=1,
                        end_line=len(lines),
                        content=preview,
                        summary=f"Full content of {rel_path}",
                        language=lang
                    ))

                self.indexed_files[rel_path] = {
                    "lines": len(lines),
                    "symbols": len(parse_res.symbols),
                    "language": lang,
                    "syntax_valid": parse_res.syntax_valid
                }

        # Embed all chunks into FAISS
        self.vector_index.add_chunks(all_chunks)
        self.is_indexed = True

        return {
            "status": "success",
            "repo_path": str(self.repo_path),
            "files_indexed": processed_files,
            "total_lines_of_code": total_loc,
            "total_symbols": sum(len(syms) for syms in self.symbols_map.values()),
            "total_chunks": len(all_chunks),
            "languages": lang_counts,
            "security_alerts": len(self.security_findings)
        }
