function getAuthHeaders() {
  const headers = { Accept: 'application/json' };
  const authHeader = localStorage.getItem('auth_header');

  if (authHeader) {
    headers.Authorization = authHeader;
  }

  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.headers || {}) },
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.error || response.statusText;
    throw new Error(detail);
  }

  return payload;
}

function normalizeLoginError(error) {
  if (error?.name === 'AbortError') {
    return new Error('Backend neodpovedá');
  }
  if (error?.message === 'authentication_required' || error?.message === 'unauthorized') {
    return new Error('Nesprávne meno alebo heslo');
  }
  return error instanceof Error ? error : new Error('Prihlásenie zlyhalo');
}

export const api = {
  login: async (username, password) => {
    const normalizedUsername = username.trim();
    const authHeader = `Basic ${btoa(`${normalizedUsername}:${password}`)}`;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);

    try {
      await request('/api/status', {
        headers: { Authorization: authHeader },
        signal: controller.signal,
      });
      return authHeader;
    } catch (error) {
      throw normalizeLoginError(error);
    } finally {
      window.clearTimeout(timeout);
    }
  },
  getHealth: () => request('/health'),
  getStatus: () => request('/api/status'),
  getLayers: () => request('/api/layers'),
  getStats: () => request('/api/stats'),
  pressLayer: (instrument) => request(`/api/layers/${instrument}/press`, { method: 'POST' }),
  restartService: () => request('/api/system/restart_service', { method: 'POST' }),
  rebootSystem: () => request('/api/system/reboot', { method: 'POST' }),
  shutdownSystem: () => request('/api/system/shutdown', { method: 'POST' }),
};
