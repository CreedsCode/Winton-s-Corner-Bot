function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

const FILTERED_CHANNEL_IDS = [
    '1426624170602532894',
    '1455182949036064885',
    '1455182523905605775',
    '1455182413054476308'
];

/**
 * Fetch and render Discord voice channels
 */
async function renderVoiceChannels() {
    const container = document.getElementById('voice-channels');
    if (!container) return;

    const data = await API.getDiscordChannels();

    if (!data || !data.channels) {
        container.innerHTML = '<p class="error">Failed to load voice channels</p>';
        return;
    }

    // Filter out hard-coded channel IDs
    const voiceChannels = data.channels
        .filter(ch => !FILTERED_CHANNEL_IDS.includes(ch.id))
        .sort((a, b) => b.position - a.position);

    if (voiceChannels.length === 0) {
        container.innerHTML = '<p class="loading-text">No active channels</p>';
        return;
    }

    container.innerHTML = voiceChannels
        .map(channel => `
            <div class="channel-item">
                <span class="channel-icon"></span>
                <div class="channel-name">${escapeHtml(channel.name)}</div>
            </div>
        `)
        .join('');
}

/**
 * Fetch and render top workshop codes
 */
async function renderWorkshopCodes() {
    const container = document.getElementById('workshop-codes');
    if (!container) return;

    const codes = await API.getWorkshopCodes(5);

    if (!codes || codes.length === 0) {
        container.innerHTML = '<p class="error">Failed to load workshop codes</p>';
        return;
    }

    if (codes.length === 0) {
        container.innerHTML = '<p class="loading-text">No codes available</p>';
        return;
    }

    container.innerHTML = codes
        .slice(0, 5)
        .map((code, idx) => {
            const title = code.title;
            const codeValue = code.code;
            return `
            <div class="code-item">
                <span class="code-rank">#${idx + 1}</span>
                <span class="code-code">${escapeHtml(title)}</span>
                <button class="code-copy-btn" onclick="copyCode(this, '${codeValue.replace(/'/g, "\\'")}')" title="Copy code">COPY</button>
            </div>
        `;
        })
        .join('');
}

/**
 * Fetch and render LFG feed
 */
async function renderLFGFeed() {
    const container = document.getElementById('lfg-feed');
    if (!container) return;

    const parties = await API.getLFGParties();

    if (!parties || parties.length === 0) {
        container.innerHTML = '<p class="error">Failed to load parties</p>';
        return;
    }

    if (parties.length === 0) {
        container.innerHTML = '<p class="loading-text">No parties available</p>';
        return;
    }

    container.innerHTML = parties
        .map(post => `
            <div class="lfg-post">
                <div class="lfg-author">${post.author || 'Anonymous'}</div>
                <div class="lfg-text">${post.title || post.description || 'No description'}</div>
            </div>
        `)
        .join('');
}

/**
 * Fetch and render latest news post
 */
async function renderNews() {
    const container = document.getElementById('news-section');
    if (!container) return;

    const news = await API.getLatestNews();

    if (!news || news.length === 0) {
        container.innerHTML = '<p class="loading-text">No news</p>';
        return;
    }

    const post = news[0];

    if (!post) {
        container.innerHTML = '<p class="loading-text">No news</p>';
        return;
    }

    container.innerHTML = `
        <div class="news-entry">
            <div class="news-date">${formatDate(post.created_at || post.createdAt || new Date().toISOString())}</div>
            <div class="news-headline">${post.title || 'Update'}</div>
            <div class="news-body">${post.content || post.description || 'No content'}</div>
        </div>
    `;
}

/**
 * Format date string to readable format (YYYY-MM-DD)
 */
function formatDate(dateString) {
    if (!dateString) return 'Unknown date';
    const date = new Date(dateString);
    return date.toISOString().split('T')[0];
}

/**
 * Copy workshop code to clipboard with visual feedback
 */
function copyCode(button, code) {
    const finish = (ok) => {
        button.textContent = ok ? '✓ COPIED' : 'COPY';
        if (ok) button.classList.add('copied');
        setTimeout(() => {
            button.textContent = 'COPY';
            button.classList.remove('copied');
        }, 460);
    };

    navigator.clipboard.writeText(code)
        .then(() => finish(true))
        .catch(err => {
            console.error('Failed to copy code:', err);
            finish(false);
        });
}

document.addEventListener('DOMContentLoaded', async function () {
    await Promise.all([
        renderVoiceChannels(),
        renderWorkshopCodes(),
        renderLFGFeed(),
        renderNews()
    ]);
});
