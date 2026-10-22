/**
 * Helper to render unified git diffs into stylized glassmorphic HTML.
 */
function renderUnifiedDiff(diffText) {
    if (!diffText || !diffText.trim()) {
        return '<div style="padding: 1.5rem; text-align: center; color: var(--text-muted);">No diff content available.</div>';
    }

    const lines = diffText.split('\n');
    let html = '<div class="diff-container">';

    for (let line of lines) {
        let escaped = escapeHtml(line);
        if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff --git')) {
            html += `<div class="diff-line diff-header">${escaped}</div>`;
        } else if (line.startsWith('@@')) {
            html += `<div class="diff-line diff-header" style="background: rgba(255, 170, 51, 0.15);">${escaped}</div>`;
        } else if (line.startsWith('+')) {
            html += `<div class="diff-line diff-add">${escaped}</div>`;
        } else if (line.startsWith('-')) {
            html += `<div class="diff-line diff-del">${escaped}</div>`;
        } else {
            html += `<div class="diff-line">${escaped}</div>`;
        }
    }

    html += '</div>';
    return html;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
