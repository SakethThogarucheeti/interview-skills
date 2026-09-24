// Thin API client -- one function per endpoint, one place that knows the base
// URL and error handling. Rename Item -> your entity everywhere below.
const BASE = "/api";
// Demo only: a VITE_ var is bundled into the JS, so this key is public to anyone who
// opens devtools. Real answer: user login (session/OAuth) or a backend-for-frontend.
const KEY = import.meta.env.VITE_API_KEY;

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(KEY && { "X-API-Key": KEY }) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error?.message || `Request failed: ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  listItems: () => request("/items"),
  getItem: (id) => request(`/items/${id}`),
  createItem: (data) => request("/items", { method: "POST", body: JSON.stringify(data) }),
  updateItem: (id, data) => request(`/items/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteItem: (id) => request(`/items/${id}`, { method: "DELETE" }),
};
