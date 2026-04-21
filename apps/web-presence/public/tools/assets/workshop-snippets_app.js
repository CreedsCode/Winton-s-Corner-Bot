document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("snippet-grid");
  const searchInput = document.getElementById("search");
  const countEl = document.getElementById("snippet-count");
  const empty = document.getElementById("empty");

  function renderSnippets(list) {
    grid.innerHTML = "";

    if (list.length === 0) {
      empty.style.display = "block";
      countEl.textContent = "0 snippets";
      return;
    }

    empty.style.display = "none";
    countEl.textContent = `${list.length} snippet${list.length !== 1 ? "s" : ""}`;

    list.forEach((snippet) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-title">${escapeHtml(snippet.title)}</div>
        <div class="card-description">${escapeHtml(snippet.description)}</div>
        <button class="btn-copy" data-id="${snippet.id}">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy
        </button>
      `;
      grid.appendChild(card);
    });
  }

  function filter(query) {
    const q = query.trim().toLowerCase();
    if (!q) return snippets;
    return snippets.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    );
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  renderSnippets(snippets);

  searchInput.addEventListener("input", () => {
    renderSnippets(filter(searchInput.value));
  });

  grid.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-copy");
    if (!btn) return;

    const id = Number(btn.dataset.id);
    const snippet = snippets.find((s) => s.id === id);
    if (!snippet) return;

    try {
      await navigator.clipboard.writeText(snippet.code);
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        Copied!
      `;
      btn.classList.add("copied");
      setTimeout(() => {
        btn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy
        `;
        btn.classList.remove("copied");
      }, 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = snippet.code;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);

      btn.textContent = "Copied!";
      btn.classList.add("copied");
      setTimeout(() => {
        btn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy
        `;
        btn.classList.remove("copied");
      }, 2000);
    }
  });
});
