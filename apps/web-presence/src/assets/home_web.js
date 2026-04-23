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

function copyCode(btn, code) {
    const finish = (ok) => {
        btn.textContent = ok ? '✓ COPIED' : 'COPY';
        if (ok) btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = 'COPY';
            btn.classList.remove('copied');
        }, 800);
    };

    navigator.clipboard.writeText(code)
        .then(() => finish(true))
        .catch(() => {
            try {
                const ta = document.createElement('textarea');
                ta.value = code;
                ta.style.cssText = 'position:fixed;opacity:0';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                finish(true);
            } catch {
                finish(false);
            }
        });
}

function renderCodes(codes) {
    const list = document.getElementById('codes-list');
    if (!list) return;

    if (!codes || codes.length === 0) {
        list.innerHTML = '<p class="codes-loading">No codes found.</p>';
        return;
    }

    list.innerHTML = codes.map((entry, i) => `
        <div class="retro-card">
            <span class="retro-rank">#${i + 1}</span>
            <span class="retro-code">${escHtml(entry.code)}</span>
            <button class="retro-copy" onclick="copyCode(this, '${escAttr(entry.code)}')">COPY</button>
        </div>
    `).join('');
}

fetch("/api/workshop_codes?origin_context_id=eq.00000000-0000-0000-0001-000000000000&order=copy_count.desc&limit=5")
    .then(r => r.json())
    .then(renderCodes)
    .catch(() => {
        const list = document.getElementById('codes-list');
        if (list) list.innerHTML = '<p class="codes-loading">Could not load codes right now.</p>';
    });
