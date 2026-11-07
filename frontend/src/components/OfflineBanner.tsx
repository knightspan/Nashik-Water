import { useQuery } from '@tanstack/react-query';
import { CloudOff, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { useRefetchInterval } from '../lib/live';

const STALE_MS = 15 * 60 * 1000;

/** Shown when the API is unreachable, or when no site has reported for 15 minutes. */
export function OfflineBanner() {
  const { t } = useTranslation();
  const interval = useRefetchInterval();
  const summary = useQuery({
    queryKey: ['summary'],
    queryFn: api.summary,
    refetchInterval: interval || 60_000,
    retry: 1,
  });

  const offline = summary.isError;
  const last = summary.data?.last_update ? new Date(summary.data.last_update).getTime() : null;
  const delayed =
    !offline && summary.data !== undefined && (last === null || Date.now() - last > STALE_MS);
  if (!offline && !delayed) return null;

  return (
    <div
      role="status"
      data-testid="offline-banner"
      className="flex items-center justify-center gap-2 bg-ink px-4 py-2 text-center text-sm font-bold text-paper"
    >
      {offline ? <CloudOff size={16} aria-hidden="true" /> : <Clock size={16} aria-hidden="true" />}
      {offline ? t('state.offline') : t('state.delayed')}
    </div>
  );
}
