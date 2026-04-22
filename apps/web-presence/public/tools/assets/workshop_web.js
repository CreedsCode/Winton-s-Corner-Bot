const workshopCodes = [];

function renderCards() {
    const grid = document.getElementById('codes-grid');
    grid.innerHTML = workshopCodes.map(entry => `
                <div class="card">
                    <div class="card-code">${escHtml(entry.code)}</div>
                    <div class="card-description">${escHtml(entry.description)}</div>
                    <button class="copy-btn" onclick="copyCode(this, '${escAttr(entry.code)}')">Copy Code</button>
                </div>
            `).join('');
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
        renderCards();
    });
