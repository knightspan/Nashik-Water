import type {
  Alert,
  ApiKey,
  AuditEntry,
  Health_,
  Series,
  Site,
  SiteIngestHealth,
  Source,
  Stats,
  Summary,
  Tokens,
  User,
} from './types';

/** Base URL of the FastAPI back end. Empty string = same origin. */
export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// --------------------------------------------------------------------------- tokens
// Access + refresh tokens live in sessionStorage (cleared when the tab closes) and are sent
// in the Authorization header — never in cookies.
const TOKENS_KEY = 'nwq.tokens';
let tokens: Tokens | null = readTokens();
const listeners = new Set<() => void>();

function readTokens(): Tokens | null {
  try {
    const raw = sessionStorage.getItem(TOKENS_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(t: Tokens | null): void {
  tokens = t;
  try {
    if (t) sessionStorage.setItem(TOKENS_KEY, JSON.stringify(t));
    else sessionStorage.removeItem(TOKENS_KEY);
  } catch {
    /* storage blocked: tokens still work for this page view */
  }
  listeners.forEach((l) => l());
}

export function getTokens(): Tokens | null {
  return tokens;
}

export function onTokensChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// --------------------------------------------------------------------------- fetch
async function request<T>(path: string, init: RequestInit = {}, auth = false): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (auth && tokens) headers.set('Authorization', `Bearer ${tokens.access_token}`);

  let res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401 && auth && tokens) {
    if (await refresh()) {
      headers.set('Authorization', `Bearer ${tokens!.access_token}`);
      res = await fetch(`${API_URL}${path}`, { ...init, headers });
    }
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && auth) setTokens(null);
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  if (!tokens) return false;
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tokens!.refresh_token }),
      });
      if (!res.ok) return false;
      setTokens((await res.json()) as Tokens);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

// --------------------------------------------------------------------------- endpoints
export const api = {
  health: () => request<Health_>('/api/health'),
  sources: () => request<Source[]>('/api/sources'),
  source: (id: string) => request<Source>(`/api/sources/${encodeURIComponent(id)}`),
  readings: (id: string, hours: number) =>
    request<Series>(`/api/sources/${encodeURIComponent(id)}/readings?hours=${hours}`),
  stats: (id: string, days = 7) =>
    request<Stats>(`/api/sources/${encodeURIComponent(id)}/stats?days=${days}`),
  alerts: (params: { limit?: number; site?: string; acknowledged?: boolean } = {}) => {
    const q = new URLSearchParams({ limit: String(params.limit ?? 50) });
    if (params.site) q.set('site', params.site);
    if (params.acknowledged !== undefined) q.set('acknowledged', String(params.acknowledged));
    return request<Alert[]>(`/api/alerts?${q}`);
  },
  summary: () => request<Summary>('/api/summary'),
  csvUrl: (id: string, days = 7) =>
    `${API_URL}/api/export/${encodeURIComponent(id)}.csv?days=${days}`,
  streamUrl: () => `${API_URL}/api/stream`,

  login: (email: string, password: string) =>
    request<Tokens>('/api/auth/login', { method: 'POST', ...json({ email, password }) }),
  me: () => request<User>('/api/auth/me', {}, true),

  admin: {
    sites: () => request<Site[]>('/api/admin/sites', {}, true),
    createSite: (s: Site) =>
      request<Site>('/api/admin/sites', { method: 'POST', ...json(s) }, true),
    updateSite: (id: string, s: Partial<Site>) =>
      request<Site>(`/api/admin/sites/${id}`, { method: 'PUT', ...json(s) }, true),
    deactivateSite: (id: string) =>
      request<Site>(`/api/admin/sites/${id}`, { method: 'DELETE' }, true),
    ack: (id: number, note?: string) =>
      request<Alert>(`/api/admin/alerts/${id}/ack`, { method: 'POST', ...json({ note }) }, true),
    apiKeys: () => request<ApiKey[]>('/api/admin/apikeys', {}, true),
    rotateKey: () =>
      request<{ key: string; api_key: ApiKey; revoked: number }>(
        '/api/admin/apikeys/rotate',
        { method: 'POST', ...json({ name: 'rotated from admin panel', revoke_previous: true }) },
        true,
      ),
    audit: (limit = 100) => request<AuditEntry[]>(`/api/admin/audit?limit=${limit}`, {}, true),
    ingestHealth: () =>
      request<{ generated_at: string; sites: SiteIngestHealth[] }>(
        '/api/admin/ingest-health',
        {},
        true,
      ),
  },
};
