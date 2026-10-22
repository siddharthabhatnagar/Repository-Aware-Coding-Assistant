import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from tree_sitter import Language, Parser
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjs
    import tree_sitter_typescript as tstypescript
    
    PY_PARSER = Parser(Language(tspython.language()))
    JS_PARSER = Parser(Language(tsjs.language()))
    TS_PARSER = Parser(Language(tstypescript.language_typescript()))
    TSX_PARSER = Parser(Language(tstypescript.language_tsx()))
    HAS_TREE_SITTER = True
except Exception as e:
    HAS_TREE_SITTER = False
    PY_PARSER = None
    JS_PARSER = None
    TS_PARSER = None
    TSX_PARSER = None

@dataclass
class CodeSymbol:
    name: str
    kind: str  # 'function', 'class', 'method', 'import', 'constant'
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    signature: str = ""
    docstring: str = ""
    code: str = ""
    parent: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)

@dataclass
class ParseResult:
    language: str
    symbols: List[CodeSymbol]
    imports: List[str]
    syntax_valid: bool = True
    error_message: Optional[str] = None
    total_lines: int = 0

class CodeParser:
    """
    Code parser using Tree-Sitter with Python AST and regex fallbacks.
    Extracts structural code symbols, call relationships, and line bounds.
    """

    @staticmethod
    def detect_language(file_path: str | Path) -> str:
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".json": "json",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".md": "markdown",
            ".sh": "bash",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".toml": "toml",
        }
        return mapping.get(ext, "text")

    def parse_code(self, code: str, file_path: str | Path) -> ParseResult:
        lang = self.detect_language(file_path)
        lines = code.splitlines()
        total_lines = len(lines)

        if lang == "python":
            return self._parse_python(code, lines)
        elif lang in ("javascript", "typescript", "tsx") and HAS_TREE_SITTER:
            return self._parse_tree_sitter_js_ts(code, lines, lang)
        else:
            return self._parse_generic_regex(code, lines, lang)

    def _parse_python(self, code: str, lines: List[str]) -> ParseResult:
        """Parses Python code using tree-sitter, falling back to python ast."""
        if HAS_TREE_SITTER and PY_PARSER:
            try:
                tree = PY_PARSER.parse(code.encode("utf-8"))
                if not tree.root_node.has_error:
                    return self._extract_from_tree_sitter_python(tree.root_node, code, lines)
            except Exception:
                pass  # Fall through to ast
                
        # Built-in Python AST fallback
        try:
            tree = ast.parse(code)
            return self._extract_from_ast_python(tree, code, lines)
        except SyntaxError as e:
            return ParseResult(
                language="python",
                symbols=[],
                imports=[],
                syntax_valid=False,
                error_message=f"SyntaxError at line {e.lineno}: {e.msg}",
                total_lines=len(lines)
            )

    def _extract_from_tree_sitter_python(self, root_node, code: str, lines: List[str]) -> ParseResult:
        symbols: List[CodeSymbol] = []
        imports: List[str] = []

        def get_node_text(node) -> str:
            return code.encode("utf-8")[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def walk(node, parent_name=None):
            nonlocal imports
            node_type = node.type
            
            if node_type == "import_statement" or node_type == "import_from_statement":
                text = get_node_text(node).strip()
                imports.append(text)
                symbols.append(CodeSymbol(
                    name=text,
                    kind="import",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=text,
                    code=text
                ))

            elif node_type == "class_definition":
                name_node = node.child_by_field_name("name")
                class_name = get_node_text(name_node) if name_node else "AnonymousClass"
                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                snippet = "\n".join(lines[start_l - 1:end_l])
                
                # Check for docstring
                docstring = ""
                body_node = node.child_by_field_name("body")
                if body_node and body_node.children:
                    first = body_node.children[0]
                    if first.type == "expression_statement":
                        docstring = get_node_text(first).strip().strip('"""').strip("'''")

                symbols.append(CodeSymbol(
                    name=class_name,
                    kind="class",
                    start_line=start_l,
                    end_line=end_l,
                    signature=f"class {class_name}",
                    docstring=docstring,
                    code=snippet,
                    parent=parent_name
                ))
                
                # Walk children inside class
                for child in node.children:
                    walk(child, parent_name=class_name)
                return

            elif node_type == "function_definition":
                name_node = node.child_by_field_name("name")
                fn_name = get_node_text(name_node) if name_node else "anonymous"
                params_node = node.child_by_field_name("parameters")
                params = get_node_text(params_node) if params_node else "()"
                sig = f"def {fn_name}{params}"
                
                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                snippet = "\n".join(lines[start_l - 1:end_l])

                docstring = ""
                body_node = node.child_by_field_name("body")
                if body_node and body_node.children:
                    first = body_node.children[0]
                    if first.type == "expression_statement":
                        docstring = get_node_text(first).strip().strip('"""').strip("'''")

                kind = "method" if parent_name else "function"
                
                # Extract calls inside function
                calls = []
                for m in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', snippet):
                    called = m.group(1)
                    if called not in ("def", "if", "for", "while", "return", "with", "except", "class", fn_name):
                        if called not in calls:
                            calls.append(called)

                symbols.append(CodeSymbol(
                    name=f"{parent_name}.{fn_name}" if parent_name else fn_name,
                    kind=kind,
                    start_line=start_l,
                    end_line=end_l,
                    signature=sig,
                    docstring=docstring,
                    code=snippet,
                    parent=parent_name,
                    calls=calls[:15]
                ))
                return

            for child in node.children:
                walk(child, parent_name)

        walk(root_node)
        return ParseResult(
            language="python",
            symbols=symbols,
            imports=imports,
            syntax_valid=True,
            total_lines=len(lines)
        )

    def _extract_from_ast_python(self, tree: ast.AST, code: str, lines: List[str]) -> ParseResult:
        symbols: List[CodeSymbol] = []
        imports: List[str] = []

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.current_class = None

            def visit_Import(self, node):
                for alias in node.names:
                    imp_str = f"import {alias.name}"
                    imports.append(imp_str)
                    symbols.append(CodeSymbol(
                        name=alias.name,
                        kind="import",
                        start_line=node.lineno,
                        end_line=getattr(node, 'end_lineno', node.lineno),
                        signature=imp_str,
                        code=imp_str
                    ))

            def visit_ImportFrom(self, node):
                mod = node.module or ""
                names = ", ".join(a.name for a in node.names)
                imp_str = f"from {mod} import {names}"
                imports.append(imp_str)
                symbols.append(CodeSymbol(
                    name=mod,
                    kind="import",
                    start_line=node.lineno,
                    end_line=getattr(node, 'end_lineno', node.lineno),
                    signature=imp_str,
                    code=imp_str
                ))

            def visit_ClassDef(self, node):
                prev_class = self.current_class
                self.current_class = node.name
                
                doc = ast.get_docstring(node) or ""
                end_line = getattr(node, 'end_lineno', node.lineno + 1)
                snippet = "\n".join(lines[node.lineno - 1:end_line])
                
                symbols.append(CodeSymbol(
                    name=node.name,
                    kind="class",
                    start_line=node.lineno,
                    end_line=end_line,
                    signature=f"class {node.name}",
                    docstring=doc,
                    code=snippet,
                    parent=prev_class
                ))
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node):
                self._handle_fn(node)

            def visit_AsyncFunctionDef(self, node):
                self._handle_fn(node, is_async=True)

            def _handle_fn(self, node, is_async=False):
                doc = ast.get_docstring(node) or ""
                end_line = getattr(node, 'end_lineno', node.lineno + 1)
                snippet = "\n".join(lines[node.lineno - 1:end_line])
                prefix = "async def " if is_async else "def "
                
                calls = []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        if isinstance(sub.func, ast.Name):
                            calls.append(sub.func.id)
                        elif isinstance(sub.func, ast.Attribute):
                            calls.append(sub.func.attr)

                kind = "method" if self.current_class else "function"
                full_name = f"{self.current_class}.{node.name}" if self.current_class else node.name
                symbols.append(CodeSymbol(
                    name=full_name,
                    kind=kind,
                    start_line=node.lineno,
                    end_line=end_line,
                    signature=f"{prefix}{node.name}(...)",
                    docstring=doc,
                    code=snippet,
                    parent=self.current_class,
                    calls=list(set(calls))[:15]
                ))

        Visitor().visit(tree)
        return ParseResult(
            language="python",
            symbols=symbols,
            imports=imports,
            syntax_valid=True,
            total_lines=len(lines)
        )

    def _parse_tree_sitter_js_ts(self, code: str, lines: List[str], lang: str) -> ParseResult:
        parser = TSX_PARSER if lang == "tsx" else (TS_PARSER if lang == "typescript" else JS_PARSER)
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception as e:
            return self._parse_generic_regex(code, lines, lang)

        symbols: List[CodeSymbol] = []
        imports: List[str] = []

        def get_node_text(node) -> str:
            return code.encode("utf-8")[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def walk(node, parent_name=None):
            nonlocal imports
            ntype = node.type

            if ntype in ("import_statement", "import_declaration"):
                text = get_node_text(node).strip()
                imports.append(text)
                symbols.append(CodeSymbol(
                    name=text,
                    kind="import",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=text,
                    code=text
                ))

            elif ntype in ("class_declaration", "class"):
                name_node = node.child_by_field_name("name")
                cname = get_node_text(name_node) if name_node else "AnonymousClass"
                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                snippet = "\n".join(lines[start_l - 1:end_l])

                symbols.append(CodeSymbol(
                    name=cname,
                    kind="class",
                    start_line=start_l,
                    end_line=end_l,
                    signature=f"class {cname}",
                    code=snippet,
                    parent=parent_name
                ))
                for child in node.children:
                    walk(child, parent_name=cname)
                return

            elif ntype in ("function_declaration", "method_definition"):
                name_node = node.child_by_field_name("name")
                fname = get_node_text(name_node) if name_node else "anonymous"
                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                snippet = "\n".join(lines[start_l - 1:end_l])
                kind = "method" if parent_name else "function"

                symbols.append(CodeSymbol(
                    name=f"{parent_name}.{fname}" if parent_name else fname,
                    kind=kind,
                    start_line=start_l,
                    end_line=end_l,
                    signature=f"function {fname}()",
                    code=snippet,
                    parent=parent_name
                ))
                return

            for child in node.children:
                walk(child, parent_name)

        walk(tree.root_node)
        return ParseResult(
            language=lang,
            symbols=symbols,
            imports=imports,
            syntax_valid=not tree.root_node.has_error,
            total_lines=len(lines)
        )

    def _parse_generic_regex(self, code: str, lines: List[str], lang: str) -> ParseResult:
        symbols: List[CodeSymbol] = []
        imports: List[str] = []

        # Generic function/class regexes
        fn_patterns = [
            (re.compile(r'^\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)'), "function"),
            (re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)\s*\((.*?)\)'), "function"),
            (re.compile(r'^\s*(?:export\s+)?const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>'), "function"),
            (re.compile(r'^\s*(?:public|private|protected)?\s*class\s+([a-zA-Z0-9_]+)'), "class"),
        ]

        for i, line in enumerate(lines, start=1):
            for pat, kind in fn_patterns:
                m = pat.match(line)
                if m:
                    name = m.group(1)
                    end_line = min(i + 25, len(lines))
                    symbols.append(CodeSymbol(
                        name=name,
                        kind=kind,
                        start_line=i,
                        end_line=end_line,
                        signature=line.strip()[:100],
                        code="\n".join(lines[i - 1:end_line])
                    ))
                    break

        return ParseResult(
            language=lang,
            symbols=symbols,
            imports=imports,
            syntax_valid=True,
            total_lines=len(lines)
        )
