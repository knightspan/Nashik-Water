import { useTranslation } from 'react-i18next';
import { sourceBadge } from '../lib/format';
import type { Source } from '../lib/types';

/** SIMULATED (virtual node), LIVE (real node, fresh data) or DATA DELAYED (real node, stale). */
export function SourceBadge({ source }: { source: Source }) {
  const { t } = useTranslation();
  const kind = sourceBadge(source);
  if (kind === 'simulated') {
    return (
      <span
        title={t('badge.simulatedHint')}
        className="inline-flex items-center rounded-full border border-dashed border-ink/60 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-ink"
      >
        {t('badge.simulated')}
      </span>
    );
  }
  if (kind === 'delayed') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-ink/40 bg-status-grey/30 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-ink">
        <span aria-hidden="true" className="h-2 w-2 rounded-full bg-status-grey" />
        {t('badge.delayed')}
      </span>
    );
  }
  return (
    <span
      title={t('badge.liveHint')}
      className="inline-flex items-center gap-1.5 rounded-full border border-status-green px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-ink"
    >
      <span aria-hidden="true" className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-green opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-status-green" />
      </span>
      {t('badge.live')}
    </span>
  );
}
