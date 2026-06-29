async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Accept': 'application/json', ...(options.headers || {}) },
    ...options,
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

export const api = {
  getHealth: () => request('/health'),
  getStatus: () => request('/api/status'),
  getLayers: () => request('/api/layers'),
  getStats: () => request('/api/stats'),
  pressLayer: (instrument) => request(`/api/layers/${instrument}/press`, { method: 'POST' }),
};