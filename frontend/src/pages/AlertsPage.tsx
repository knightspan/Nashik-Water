import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertsTable } from '../components/AlertsTable';
import { EmptyState, ErrorState, LoadingBlock } from '../components/States';
import { api } from '../lib/api';
import { siteName } from '../lib/format';
import { useRefetchInterval } from '../lib/live';

type AckFilter = 'all' | 'open' | 'acknowledged';

export default function AlertsPage() {
  const { t, i18n } = useTranslation();
  const interval = useRefetchInterval();
  const [site, setSite] = useState('');
  const [ack, setAck] = useState<AckFilter>('all');

  const sources = useQuery({ queryKey: ['sources'], queryFn: api.sources });
  const alerts = useQuery({
    queryKey: ['alerts', 'list', site, ack],
    queryFn: () =>
      api.alerts({
        limit: 200,
        site: site || undefined,
        acknowledged: ack === 'all' ? undefined : ack === 'acknowledged',
      }),
    refetchInterval: interval,
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-8 sm:py-14">
      <h1 className="text-[clamp(2.5rem,8vw,5.5rem)] leading-crush">{t('alerts.title')}</h1>
      <p className="mt-4 max-w-2xl text-muted">{t('alerts.lede')}</p>

      <div className="my-8 flex flex-wrap gap-4 border-y border-line/10 py-4">
        <label className="flex w-full flex-col gap-1 text-xs font-bold uppercase tracking-wide text-muted sm:w-auto">
          {t('alerts.site')}
          <select
            value={site}
            onChange={(e) => setSite(e.target.value)}
            className="w-full rounded-full sm:min-w-[220px] border border-ink bg-paper px-4 py-2 text-sm normal-case tracking-normal text-ink"
          >
            <option value="">{t('alerts.allSites')}</option>
            {sources.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {siteName(s, i18n.language)}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="flex min-w-0 flex-col gap-1">
          <legend className="text-xs font-bold uppercase tracking-wide text-muted">
            {t('alerts.state')}
          </legend>
          <div className="inline-flex rounded-full border border-ink p-0.5">
            {(['all', 'open', 'acknowledged'] as const).map((k) => (
              <button
                key={k}
                type="button"
                aria-pressed={ack === k}
                onClick={() => setAck(k)}
                className={`rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-wide ${ack === k ? 'bg-ink text-paper' : 'hover:bg-surface'}`}
              >
                {t(`alerts.${k}`)}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      {alerts.isPending && <LoadingBlock rows={4} />}
      {alerts.isError && <ErrorState onRetry={() => void alerts.refetch()} />}
      {alerts.data &&
        (alerts.data.length ? (
          <AlertsTable alerts={alerts.data} />
        ) : (
          <EmptyState>{t('alerts.empty')}</EmptyState>
        ))}
    </div>
  );
}
