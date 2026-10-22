# ⚡ RepoPulse - Repository-Aware Coding Assistant

An intelligent, code-aware assistant engineered to help software engineers **understand unfamiliar codebases**, **locate bugs**, **trace dependencies**, **generate targeted unit tests**, **propose unified git patches**, and **conduct security-conscious code reviews** with exact file and line references.

Featuring an **interactive, animated glassmorphic UI styled in a radiant orange ember theme** with full safety sandboxing for untrusted repository content.

---

## 🌟 The Problem

When developers encounter large, unfamiliar, or legacy repositories, they face critical friction:
- **Steep onboarding curve**: Understanding architecture, entry points, and module relationships takes days.
- **Bug hunting overhead**: Locating root causes across multiple files without call-graph context is error-prone.
- **Hidden vulnerabilities**: Hardcoded secrets, unhandled exceptions, SQL injections, and bypasses lurk undetected.
- **Security risks with untrusted repos**: Indexing or executing untrusted code can trigger path traversal attacks, credential leakage, or resource exhaustion.

---

## 🚀 Key Proof Pillars

1. **Code-Aware RAG**: AST-aware chunking preserving function and class boundaries with line bounds, symbol types, and call hierarchies rather than arbitrary character splits.
2. **Tool Integration**: Direct Git integration (diffs, branch detection, commit logs, and patch application) combined with Tree-sitter parsers.
3. **Software Engineering**: Complete test generation with boundary condition checks and unified diff generation ready for review or `git apply`.
4. **Safe Handling of Untrusted Content**:
   - Strict path traversal prevention (`../` traversal and symlink escape blocks).
   - Dynamic secret and credential masking (API keys, JWT secrets, passwords).
   - Binary file detection via null-byte inspection.
   - Resource limits (file size and max indexed files caps).

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies | Purpose |
|---|---|---|
| **API & Backend** | **FastAPI**, **Uvicorn**, **Pydantic v2** | High-performance asynchronous REST API, OpenAPI schema validation |
| **Code Intelligence** | **Tree-Sitter**, **Python AST** | Multi-language AST parsing (Python, JavaScript, TypeScript, TSX) |
| **Embeddings & Vector Search** | **FAISS**, **FastEmbed** (`BAAI/bge-small-en-v1.5`) | Cosine similarity vector search combined with keyword/symbol hybrid scoring |
| **RAG & Synthesis** | **LangChain** | Code-aware retrieval, prompt templating, and optional LLM provider integration |
| **Version Control** | **GitPython**, **Git CLI** | Branch tracking, uncommitted diffs, commit history, patch verification & application |
| **Frontend** | **HTML5**, **CSS3**, **Vanilla JS** | Animated glassmorphic UI in glowing orange, split-pane code explorer, diff renderer |

---

## ✨ Features Walkthrough

### 1. 🔍 Code Search & Code-Aware RAG
- **Hybrid Search**: Blends dense 384-dimensional semantic embeddings with exact token and symbol matching.
- **Symbol Filtering**: Filter by `functions`, `classes`, `methods`, or `imports`.
- **Exact File & Line References**: Every snippet links directly to its file and line range (`L32-L46`).
- **One-Click Code Inspector**: View the matched symbol highlighted within its full source file.

### 2. 🌲 Repository Explorer & AST Symbol Inspector
- **Interactive File Tree**: Collapsible file tree displaying file sizes, extensions, and safety status.
- **Line-Numbered Code Viewer**: Full source code viewing with syntax formatting and line-click inspection.
- **Live Tree-Sitter AST Panel**: Shows all classes, methods, docstrings, and function call dependencies.

### 3. 🕸️ Dependency Explanations & Intra-Repo Graph
- **Manifest Intelligence**: Parses `requirements.txt` and `package.json`.
- **Curated Purpose Explanations**: Details what each package does (e.g. FastAPI, PyJWT, SQLAlchemy, Axios) and its architectural role.
- **Security & Version Risk**: Flags unpinned dependencies (`*`) and outdated packages.
- **Intra-Repo Import Graph**: Detects internal module imports and runs cycle detection to warn of circular dependencies.

### 4. 🧪 Targeted Unit Test Suggestions
- **Function-Targeted Testing**: Inspects functions and classes to generate comprehensive unit tests.
- **Boundary Scenarios**: Automatically generates tests for zero-division, negative numbers, token expiration, revocation, and SQL injection payloads.
- **One-Click Export**: Copy individual test cases or export the full test file.

### 5. 🩹 Patch Proposals & 1-Click Git Apply
- **Unified Git Diffs**: Generates standards-compliant git patches (`diff --git a/... b/...`, `@@ -line,len +line,len @@`).
- **Root Cause & Remediation**: Explains the bug mechanism and how the proposed patch resolves it.
- **Side-by-Side / Colorized Unified Diff**: Green additions (`+`) and red deletions (`-`).
- **Git Safety Verification**:
  - **Dry-run Patch**: Tests whether the patch applies cleanly using `git apply --check`.
  - **Apply Patch**: Applies the patch directly to the working directory.

### 6. 🛡️ Automated Code Review & Security Audit
- **CWE-798**: Flags hardcoded secrets, API keys, and passwords.
- **CWE-89**: Flags dynamic string interpolation in SQL queries.
- **CWE-347**: Flags JWT authentication verification bypasses (e.g. `verify_exp: False`).
- **Robustness**: Identifies unhandled exceptions and missing input guards.
- **Categorized Findings**: Broken down into **Critical**, **Warning**, and **Info** with suggested code replacements.

### 7. 📜 Git Timeline & Uncommitted Diff
- Real-time display of active branch, commit hash, and dirty working tree status.
- Colorized viewer for uncommitted unstaged and staged changes.
- Chronological commit history timeline.

---

## 🎨 Frontend Design System

- **Glassmorphism**: Translucent panels (`backdrop-filter: blur(16px)`), frosted borders with luminous orange rim highlights.
- **Color Palette**:
  - Primary Background: Obsidian Charcoal (`#0a0705`, `#140d08`)
  - Accent / Glow: Radiant Orange (`#ff6b00`, `#ff8c33`, `#ffaa33`)
  - Glass Surface: `rgba(28, 17, 10, 0.65)`
  - Diff Additions: Mint Teal (`#2ec4b6`, `#6fffe9`)
  - Diff Deletions: Coral Red (`#ff4444`, `#ff758f`)
- **Micro-Interactions**: Pulsing readiness dots, interactive hover elevation, smooth accordion transitions, and copy-to-clipboard ripples.

---

## 📖 How to Use

### 1. Installation
Clone the repository:
```bash
git clone https://github.com/siddharthabhatnagar/Repository-Aware-Coding-Assistant.git
cd Repository-Aware-Coding-Assistant
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Running the Application
Launch the server:
```bash
python run.py
```
Or with Uvicorn directly:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```
Interactive API docs are available at `http://127.0.0.1:8000/docs`.

### 3. Using the Assistant

1. **Explore the Sample Repository**:
   - Out of the box, `sample_repo` is automatically loaded and indexed.
   - It contains realistic files with intentional issues:
     - `auth_service.py` (JWT token auth with hardcoded secret and disabled expiration check)
     - `calculator.py` (Arithmetic functions with unhandled zero division)
     - `database.py` (SQLite connection manager with string-formatted SQL query)

2. **Search Code**:
   - Go to the **Code Search & RAG** tab.
   - Type `JWT token verify` or `divide operation` and press **Search Code**.
   - Review matching chunks with their exact line ranges and click **Inspect in File**.

3. **Inspect AST & Code**:
   - Navigate to **Repo Explorer & AST**.
   - Click any file on the left tree to inspect source code and explore Tree-Sitter AST symbols on the right.

4. **Review Dependencies**:
   - Click **Dependency Graph** to see all packages, risk assessments, and intra-repo import connections.

5. **Generate Unit Tests**:
   - Click **Test Suggestions**, select `calculator.py` or `auth_service.py`, and click **Generate Tests**.
   - Copy individual test snippets or the entire generated test file.

6. **Propose and Apply a Patch**:
   - Go to **Patch Proposals**.
   - Click one of the quick presets (e.g. *Fix ZeroDivisionError in calculator.py*).
   - Review the colorized unified diff, click **Dry-Run Patch** to verify, and click **Apply Patch** to update the file.

7. **Run Security & Code Review**:
   - Go to **Code Review & Security** to view all detected security vulnerabilities with exact line numbers and remediation suggestions.

8. **Open Any Local Repository**:
   - Click **📂 Open Repo** in the top navigation bar.
   - Enter the path to any local project folder to index and analyze it.

---

## 🌐 Deploying to Render (render.com)

This repository includes first-class support for **Render**:
* `render.yaml` Blueprint specification (Infrastructure-as-Code)
* `.python-version` configured for Python `3.12.0`
* `Procfile` configured for production Uvicorn
* Dynamic `$PORT` and `0.0.0.0` host binding

### Option 1: Automatic Blueprint Deployment (Recommended)
1. Go to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** > **Blueprint**.
3. Connect your GitHub repository: `https://github.com/siddharthabhatnagar/Repository-Aware-Coding-Assistant`.
4. Render will automatically detect [`render.yaml`](render.yaml) and configure:
   - **Environment**: Python
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
5. Click **Apply**. Your app will build, index the sample repo on startup, and provide a public live URL!

### Option 2: Manual Web Service Deployment
1. Go to **New +** > **Web Service**.
2. Select your repository `Repository-Aware-Coding-Assistant`.
3. Set the following fields:
   - **Runtime**: `Python`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Advanced** > **Add Environment Variable**:
   - `PYTHON_VERSION`: `3.12.0`
   - `ENVIRONMENT`: `production`
5. Click **Create Web Service**.

---

## 🧪 Running Automated Tests

Run the test suite with pytest:
```bash
pytest tests/ -v
```

The test suite validates:
- Path traversal blocking and security bounds.
- Secret masking and credential redaction.
- Tree-sitter AST extraction and line-number accuracy.
- FAISS vector indexing and hybrid search recall.
- Dependency manifest parsing and cycle detection.
- Patch proposal generation and automated security auditing.

---

## 📄 License
MIT License. Free to use, modify, and distribute.
