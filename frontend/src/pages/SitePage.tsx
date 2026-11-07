import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Download } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { AlertsTable } from '../components/AlertsTable';
import { ParamChart } from '../components/ParamChart';
import { SourceBadge } from '../components/SourceBadge';
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from '../components/States';
import { StatsPanel } from '../components/StatsPanel';
import { StatusBadge } from '../components/StatusBadge';
import { api, ApiError } from '../lib/api';
import { DIGITS, fmt, siteDescription, STATUS_HEX, timeAgo, UNITS } from '../lib/format';
import { useRefetchInterval } from '../lib/live';
import type { Param } from '../lib/types';

const RANGES = [
  { hours: 24, key: 'site.range24h' },
  { hours: 168, key: 'site.range7d' },
  { hours: 720, key: 'site.range30d' },
];
const CHART_PARAMS: Param[] = ['wqi', 'ph', 'tds', 'turb', 'temp'];

export default function SitePage() {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const interval = useRefetchInterval();
  const [hours, setHours] = useState(24);

  const source = useQuery({
    queryKey: ['source', id],
    queryFn: () => api.source(id),
    refetchInterval: interval,
  });
  const series = useQuery({
    queryKey: ['readings', id, hours],
    queryFn: () => api.readings(id, hours),
    refetchInterval: interval,
    placeholderData: (prev) => prev,
  });
  const stats = useQuery({
    queryKey: ['stats', id],
    queryFn: () => api.stats(id, 7),
    refetchInterval: 5 * 60_000,
  });
  const alerts = useQuery({
    queryKey: ['alerts', 'site', id],
    queryFn: () => api.alerts({ site: id, limit: 20 }),
  });

  if (source.isPending) {
    return (
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-10 sm:px-8">
        <Skeleton className="h-24 w-2/3" />
        <LoadingBlock rows={3} />
      </div>
    );
  }
  if (source.isError) {
    const notFound = source.error instanceof ApiError && source.error.status === 404;
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <ErrorState
          message={notFound ? t('site.notFound') : undefined}
          onRetry={notFound ? undefined : () => void source.refetch()}
        />
      </div>
    );
  }

  const s = source.data;
  const r = s.latest;
  const other = lang === 'mr' ? s.name_en : s.name_mr;

  return (
    <div className="mx-auto max-w-7xl space-y-10 px-4 py-8 sm:px-8 sm:py-12">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-wide hover:text-subtle"
      >
        <ArrowLeft size={16} aria-hidden="true" /> {t('site.back')}
      </Link>

      <header className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-end">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className="eyebrow">{t(`kind.${s.kind}`, { defaultValue: s.kind })}</span>
            <SourceBadge source={s} />
          </div>
          <h1 className="text-[clamp(2.25rem,7vw,5rem)] leading-crush">
            {lang === 'mr' ? s.name_mr : s.name_en}
          </h1>
          <p className="mt-3 font-serif text-2xl italic text-muted">{other}</p>
          <p className="mt-4 max-w-2xl text-muted">{siteDescription(s, lang)}</p>
        </div>

        <section
          aria-label={t('param.health')}
          data-testid="status-card"
          className="border-t-8 bg-surface p-6"
          style={{ borderTopColor: STATUS_HEX[s.status_colour] }}
        >
          <StatusBadge colour={s.status_colour} size="lg" />
          <p className="mt-4 font-display text-3xl font-bold tracking-tight">
            {r && !s.stale ? t(`label.${r.label}`) : r ? t('badge.delayed') : t('home.noData')}
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-muted">{t('param.confidence')}</dt>
              <dd className="text-lg font-bold">
                {r?.confidence ? `${fmt(r.confidence, 0)}%` : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-muted">{t('param.health')}</dt>
              <dd className="text-lg font-bold">{r ? t(`health.${r.health}`) : '—'}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-muted">{t('summary.lastUpdate')}</dt>
              <dd className="font-bold">{r ? timeAgo(r.ts, lang) : '—'}</dd>
            </div>
          </dl>
        </section>
      </header>

      <section aria-labelledby="current-title">
        <h2 id="current-title" className="mb-4 text-2xl">
          {t('site.current')}
        </h2>
        <dl className="grid grid-cols-2 border-l border-t border-line/10 sm:grid-cols-3 lg:grid-cols-6">
          {(['ph', 'tds', 'turb', 'temp', 'wqi'] as const).map((p) => (
            <div key={p} className="border-b border-r border-line/10 p-4">
              <dt className={`text-xs tracking-wide text-muted ${p === 'ph' ? '' : 'uppercase'}`}>
                {t(`param.${p}`)}
              </dt>
              <dd className="mt-1 font-display text-3xl font-bold tabular-nums tracking-tight">
                {fmt(r?.[p], DIGITS[p])}
                {UNITS[p] && (
                  <span className="ml-1 font-sans text-sm font-medium text-muted">{UNITS[p]}</span>
                )}
              </dd>
            </div>
          ))}
          <div className="border-b border-r border-line/10 p-4">
            <dt className="text-xs uppercase tracking-wide text-muted">{t('site.wqiBand')}</dt>
            <dd className="mt-1 text-lg font-bold leading-tight">
              {r?.wqi_band ? t(`band.${r.wqi_band}`) : '—'}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="history-title">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="history-title" className="text-2xl">
              {t('site.history')}
            </h2>
            <p className="text-xs text-muted">
              {series.data && t(`site.resolution.${series.data.resolution}`)} ·{' '}
              {t('site.redShaded')}
            </p>
          </div>
          <div
            role="group"
            aria-label={t('site.history')}
            className="inline-flex rounded-full border border-ink p-0.5"
          >
            {RANGES.map((rg) => (
              <button
                key={rg.hours}
                type="button"
                aria-pressed={hours === rg.hours}
                onClick={() => setHours(rg.hours)}
                className={`rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-wide transition-colors ${hours === rg.hours ? 'bg-ink text-paper' : 'hover:bg-surface'}`}
              >
                {t(rg.key)}
              </button>
            ))}
          </div>
        </div>
        {series.isPending && <LoadingBlock rows={2} />}
        {series.isError && <ErrorState onRetry={() => void series.refetch()} />}
        {series.data && series.data.points.length === 0 && (
          <EmptyState>{t('site.noChartData')}</EmptyState>
        )}
        {series.data && series.data.points.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {CHART_PARAMS.map((p) => (
              <div key={p} className={p === 'wqi' ? 'md:col-span-2' : ''}>
                <ParamChart points={series.data.points} param={p} hours={hours} />
              </div>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="stats-title">
        <h2 id="stats-title" className="mb-4 text-2xl">
          {t('site.stats')}
        </h2>
        {stats.isPending && <LoadingBlock rows={2} />}
        {stats.data &&
          (stats.data.count ? (
            <StatsPanel stats={stats.data} />
          ) : (
            <EmptyState>{t('site.noChartData')}</EmptyState>
          ))}
      </section>

      <section aria-labelledby="alerts-title">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <h2 id="alerts-title" className="text-2xl">
            {t('site.alerts')}
          </h2>
          <a href={api.csvUrl(s.id, 7)} className="btn-pill" download>
            <Download size={16} aria-hidden="true" /> {t('site.download')}
          </a>
        </div>
        {alerts.isPending && <LoadingBlock rows={1} />}
        {alerts.data &&
          (alerts.data.length ? (
            <AlertsTable alerts={alerts.data} showSite={false} />
          ) : (
            <EmptyState>{t('site.noAlerts')}</EmptyState>
          ))}
      </section>
    </div>
  );
}
