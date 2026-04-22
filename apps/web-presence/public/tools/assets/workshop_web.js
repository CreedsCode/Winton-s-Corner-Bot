const workshopCodes = [];
let activeTags = new Set();
let searchQuery = '';

function renderFilterBar() {
    const allTags = [...new Set(workshopCodes.flatMap(e => e.tags || []))].sort();
    const bar = document.getElementById('tag-filter');
    if (allTags.length === 0) {
        bar.innerHTML = '';
        return;
    }
    bar.innerHTML = allTags.map(tag => `
        <button class="tag-btn${activeTags.has(tag) ? ' active' : ''}"
                onclick="toggleTag('${escAttr(tag)}')">${escHtml(tag)}</button>
    `).join('');
}

function toggleTag(tag) {
    activeTags.has(tag) ? activeTags.delete(tag) : activeTags.add(tag);
    renderFilterBar();
    renderCards();
}

function renderCards() {
    const q = searchQuery.toLowerCase();
    const filtered = workshopCodes.filter(e => {
        const matchesTag = activeTags.size === 0 || (e.tags || []).some(t => activeTags.has(t));
        const matchesSearch = !q ||
            e.code.toLowerCase().includes(q) ||
            (e.description || '').toLowerCase().includes(q) ||
            (e.tags || []).some(t => t.toLowerCase().includes(q));

        return matchesTag && matchesSearch;
    });

    const grid = document.getElementById('codes-grid');
    grid.innerHTML = filtered.length > 0 ? filtered.map(entry => {
        const tagChips = (entry.tags || []).map(t =>
            `<span class="tag-chip">${escHtml(t)}</span>`
        ).join('');
        return `
            <div class="card">
                <div class="card-code">${escHtml(entry.code)}</div>
                <div class="card-description">${escHtml(entry.description)}</div>
                ${tagChips ? `<div class="card-tags">${tagChips}</div>` : ''}
                <button class="copy-btn" onclick="copyCode(this, '${escAttr(entry.code)}')">Copy Code</button>
            </div>
        `;
    }).join('') : '<p class="no-results">No codes match your search.</p>';
}

function copyCode(btn, code) {
    navigator.clipboard.writeText(code).then(() => {
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = 'Copy Code';
            btn.classList.remove('copied');
        }, 750);
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = code;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = 'Copy Code';
            btn.classList.remove('copied');
        }, 750);
    });
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escAttr(str) {
    return String(str).replace(/'/g, "\\'");
}

fetch("http://localhost:8000/codes")
    .then((r) => r.json())
    .then((codes) => {
        workshopCodes.push(...codes);
        renderFilterBar();
        renderCards();
    });

document.getElementById('search-input').addEventListener('input', function () {
    searchQuery = this.value.trim();
    renderCards();
});
