import { ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { fmt, siteName, STATUS_HEX, timeAgo } from '../lib/format';
import type { Source } from '../lib/types';
import { SourceBadge } from './SourceBadge';
import { StatusBadge } from './StatusBadge';

export function SiteCard({ source }: { source: Source }) {
  const { t, i18n } = useTranslation();
  const r = source.latest;
  const lang = i18n.language;
  return (
    <Link
      to={`/site/${source.id}`}
      data-testid="site-card"
      className="card group relative flex flex-col gap-4 border-l-4 p-5"
      style={{ borderLeftColor: STATUS_HEX[source.status_colour] }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-xl leading-tight">{siteName(source, lang)}</h3>
          <p className="text-xs text-muted">
            {t(`kind.${source.kind}`, { defaultValue: source.kind })}
          </p>
        </div>
        <SourceBadge source={source} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge colour={source.status_colour} />
        {r && !source.stale && t(`label.${r.label}`) !== t(`status.${source.status_colour}`) && (
          <span className="text-sm">
            {t(`label.${r.label}`)}
            {r.confidence ? ` · ${fmt(r.confidence, 0)}%` : ''}
          </span>
        )}
      </div>
      {r ? (
        <dl className="grid grid-cols-4 gap-2 text-sm">
          {(['ph', 'tds', 'turb', 'wqi'] as const).map((p) => (
            <div key={p}>
              <dt
                className={`text-[11px] tracking-wide text-muted ${p === 'ph' ? '' : 'uppercase'}`}
              >
                {t(`paramShort.${p}`)}
              </dt>
              <dd className="font-bold tabular-nums">
                {fmt(r[p], p === 'ph' ? 2 : p === 'tds' ? 0 : 1)}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-muted">{t('home.noData')}</p>
      )}
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{r ? t('home.updated', { ago: timeAgo(r.ts, lang) }) : ''}</span>
        <span className="inline-flex items-center gap-1 font-bold uppercase tracking-wide text-ink">
          {t('home.openSite')}
          <ArrowRight
            size={14}
            aria-hidden="true"
            className="transition-transform group-hover:translate-x-1"
          />
        </span>
      </div>
    </Link>
  );
}
