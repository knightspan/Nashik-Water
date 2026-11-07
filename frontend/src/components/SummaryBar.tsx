import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { timeAgo } from '../lib/format';
import type { Colour, Summary } from '../lib/types';
import { Skeleton } from './States';
import { StatusDot } from './StatusBadge';

const ORDER: Colour[] = ['RED', 'AMBER', 'GREEN', 'GREY'];

export function SummaryBar({ summary }: { summary: Summary | undefined }) {
  const { t, i18n } = useTranslation();
  if (!summary) return <Skeleton className="h-[72px] w-full" />;
  return (
    <section
      aria-label={t('summary.sites')}
      className="grid grid-cols-2 border-y border-line/10 sm:grid-cols-4 lg:grid-cols-6"
    >
      {ORDER.map((c) => (
        <div
          key={c}
          className="flex items-center gap-3 border-b border-r border-line/10 px-4 py-3 lg:border-b-0"
        >
          <StatusDot colour={c} />
          <div>
            <p
              className="font-display text-2xl font-bold leading-none tracking-tight"
              data-testid={`count-${c}`}
            >
              {summary.colours[c] ?? 0}
            </p>
            <p className="text-xs text-muted">{t(`status.${c}`)}</p>
          </div>
        </div>
      ))}
      <Link
        to="/alerts"
        className="flex flex-col justify-center border-b border-r border-line/10 px-4 py-3 transition-colors hover:bg-surface sm:border-b-0"
      >
        <p
          className={`font-display text-2xl font-bold leading-none tracking-tight ${summary.active_alerts ? 'text-status-red' : ''}`}
        >
          {summary.active_alerts}
        </p>
        <p className="text-xs text-muted">{t('summary.activeAlerts')}</p>
      </Link>
      <div className="flex flex-col justify-center px-4 py-3">
        <p className="text-sm font-bold">
          {summary.last_update ? timeAgo(summary.last_update, i18n.language) : t('summary.never')}
        </p>
        <p className="text-xs text-muted">{t('summary.lastUpdate')}</p>
      </div>
    </section>
  );
}
