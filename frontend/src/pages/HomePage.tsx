import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { EchoText } from '../components/EchoText';
import { Legend } from '../components/Legend';
import { SiteCard } from '../components/SiteCard';
import { SiteMap } from '../components/SiteMap';
import { ErrorState, LoadingBlock, Skeleton } from '../components/States';
import { SummaryBar } from '../components/SummaryBar';
import { api } from '../lib/api';
import { sortBySeverity } from '../lib/format';
import { useRefetchInterval } from '../lib/live';

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const interval = useRefetchInterval();
  const sources = useQuery({
    queryKey: ['sources'],
    queryFn: api.sources,
    refetchInterval: interval,
  });
  const summary = useQuery({
    queryKey: ['summary'],
    queryFn: api.summary,
    refetchInterval: interval,
  });

  return (
    <>
      <section className="overflow-hidden px-4 pb-6 pt-10 text-center sm:px-8 sm:pt-14">
        <p className="eyebrow mb-4">{t('home.eyebrow')}</p>
        <EchoText text="GODAVARI" className="text-[clamp(3rem,12vw,9rem)]" />
        <p className="mx-auto mt-6 max-w-2xl text-base text-muted sm:text-lg">{t('home.lede')}</p>
      </section>

      <SummaryBar summary={summary.data} />

      {sources.isPending ? (
        <Skeleton className="h-[58vh] min-h-[340px] w-full md:h-[68vh]" />
      ) : sources.data ? (
        <SiteMap sources={sources.data} />
      ) : null}

      <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-8">
        <Legend />
        <section aria-labelledby="sites-title">
          <div className="mb-5 flex items-baseline justify-between gap-4">
            <h2 id="sites-title" className="text-3xl sm:text-4xl">
              {t('home.sites')}
            </h2>
            <p className="text-xs uppercase tracking-wide text-muted">{t('home.sitesHint')}</p>
          </div>
          {sources.isPending && <LoadingBlock rows={4} />}
          {sources.isError && !sources.data && (
            <ErrorState onRetry={() => void sources.refetch()} />
          )}
          {sources.data && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sortBySeverity(sources.data, i18n.language).map((s) => (
                <SiteCard key={s.id} source={s} />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
