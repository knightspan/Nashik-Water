import { AlertTriangle, Inbox, RotateCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-sm bg-echo-4 ${className}`} />;
}

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-label={t('state.loading')} className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 border border-dashed border-line/20 px-6 py-10 text-center text-muted">
      <Inbox aria-hidden="true" size={28} strokeWidth={1.5} />
      <p>{children}</p>
    </div>
  );
}

export function ErrorState({ onRetry, message }: { onRetry?: () => void; message?: string }) {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 border border-status-red/40 px-6 py-10 text-center"
    >
      <AlertTriangle aria-hidden="true" size={28} strokeWidth={1.5} className="text-status-red" />
      <p className="font-bold">{message ?? t('state.error')}</p>
      {onRetry && (
        <button type="button" className="btn-pill" onClick={onRetry}>
          <RotateCw size={14} aria-hidden="true" /> {t('state.retry')}
        </button>
      )}
    </div>
  );
}
