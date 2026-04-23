// Winton's Corner — shared app utilities

const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('wc_token');
}

function saveToken(t) {
  localStorage.setItem('wc_token', t);
}

function clearToken() {
  localStorage.removeItem('wc_token');
}

function parseJwt(t) {
  try {
    return JSON.parse(atob(t.split('.')[1]));
  } catch {
    return null;
  }
}

/**
 * Fetch the API with optional Bearer token injection.
 * On 401: clears the stored token (caller decides whether to redirect).
 */
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const resp = await fetch(API_BASE + path, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
  }
  return resp;
}

/** Read #token=... from the URL fragment, persist it, and strip the fragment. */
function captureTokenFromFragment() {
  const hash = window.location.hash;
  if (hash.startsWith('#token=')) {
    const token = hash.slice(7);
    saveToken(token);
    // Replace history entry so the token doesn't linger in the URL
    window.history.replaceState(null, '', window.location.pathname);
    return token;
  }
  return null;
}

/** Simple HTML escaping to prevent XSS when rendering untrusted content. */
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function logout() {
  clearToken();
  window.location.href = '/app/';
}
