import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, LogOut, Plus } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertsTable } from '../components/AlertsTable';
import { EmptyState, ErrorState, LoadingBlock } from '../components/States';
import { api, ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { dateTime, timeAgo } from '../lib/format';
import type { Alert, Site } from '../lib/types';

const TABS = ['sites', 'alerts', 'ingest', 'keys', 'audit'] as const;
type Tab = (typeof TABS)[number];

const input =
  'w-full rounded-sm border border-line/25 bg-paper px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none';

function Login() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401 ? t('admin.loginError') : t('state.error'),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="card mx-auto max-w-sm space-y-4 p-6"
      aria-labelledby="login-title"
    >
      <h2 id="login-title" className="text-2xl">
        {t('admin.login')}
      </h2>
      <label className="block text-sm font-bold">
        {t('admin.email')}
        <input
          className={`${input} mt-1`}
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="block text-sm font-bold">
        {t('admin.password')}
        <input
          className={`${input} mt-1`}
          type="password"
          autoComplete="current-password"
          required
          maxLength={72}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm font-bold text-status-red">
          {error}
        </p>
      )}
      <button type="submit" className="btn-pill w-full justify-center" disabled={busy}>
        {t('admin.login')}
      </button>
    </form>
  );
}

const EMPTY_SITE: Site = {
  id: '',
  name_en: '',
  name_mr: '',
  kind: 'river',
  lat: 20.0,
  lon: 73.78,
  simulated: true,
  active: true,
  description_en: '',
  description_mr: '',
};

function SiteForm({
  initial,
  isNew,
  onDone,
}: {
  initial: Site;
  isNew: boolean;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [s, setS] = useState<Site>(initial);
  const save = useMutation({
    mutationFn: () => {
      if (isNew) return api.admin.createSite(s);
      const { id, ...rest } = s;
      return api.admin.updateSite(id, rest);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'sites'] });
      void qc.invalidateQueries({ queryKey: ['sources'] });
      onDone();
    },
  });
  const field = (
    k: keyof Site,
    label: string,
    type = 'text',
    extra: Record<string, unknown> = {},
  ) => (
    <label className="block text-xs font-bold uppercase tracking-wide text-muted">
      {label}
      <input
        className={`${input} mt-1 normal-case tracking-normal`}
        type={type}
        value={String(s[k])}
        onChange={(e) =>
          setS({ ...s, [k]: type === 'number' ? Number(e.target.value) : e.target.value })
        }
        {...extra}
      />
    </label>
  );
  return (
    <form
      className="grid gap-3 border border-line/15 bg-surface p-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {isNew &&
        field('id', t('admin.sites.id'), 'text', { pattern: '[a-z0-9_]{2,64}', required: true })}
      {field('name_en', t('admin.sites.nameEn'), 'text', { required: true })}
      {field('name_mr', t('admin.sites.nameMr'), 'text', { required: true, lang: 'mr' })}
      {field('kind', t('admin.sites.kind'), 'text', { required: true })}
      {field('lat', t('admin.sites.lat'), 'number', {
        step: 'any',
        min: -90,
        max: 90,
        required: true,
      })}
      {field('lon', t('admin.sites.lon'), 'number', {
        step: 'any',
        min: -180,
        max: 180,
        required: true,
      })}
      <label className="block text-xs font-bold uppercase tracking-wide text-muted sm:col-span-2">
        {t('admin.sites.descEn')}
        <textarea
          className={`${input} mt-1 normal-case tracking-normal`}
          rows={2}
          value={s.description_en}
          onChange={(e) => setS({ ...s, description_en: e.target.value })}
        />
      </label>
      <label className="block text-xs font-bold uppercase tracking-wide text-muted sm:col-span-2">
        {t('admin.sites.descMr')}
        <textarea
          lang="mr"
          className={`${input} mt-1 normal-case tracking-normal`}
          rows={2}
          value={s.description_mr}
          onChange={(e) => setS({ ...s, description_mr: e.target.value })}
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={s.simulated}
          onChange={(e) => setS({ ...s, simulated: e.target.checked })}
        />
        {t('admin.sites.simulated')}
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={s.active}
          onChange={(e) => setS({ ...s, active: e.target.checked })}
        />
        {t('admin.sites.active')}
      </label>
      {save.isError && (
        <p role="alert" className="text-sm font-bold text-status-red sm:col-span-2">
          {(save.error as Error).message}
        </p>
      )}
      <div className="flex gap-2 sm:col-span-2">
        <button type="submit" className="btn-pill" disabled={save.isPending}>
          {t('admin.sites.save')}
        </button>
        <button type="button" className="btn-pill border-line/30" onClick={onDone}>
          {t('admin.sites.cancel')}
        </button>
      </div>
    </form>
  );
}

function SitesTab() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const sites = useQuery({ queryKey: ['admin', 'sites'], queryFn: api.admin.sites });
  const [editing, setEditing] = useState<string | null>(null);
  const deactivate = useMutation({
    mutationFn: (id: string) => api.admin.deactivateSite(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'sites'] });
      void qc.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  if (sites.isPending) return <LoadingBlock />;
  if (sites.isError) return <ErrorState onRetry={() => void sites.refetch()} />;
  return (
    <div className="space-y-3">
      {editing === '__new__' ? (
        <SiteForm initial={EMPTY_SITE} isNew onDone={() => setEditing(null)} />
      ) : (
        <button type="button" className="btn-pill" onClick={() => setEditing('__new__')}>
          <Plus size={16} aria-hidden="true" /> {t('admin.sites.add')}
        </button>
      )}
      <ul className="space-y-3">
        {sites.data.map((s) => (
          <li key={s.id} className="card p-4">
            {editing === s.id ? (
              <SiteForm initial={s} isNew={false} onDone={() => setEditing(null)} />
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-display text-lg font-bold tracking-tight">
                    {i18n.language === 'mr' ? s.name_mr : s.name_en}
                    <span className="ml-2 font-sans text-xs font-medium text-muted">{s.id}</span>
                  </p>
                  <p className="text-xs text-muted">
                    {s.lat.toFixed(4)}, {s.lon.toFixed(4)} · {s.kind} ·{' '}
                    {s.simulated ? t('admin.sites.simulated') : t('badge.live')} ·{' '}
                    {s.active ? t('admin.sites.active') : t('admin.sites.inactive')}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-pill !py-1 !text-xs"
                    onClick={() => setEditing(s.id)}
                  >
                    {t('admin.sites.edit')}
                  </button>
                  {s.active && (
                    <button
                      type="button"
                      className="btn-pill !py-1 !text-xs"
                      onClick={() =>
                        window.confirm(t('admin.sites.confirmDeactivate')) &&
                        deactivate.mutate(s.id)
                      }
                    >
                      {t('admin.sites.deactivate')}
                    </button>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AlertsTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const alerts = useQuery({
    queryKey: ['alerts', 'admin'],
    queryFn: () => api.alerts({ limit: 200 }),
  });
  const ack = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => api.admin.ack(id, note),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['alerts'] });
      void qc.invalidateQueries({ queryKey: ['summary'] });
    },
  });
  const onAck = (a: Alert) => {
    const note = window.prompt(`${t('alerts.ack')} — ${t('alerts.note')}`, '') ?? undefined;
    ack.mutate({ id: a.id, note: note || undefined });
  };
  if (alerts.isPending) return <LoadingBlock />;
  if (alerts.isError) return <ErrorState onRetry={() => void alerts.refetch()} />;
  return alerts.data.length ? (
    <AlertsTable alerts={alerts.data} onAck={onAck} />
  ) : (
    <EmptyState>{t('alerts.empty')}</EmptyState>
  );
}

function IngestTab() {
  const { t, i18n } = useTranslation();
  const health = useQuery({
    queryKey: ['admin', 'ingest'],
    queryFn: api.admin.ingestHealth,
    refetchInterval: 30_000,
  });
  if (health.isPending) return <LoadingBlock />;
  if (health.isError) return <ErrorState onRetry={() => void health.refetch()} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line/15 text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="py-2 pr-4">
              {t('alerts.site')}
            </th>
            <th scope="col" className="py-2 pr-4">
              {t('admin.ingest.lastMessage')}
            </th>
            <th scope="col" className="py-2 pr-4 text-right">
              {t('admin.ingest.perHour')}
            </th>
            <th scope="col" className="py-2">
              {t('admin.ingest.last24h')}
            </th>
          </tr>
        </thead>
        <tbody>
          {health.data.sites.map((s) => {
            const max = Math.max(1, ...s.hourly);
            return (
              <tr key={s.site_id} className="border-b border-line/5">
                <th scope="row" className="py-3 pr-4 text-left font-bold">
                  {s.name_en}{' '}
                  {s.simulated && (
                    <span className="text-xs font-medium text-muted">({t('badge.simulated')})</span>
                  )}
                </th>
                <td className="py-3 pr-4">
                  {s.last_received_at ? timeAgo(s.last_received_at, i18n.language) : '—'}
                </td>
                <td className="py-3 pr-4 text-right font-bold tabular-nums">
                  {s.messages_last_hour}
                </td>
                <td className="py-3">
                  <div
                    className="flex h-8 items-end gap-[2px]"
                    role="img"
                    aria-label={s.hourly.join(', ')}
                  >
                    {s.hourly.map((n, i) => (
                      <span
                        key={i}
                        title={String(n)}
                        className="w-2 rounded-t-[2px] bg-water"
                        style={{
                          height: `${Math.max(n ? 8 : 2, (n / max) * 100)}%`,
                          opacity: n ? 1 : 0.25,
                        }}
                      />
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function KeysTab() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const keys = useQuery({ queryKey: ['admin', 'keys'], queryFn: api.admin.apiKeys });
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const rotate = useMutation({
    mutationFn: api.admin.rotateKey,
    onSuccess: (res) => {
      setNewKey(res.key);
      setCopied(false);
      void qc.invalidateQueries({ queryKey: ['admin', 'keys'] });
    },
  });
  return (
    <div className="space-y-6">
      <button
        type="button"
        className="btn-pill"
        onClick={() => window.confirm(t('admin.keys.confirm')) && rotate.mutate()}
        disabled={rotate.isPending}
      >
        <KeyRound size={16} aria-hidden="true" /> {t('admin.keys.rotate')}
      </button>
      {newKey && (
        <div className="border-2 border-ink p-4" role="status">
          <p className="mb-2 text-sm font-bold">{t('admin.keys.newKey')}</p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="break-all bg-surface px-2 py-1 text-sm">{newKey}</code>
            <button
              type="button"
              className="btn-pill !py-1 !text-xs"
              onClick={() =>
                void navigator.clipboard?.writeText(newKey).then(() => setCopied(true))
              }
            >
              {copied ? (
                <Check size={14} aria-hidden="true" />
              ) : (
                <Copy size={14} aria-hidden="true" />
              )}
              {copied ? t('admin.keys.copied') : t('admin.keys.copy')}
            </button>
          </div>
        </div>
      )}
      {keys.data && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line/15 text-left text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="py-2 pr-4">
                {t('admin.keys.prefix')}
              </th>
              <th scope="col" className="py-2 pr-4">
                {t('admin.keys.created')}
              </th>
              <th scope="col" className="py-2 pr-4">
                {t('admin.keys.lastUsed')}
              </th>
              <th scope="col" className="py-2">
                {t('alerts.state')}
              </th>
            </tr>
          </thead>
          <tbody>
            {keys.data.map((k) => (
              <tr key={k.id} className="border-b border-line/5">
                <td className="py-2 pr-4 font-mono">{k.prefix}…</td>
                <td className="py-2 pr-4">{dateTime(k.created_at, i18n.language)}</td>
                <td className="py-2 pr-4">
                  {k.last_used_at ? timeAgo(k.last_used_at, i18n.language) : '—'}
                </td>
                <td className="py-2 font-bold">
                  {k.active ? t('admin.sites.active') : t('admin.keys.revoked')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AuditTab() {
  const { t, i18n } = useTranslation();
  const audit = useQuery({ queryKey: ['admin', 'audit'], queryFn: () => api.admin.audit(200) });
  if (audit.isPending) return <LoadingBlock />;
  if (audit.isError) return <ErrorState onRetry={() => void audit.refetch()} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line/15 text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="py-2 pr-4">
              {t('admin.audit.when')}
            </th>
            <th scope="col" className="py-2 pr-4">
              {t('admin.audit.who')}
            </th>
            <th scope="col" className="py-2 pr-4">
              {t('admin.audit.action')}
            </th>
            <th scope="col" className="py-2">
              {t('admin.audit.details')}
            </th>
          </tr>
        </thead>
        <tbody>
          {audit.data.map((a) => (
            <tr key={a.id} className="border-b border-line/5 align-top">
              <td className="whitespace-nowrap py-2 pr-4">{dateTime(a.ts, i18n.language)}</td>
              <td className="py-2 pr-4">{a.user_email ?? '—'}</td>
              <td className="py-2 pr-4 font-mono text-xs">{a.action}</td>
              <td
                className="max-w-[420px] truncate py-2 font-mono text-xs text-muted"
                title={JSON.stringify(a.details)}
              >
                {JSON.stringify(a.details)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminPage() {
  const { t } = useTranslation();
  const { user, loading, logout } = useAuth();
  const [tab, setTab] = useState<Tab>('sites');

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-8 sm:py-14">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-[clamp(2.5rem,8vw,5.5rem)] leading-crush">{t('admin.title')}</h1>
        {user && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted">{t('admin.signedInAs', { email: user.email })}</span>
            <button type="button" className="btn-pill !py-1" onClick={logout}>
              <LogOut size={14} aria-hidden="true" /> {t('admin.logout')}
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <LoadingBlock rows={2} />
      ) : !user ? (
        <Login />
      ) : user.role !== 'admin' ? (
        <ErrorState message={t('admin.adminOnly')} />
      ) : (
        <>
          <div
            role="tablist"
            aria-label={t('admin.title')}
            className="mb-6 flex gap-1 overflow-x-auto border-b border-line/15"
          >
            {TABS.map((k) => (
              <button
                key={k}
                role="tab"
                type="button"
                aria-selected={tab === k}
                onClick={() => setTab(k)}
                className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-bold uppercase tracking-wide ${tab === k ? 'border-ink' : 'border-transparent text-muted hover:text-ink'}`}
              >
                {t(`admin.tabs.${k}`)}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {tab === 'sites' && <SitesTab />}
            {tab === 'alerts' && <AlertsTab />}
            {tab === 'ingest' && <IngestTab />}
            {tab === 'keys' && <KeysTab />}
            {tab === 'audit' && <AuditTab />}
          </div>
        </>
      )}
    </div>
  );
}
