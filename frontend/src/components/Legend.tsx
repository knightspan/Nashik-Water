import { useTranslation } from 'react-i18next';
import type { Colour } from '../lib/types';
import { StatusDot } from './StatusBadge';

const ORDER: Colour[] = ['GREEN', 'AMBER', 'RED', 'GREY'];

export function Legend({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="legend-title" className={compact ? '' : 'card p-5'}>
      <h2 id="legend-title" className="eyebrow mb-3 !font-sans !tracking-[0.18em]">
        {t('legend.title')}
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ORDER.map((c) => (
          <li key={c} className="flex items-start gap-3 text-sm">
            <StatusDot colour={c} />
            <span>
              <strong>{t(`status.${c}`)}</strong>
              <span className="text-muted"> — {t(`legend.${c}`)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
