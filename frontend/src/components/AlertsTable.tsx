import { CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { dateTime, fmt } from '../lib/format';
import type { Alert } from '../lib/types';
import { StatusBadge } from './StatusBadge';

interface Props {
  alerts: Alert[];
  showSite?: boolean;
  onAck?: (a: Alert) => void;
}

/** Table on wide screens, stacked cards on phones. Newest first. */
export function AlertsTable({ alerts, showSite = true, onAck }: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const name = (a: Alert) => (lang === 'mr' ? a.site_name_mr : a.site_name_en);
  const ackCell = (a: Alert) =>
    a.acknowledged ? (
      <span className="inline-flex items-center gap-1 text-xs">
        <CheckCircle2 size={14} aria-hidden="true" className="text-status-green" />
        {t('alerts.acknowledged')}
        {a.acknowledged_by && (
          <span className="text-muted"> {t('alerts.ackedBy', { who: a.acknowledged_by })}</span>
        )}
      </span>
    ) : onAck ? (
      <button type="button" className="btn-pill !px-3 !py-1 !text-xs" onClick={() => onAck(a)}>
        {t('alerts.ack')}
      </button>
    ) : (
      <span className="text-xs font-bold uppercase">{t('alerts.open')}</span>
    );

  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm" data-testid="alerts-table">
          <thead>
            <tr className="border-b border-line/15 text-left text-xs uppercase tracking-wide text-muted">
              {showSite && (
                <th scope="col" className="py-3 pr-4 font-bold">
                  {t('alerts.site')}
                </th>
              )}
              <th scope="col" className="py-3 pr-4 font-bold">
                {t('alerts.time')}
              </th>
              <th scope="col" className="py-3 pr-4 font-bold">
                {t('alerts.label')}
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-bold">
                {t('alerts.confidence')}
              </th>
              <th scope="col" className="py-3 pr-4 text-right font-bold">
                {t('alerts.wqi')}
              </th>
              <th scope="col" className="py-3 font-bold">
                {t('alerts.state')}
              </th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className="border-b border-line/5 align-top">
                {showSite && (
                  <td className="py-3 pr-4 font-bold">
                    <Link to={`/site/${a.site_id}`} className="hover:underline">
                      {name(a)}
                    </Link>
                  </td>
                )}
                <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{dateTime(a.ts, lang)}</td>
                <td className="py-3 pr-4">
                  <StatusBadge colour="RED" size="sm" />{' '}
                  <span className="ml-1">{t(`label.${a.label}`)}</span>
                  {a.note && (
                    <p className="mt-1 text-xs text-muted">
                      {t('alerts.note')}: {a.note}
                    </p>
                  )}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {a.confidence !== null ? `${fmt(a.confidence, 0)}%` : '—'}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">{fmt(a.wqi, 1)}</td>
                <td className="py-3">{ackCell(a)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="space-y-3 md:hidden">
        {alerts.map((a) => (
          <li key={a.id} className="card space-y-2 border-l-4 border-l-status-red p-4">
            {showSite && (
              <Link
                to={`/site/${a.site_id}`}
                className="block font-display text-lg font-bold leading-tight"
              >
                {name(a)}
              </Link>
            )}
            <p className="text-xs text-muted">{dateTime(a.ts, lang)}</p>
            <p className="flex flex-wrap items-center gap-2 text-sm">
              <StatusBadge colour="RED" size="sm" /> {t(`label.${a.label}`)}
              <span className="text-muted">
                · {a.confidence !== null ? `${fmt(a.confidence, 0)}%` : '—'} · WQI {fmt(a.wqi, 0)}
              </span>
            </p>
            {a.note && (
              <p className="text-xs text-muted">
                {t('alerts.note')}: {a.note}
              </p>
            )}
            <div>{ackCell(a)}</div>
          </li>
        ))}
      </ul>
    </>
  );
}
