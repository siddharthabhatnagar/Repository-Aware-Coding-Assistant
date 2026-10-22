/**
 * RepoPulse - Frontend Interactive Engine
 * Handles State, API Communication, Tree Rendering, Code Highlighting, and UI Controls.
 */

const state = {
    activeTab: 'search',
    repoPath: '',
    isIndexed: false,
    fileTree: null,
    currentFile: null,
    currentFileContent: '',
    currentFileSymbols: [],
    searchResults: [],
    lastPatch: null,
};

// Initial setup on page load
document.addEventListener('DOMContentLoaded', async () => {
    setupTabNavigation();
    setupModals();
    await checkHealthAndInitialize();
});

async function checkHealthAndInitialize() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        if (data.is_indexed && data.repo_path) {
            state.repoPath = data.repo_path;
            state.isIndexed = true;
            updateHeaderStatus(data.repo_path, true);
            await loadInitialRepoData();
        } else {
            // Open default sample repo
            await openRepoPath('sample_repo');
        }
    } catch (e) {
        console.error("Health check error:", e);
        showNotification("Failed to connect to backend API", "danger");
    }
}

function updateHeaderStatus(repoPath, isIndexed) {
    const el = document.getElementById('repo-path-display');
    if (el) {
        const parts = repoPath.split(/[\\/]/);
        el.textContent = parts[parts.length - 1] || repoPath;
        el.title = repoPath;
    }
    const idxBadge = document.getElementById('index-status-badge');
    if (idxBadge) {
        idxBadge.innerHTML = isIndexed 
            ? '<span class="pulse-dot"></span> Indexed (Ready)' 
            : '<span class="pulse-dot" style="background: var(--warning)"></span> Not Indexed';
    }
}

async function loadInitialRepoData() {
    await fetchTree();
    await fetchGitStatus();
}

/* ==========================================================================
   Tab Navigation
   ========================================================================== */
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            switchTab(target);
        });
    });
}

function switchTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-pane').forEach(p => {
        p.classList.toggle('active', p.id === `tab-${tabId}`);
    });

    // Lazy load tab data
    if (tabId === 'dependencies') {
        loadDependencies();
    } else if (tabId === 'review') {
        runCodeReview();
    } else if (tabId === 'git') {
        loadGitTimeline();
    } else if (tabId === 'tests' && state.currentFile) {
        document.getElementById('test-target-file').value = state.currentFile;
    }
}

/* ==========================================================================
   Repository Operations
   ========================================================================== */
async function openRepoPath(path) {
    showNotification(`Opening & indexing repository: ${path}...`, 'info');
    try {
        const res = await fetch('/api/repo/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_path: path })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to open repository");

        state.repoPath = data.repo_path;
        state.isIndexed = true;
        updateHeaderStatus(data.repo_path, true);
        showNotification(`Indexed ${data.files_indexed} files with ${data.total_symbols} symbols!`, 'success');
        
        await loadInitialRepoData();
        closeModal('open-repo-modal');
    } catch (err) {
        showNotification(err.message, 'danger');
    }
}

async function fetchTree() {
    try {
        const res = await fetch('/api/repo/tree');
        const tree = await res.json();
        state.fileTree = tree;
        renderFileTree(tree, document.getElementById('tree-root'));
        
        // Auto-select first file if available
        if (tree.children && tree.children.length > 0) {
            const firstFile = findFirstFile(tree);
            if (firstFile) {
                loadFileContent(firstFile.path);
            }
        }
    } catch (e) {
        console.error("Error loading tree:", e);
    }
}

function findFirstFile(node) {
    if (node.type === 'file') return node;
    if (node.children) {
        for (let child of node.children) {
            const found = findFirstFile(child);
            if (found) return found;
        }
    }
    return null;
}

function renderFileTree(node, container, level = 0) {
    container.innerHTML = '';
    
    function createNodeElement(item, depth) {
        const row = document.createElement('div');
        row.className = 'tree-node';
        row.style.paddingLeft = `${depth * 14 + 8}px`;

        if (item.type === 'directory') {
            row.innerHTML = `<span style="color: var(--orange-light);">📁</span> <span>${escapeHtml(item.name)}</span>`;
            const childrenWrapper = document.createElement('div');
            let isExpanded = true;

            row.addEventListener('click', () => {
                isExpanded = !isExpanded;
                childrenWrapper.style.display = isExpanded ? 'block' : 'none';
                row.querySelector('span').textContent = isExpanded ? '📁' : '📂';
            });

            container.appendChild(row);
            container.appendChild(childrenWrapper);

            if (item.children) {
                item.children.forEach(child => createChild(child, childrenWrapper, depth + 1));
            }
        } else {
            const icon = getFileIcon(item.name);
            row.innerHTML = `<span>${icon}</span> <span>${escapeHtml(item.name)}</span>`;
            row.addEventListener('click', () => {
                document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active-file'));
                row.classList.add('active-file');
                loadFileContent(item.path);
            });
            container.appendChild(row);
        }
    }

    function createChild(item, parentEl, depth) {
        const row = document.createElement('div');
        row.className = 'tree-node';
        row.style.paddingLeft = `${depth * 14 + 8}px`;

        if (item.type === 'directory') {
            row.innerHTML = `<span style="color: var(--orange-light);">📁</span> <span>${escapeHtml(item.name)}</span>`;
            const wrapper = document.createElement('div');
            let expanded = true;
            row.addEventListener('click', () => {
                expanded = !expanded;
                wrapper.style.display = expanded ? 'block' : 'none';
            });
            parentEl.appendChild(row);
            parentEl.appendChild(wrapper);
            if (item.children) {
                item.children.forEach(c => createChild(c, wrapper, depth + 1));
            }
        } else {
            const icon = getFileIcon(item.name);
            row.innerHTML = `<span>${icon}</span> <span>${escapeHtml(item.name)}</span>`;
            row.addEventListener('click', () => {
                document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active-file'));
                row.classList.add('active-file');
                loadFileContent(item.path);
            });
            parentEl.appendChild(row);
        }
    }

    if (node.children) {
        node.children.forEach(c => createChild(c, container, 0));
    }
}

function getFileIcon(filename) {
    if (filename.endsWith('.py')) return '🐍';
    if (filename.endsWith('.js') || filename.endsWith('.ts')) return '⚡';
    if (filename.endsWith('.json')) return '📦';
    if (filename.endsWith('.txt') || filename.endsWith('.md')) return '📄';
    return '📝';
}

async function loadFileContent(relPath) {
    state.currentFile = relPath;
    document.getElementById('current-file-title').textContent = relPath;
    
    try {
        const res = await fetch(`/api/repo/file?path=${encodeURIComponent(relPath)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error reading file");

        state.currentFileContent = data.content;
        state.currentFileSymbols = data.symbols || [];

        renderCodeWithLines(data.content);
        renderAstSymbols(data.symbols || []);
        
        // Also update test tab default target
        const testInput = document.getElementById('test-target-file');
        if (testInput) testInput.value = relPath;

    } catch (e) {
        showNotification(e.message, 'danger');
    }
}

function renderCodeWithLines(content) {
    const lines = content.split('\n');
    const lineNumbersEl = document.getElementById('code-line-numbers');
    const codeContentEl = document.getElementById('code-content');

    lineNumbersEl.innerHTML = lines.map((_, i) => `<span class="line-number" data-line="${i+1}">${i+1}</span>`).join('');
    codeContentEl.innerHTML = escapeHtml(content);
}

function renderAstSymbols(symbols) {
    const container = document.getElementById('ast-symbols-list');
    if (!container) return;
    
    if (symbols.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No AST symbols in this file.</div>';
        return;
    }

    container.innerHTML = symbols.map(s => `
        <div class="symbol-item" onclick="highlightLines(${s.start_line}, ${s.end_line})">
            <div class="symbol-kind">${s.kind}</div>
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary);">${escapeHtml(s.name)}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-top: 0.2rem;">
                <span>Lines ${s.start_line} - ${s.end_line}</span>
                ${s.calls && s.calls.length ? `<span>Calls: ${s.calls.length}</span>` : ''}
            </div>
        </div>
    `).join('');
}

function highlightLines(start, end) {
    const lineEls = document.querySelectorAll('.line-number');
    lineEls.forEach(el => {
        const num = parseInt(el.dataset.line, 10);
        if (num >= start && num <= end) {
            el.style.color = 'var(--orange-primary)';
            el.style.fontWeight = 'bold';
        } else {
            el.style.color = '';
            el.style.fontWeight = '';
        }
    });
}

/* ==========================================================================
   Code Search & RAG
   ========================================================================== */
async function handleSearch() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) return;

    const symbolType = document.getElementById('search-symbol-type').value;
    const fileFilter = document.getElementById('search-file-filter').value.trim() || null;
    const resultsContainer = document.getElementById('search-results');
    
    resultsContainer.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Searching repository AST & embeddings...</div>';

    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                top_k: 8,
                symbol_type: symbolType,
                file_filter: fileFilter
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Search failed");

        state.searchResults = data.results;
        renderSearchResults(data.results);
    } catch (e) {
        resultsContainer.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');
    if (!results || results.length === 0) {
        container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">No matching code symbols found.</div>';
        return;
    }

    container.innerHTML = results.map(r => {
        const c = r.chunk;
        return `
            <div class="glass-panel result-card">
                <div class="result-header">
                    <div class="result-file-ref">
                        <span>📄 ${escapeHtml(c.file_path)}</span>
                        <span class="badge badge-orange">L${c.start_line}-${c.end_line}</span>
                        <span class="badge" style="background: rgba(255, 140, 56, 0.1); color: var(--text-secondary); text-transform: uppercase;">${c.symbol_type}</span>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <span style="font-size: 0.75rem; color: var(--amber-accent); font-weight: 600;">Match: ${(r.score * 100).toFixed(0)}%</span>
                        <button class="btn btn-glass" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="viewInExplorer('${c.file_path}', ${c.start_line}, ${c.end_line})">Inspect in File</button>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                    <strong>${escapeHtml(c.symbol_name)}</strong> &mdash; ${escapeHtml(c.summary || '')}
                </div>
                <div class="code-box">${escapeHtml(c.content)}</div>
            </div>
        `;
    }).join('');
}

function viewInExplorer(filePath, startLine, endLine) {
    switchTab('explorer');
    loadFileContent(filePath).then(() => {
        highlightLines(startLine, endLine);
    });
}

/* ==========================================================================
   Dependency Explanations
   ========================================================================== */
async function loadDependencies() {
    const container = document.getElementById('dependencies-container');
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Analyzing manifests and intra-repo imports...</div>';

    try {
        const res = await fetch('/api/dependencies');
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to load dependencies");

        renderDependencies(data);
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

function renderDependencies(data) {
    const container = document.getElementById('dependencies-container');
    const manifests = data.manifests || {};
    const pythonDeps = manifests.python_requirements || [];
    const nodeDeps = manifests.node_package || [];
    const graph = data.graph || { nodes: [], edges: [] };

    let html = `
        <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
            <h3 style="color: var(--orange-light); margin-bottom: 0.5rem;">Repository Dependency Intelligence</h3>
            <p style="color: var(--text-secondary); font-size: 0.9rem;">${escapeHtml(data.summary)}</p>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
            <!-- Python Dependencies -->
            <div class="glass-panel" style="padding: 1.25rem;">
                <h4 style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span>🐍</span> Python Dependencies (requirements.txt)
                </h4>
                <div>
                    ${pythonDeps.length === 0 ? '<div style="color: var(--text-muted);">No requirements.txt found.</div>' : 
                      pythonDeps.map(p => `
                        <div style="padding: 0.75rem; background: rgba(255, 140, 56, 0.05); border: 1px solid var(--border-glass-subtle); border-radius: var(--radius-sm); margin-bottom: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: 600; color: var(--amber-accent); font-family: var(--font-mono);">${escapeHtml(p.name)}</span>
                                <span class="badge ${p.risk_level === 'Medium' ? 'badge-orange' : 'badge-safe'}">${escapeHtml(p.version)}</span>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.3rem;">${escapeHtml(p.purpose)}</div>
                            ${p.advisory ? `<div style="font-size: 0.75rem; color: var(--warning); margin-top: 0.2rem;">⚠️ ${escapeHtml(p.advisory)}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>

            <!-- Node.js Dependencies -->
            <div class="glass-panel" style="padding: 1.25rem;">
                <h4 style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span>⚡</span> Node.js Dependencies (package.json)
                </h4>
                <div>
                    ${nodeDeps.length === 0 ? '<div style="color: var(--text-muted);">No package.json found.</div>' : 
                      nodeDeps.map(n => `
                        <div style="padding: 0.75rem; background: rgba(255, 140, 56, 0.05); border: 1px solid var(--border-glass-subtle); border-radius: var(--radius-sm); margin-bottom: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: 600; color: var(--orange-light); font-family: var(--font-mono);">${escapeHtml(n.name)}</span>
                                <span class="badge ${n.is_dev ? 'badge-git' : 'badge-safe'}">${n.is_dev ? 'dev: ' : ''}${escapeHtml(n.version)}</span>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.3rem;">${escapeHtml(n.purpose)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>

        <!-- Intra-repo Import Graph -->
        <div class="glass-panel" style="padding: 1.25rem;">
            <h4 style="margin-bottom: 0.75rem;">Intra-Repository Import Call Graph</h4>
            <div style="display: flex; flex-wrap: wrap; gap: 0.75rem;">
                ${graph.edges.length === 0 ? '<div style="color: var(--text-muted);">No cross-file internal imports detected.</div>' :
                  graph.edges.map(e => `
                    <div class="badge badge-git" style="padding: 0.5rem 0.85rem; font-size: 0.85rem;">
                        <strong>${escapeHtml(e.source)}</strong> &rarr; ${escapeHtml(e.target)}
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

/* ==========================================================================
   Test Suggestions
   ========================================================================== */
async function generateTests() {
    const file = document.getElementById('test-target-file').value.trim();
    if (!file) {
        showNotification("Please specify a target file path (e.g. calculator.py)", "warning");
        return;
    }

    const container = document.getElementById('test-results-container');
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Generating unit tests with boundary condition checks...</div>';

    try {
        const res = await fetch('/api/tests/suggest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: file })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to generate tests");

        renderTestSuggestions(data);
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

function renderTestSuggestions(data) {
    const container = document.getElementById('test-results-container');
    const cases = data.test_cases || [];

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="font-size: 1.1rem; color: var(--orange-light);">Suggested Tests for ${escapeHtml(data.file_path)}</h3>
            <button class="btn btn-primary" onclick="copyFullTestSuite()">Copy Complete Test File</button>
        </div>
    `;

    html += cases.map((tc, idx) => `
        <div class="glass-panel" style="padding: 1.25rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <span style="font-weight: 700; color: var(--amber-accent); font-family: var(--font-mono);">${escapeHtml(tc.test_name)}</span>
                    <span class="badge badge-orange">${escapeHtml(tc.target_ref)}</span>
                </div>
                <button class="btn btn-glass" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="copyCodeText(this)">Copy Test</button>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.6rem;">
                🎯 <strong>Scenario:</strong> ${escapeHtml(tc.scenario)}
            </div>
            <div class="code-box">${escapeHtml(tc.code)}</div>
        </div>
    `).join('');

    // Hidden container for full test suite copy
    html += `<textarea id="full-test-suite-hidden" style="display:none;">${escapeHtml(data.full_test_file_content || '')}</textarea>`;

    container.innerHTML = html;
}

function copyFullTestSuite() {
    const el = document.getElementById('full-test-suite-hidden');
    if (el) {
        navigator.clipboard.writeText(el.value);
        showNotification("Full test suite copied to clipboard!", "success");
    }
}

function copyCodeText(button) {
    const card = button.closest('.glass-panel');
    const code = card.querySelector('.code-box').textContent;
    navigator.clipboard.writeText(code);
    button.textContent = "Copied!";
    setTimeout(() => button.textContent = "Copy Test", 2000);
}

/* ==========================================================================
   Patch Proposals & Git Apply
   ========================================================================== */
function setPatchPrompt(promptText) {
    document.getElementById('patch-issue-input').value = promptText;
    proposePatch();
}

async function proposePatch() {
    const issue = document.getElementById('patch-issue-input').value.trim();
    if (!issue) {
        showNotification("Please describe the bug or select a preset", "warning");
        return;
    }

    const container = document.getElementById('patch-result-container');
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Generating unified diff patch...</div>';

    try {
        const res = await fetch('/api/patch/propose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issue_description: issue })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to generate patch");

        state.lastPatch = data;
        renderPatchProposal(data);
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

function renderPatchProposal(patch) {
    const container = document.getElementById('patch-result-container');
    const diffHtml = renderUnifiedDiff(patch.unified_diff);

    container.innerHTML = `
        <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <h3 style="color: var(--orange-light);">${escapeHtml(patch.title)}</h3>
                <div style="display: flex; gap: 0.5rem;">
                    <span class="badge badge-orange">${escapeHtml(patch.file_path)} : L${escapeHtml(patch.lines_affected)}</span>
                    <span class="badge badge-safe">Confidence: ${(patch.confidence * 100).toFixed(0)}%</span>
                </div>
            </div>
            <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                <strong>Root Cause:</strong> ${escapeHtml(patch.root_cause)}
            </div>
            <div style="font-size: 0.9rem; color: var(--amber-accent); margin-bottom: 1rem;">
                <strong>Remediation:</strong> ${escapeHtml(patch.solution)}
            </div>

            <div style="margin-bottom: 1rem;">${diffHtml}</div>

            <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
                <button class="btn btn-glass" onclick="applyCurrentPatch(true)">Dry-Run Patch (Check)</button>
                <button class="btn btn-primary" onclick="applyCurrentPatch(false)">Apply Patch to Repository</button>
            </div>
        </div>
        <div id="patch-apply-feedback" style="margin-top: 1rem;"></div>
    `;
}

async function applyCurrentPatch(dryRun) {
    if (!state.lastPatch) return;

    const feedbackEl = document.getElementById('patch-apply-feedback');
    feedbackEl.innerHTML = '<div style="color: var(--text-muted);">Executing Git patch application...</div>';

    try {
        const res = await fetch('/api/patch/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patch_content: state.lastPatch.unified_diff,
                dry_run: dryRun
            })
        });
        const data = await res.json();
        
        if (data.success) {
            feedbackEl.innerHTML = `
                <div class="glass-panel" style="padding: 1rem; border-color: var(--success); background: var(--success-bg);">
                    <div style="color: #6fffe9; font-weight: 600;">✅ ${escapeHtml(data.message)}</div>
                </div>
            `;
            if (!dryRun) {
                showNotification("Patch applied to repository cleanly!", "success");
                await fetchGitStatus();
            }
        } else {
            feedbackEl.innerHTML = `
                <div class="glass-panel" style="padding: 1rem; border-color: var(--danger); background: var(--danger-bg);">
                    <div style="color: var(--danger); font-weight: 600;">❌ ${escapeHtml(data.message)}</div>
                </div>
            `;
        }
    } catch (e) {
        feedbackEl.innerHTML = `<div style="color: var(--danger);">${escapeHtml(e.message)}</div>`;
    }
}

/* ==========================================================================
   Automated Code Review
   ========================================================================== */
async function runCodeReview() {
    const container = document.getElementById('review-results-container');
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Auditing repository for security vulnerabilities, bug risks, and code smells...</div>';

    try {
        const res = await fetch('/api/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Review failed");

        renderCodeReview(data);
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

function renderCodeReview(data) {
    const container = document.getElementById('review-results-container');
    const findings = data.findings || [];

    let html = `
        <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem;">
            <div class="glass-panel" style="flex: 1; padding: 1.25rem; border-left: 4px solid var(--danger);">
                <div style="font-size: 0.8rem; color: var(--text-muted);">CRITICAL RISKS</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: var(--danger);">${data.critical_count}</div>
            </div>
            <div class="glass-panel" style="flex: 1; padding: 1.25rem; border-left: 4px solid var(--warning);">
                <div style="font-size: 0.8rem; color: var(--text-muted);">WARNINGS</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: var(--warning);">${data.warning_count}</div>
            </div>
            <div class="glass-panel" style="flex: 1; padding: 1.25rem; border-left: 4px solid var(--orange-primary);">
                <div style="font-size: 0.8rem; color: var(--text-muted);">INFO / ADVISORIES</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: var(--orange-light);">${data.info_count}</div>
            </div>
        </div>
    `;

    html += findings.map(f => {
        const sevClass = f.severity.toLowerCase();
        return `
            <div class="glass-panel finding-card ${sevClass}">
                <div class="finding-header">
                    <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <span class="badge ${f.severity === 'CRITICAL' ? 'badge-orange' : 'badge-safe'}" style="${f.severity === 'CRITICAL' ? 'background: var(--danger-bg); color: var(--danger); border-color: var(--danger-border);' : ''}">${f.severity}</span>
                        <span style="font-weight: 600; color: var(--text-primary); font-size: 1rem;">${escapeHtml(f.title)}</span>
                    </div>
                    <div class="badge badge-orange" style="font-family: var(--font-mono);">
                        ${escapeHtml(f.file_path)} : L${f.start_line}-${f.end_line}
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                    ${escapeHtml(f.description)}
                </div>
                <div style="background: rgba(0, 0, 0, 0.3); padding: 0.65rem; border-radius: var(--radius-sm); border-left: 3px solid var(--amber-accent); font-size: 0.85rem; color: var(--amber-accent);">
                    💡 <strong>Suggested Fix:</strong> ${escapeHtml(f.recommendation)}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

/* ==========================================================================
   Git Status & Timeline
   ========================================================================== */
async function fetchGitStatus() {
    try {
        const res = await fetch('/api/git/status');
        const data = await res.json();
        const branchEl = document.getElementById('git-branch-badge');
        if (branchEl) {
            branchEl.textContent = `🌿 ${data.branch || 'main'}`;
        }
    } catch (e) {
        console.error("Git status fetch error:", e);
    }
}

async function loadGitTimeline() {
    const container = document.getElementById('git-timeline-container');
    container.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Fetching Git history and uncommitted changes...</div>';

    try {
        const [statRes, diffRes, histRes] = await Promise.all([
            fetch('/api/git/status'),
            fetch('/api/git/diff'),
            fetch('/api/git/history')
        ]);

        const status = await statRes.json();
        const diff = await diffRes.json();
        const history = await histRes.json();

        let html = `
            <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
                <h3 style="color: var(--orange-light); margin-bottom: 0.75rem;">Git Repository Status</h3>
                <div style="display: flex; gap: 1.5rem; font-size: 0.9rem;">
                    <div><strong>Active Branch:</strong> <span class="badge badge-git">${escapeHtml(status.branch)}</span></div>
                    <div><strong>Head Commit:</strong> <span class="badge badge-orange">${escapeHtml(status.commit_hash)}</span></div>
                    <div><strong>Status:</strong> ${status.is_dirty ? '<span style="color: var(--warning);">Dirty (Uncommitted Changes)</span>' : '<span style="color: #6fffe9;">Clean</span>'}</div>
                </div>
            </div>

            <!-- Current Diff -->
            <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
                <h4 style="margin-bottom: 0.75rem;">Uncommitted Diff</h4>
                ${diff.diff ? renderUnifiedDiff(diff.diff) : '<div style="color: var(--text-muted); font-size: 0.85rem;">No uncommitted changes in working directory.</div>'}
            </div>

            <!-- Commit History -->
            <div class="glass-panel" style="padding: 1.5rem;">
                <h4 style="margin-bottom: 1rem;">Commit History</h4>
                <div>
                    ${(history.commits || []).map(c => `
                        <div style="padding: 0.75rem; border-bottom: 1px solid var(--border-glass-subtle); display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span class="badge badge-orange" style="margin-right: 0.5rem;">${escapeHtml(c.hash)}</span>
                                <strong style="color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(c.summary)}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">By ${escapeHtml(c.author)} on ${escapeHtml(c.date)}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); padding: 1rem;">${escapeHtml(e.message)}</div>`;
    }
}

/* ==========================================================================
   Modals & Notifications
   ========================================================================== */
function setupModals() {
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            e.target.classList.remove('active');
        }
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `glass-panel`;
    toast.style.cssText = `
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        padding: 0.85rem 1.25rem;
        z-index: 1000;
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-color: ${type === 'danger' ? 'var(--danger)' : (type === 'success' ? 'var(--success)' : 'var(--orange-primary)')};
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        animation: fadeIn 0.3s ease;
    `;
    toast.innerHTML = `<span>${type === 'danger' ? '⚠️' : (type === 'success' ? '✅' : 'ℹ️')}</span> <span>${escapeHtml(message)}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 3500);
}

async function saveSettings() {
    const provider = document.getElementById('settings-provider').value;
    const key = document.getElementById('settings-key').value.trim();

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider, api_key: key })
        });
        const data = await res.json();
        showNotification(`Configured LLM provider: ${data.provider}`, 'success');
        closeModal('settings-modal');
    } catch (e) {
        showNotification("Failed to update settings", "danger");
    }
}
