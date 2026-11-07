import { useTranslation } from 'react-i18next';
import { BANDS, fmt, STATUS_HEX } from '../lib/format';
import type { Colour, Stats } from '../lib/types';
import { StatusDot } from './StatusBadge';

const COLOURS: Colour[] = ['GREEN', 'AMBER', 'RED', 'GREY'];
// Sequential single-hue ramp (light -> dark) for WQI bands: magnitude, not status.
const BAND_SHADE = ['#c9dcf0', '#93b8df', '#5d93c9', '#2d6aa8', '#0b3f73'];

function Meter({
  pct,
  color,
  label,
  value,
}: {
  pct: number;
  color: string;
  label: React.ReactNode;
  value: string;
}) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-x-3 gap-y-1 text-sm">
      <span className="flex items-center gap-2">{label}</span>
      <span className="text-right font-bold tabular-nums">{value}</span>
      <span className="col-span-2 h-2 w-full rounded-full bg-echo-4" aria-hidden="true">
        <span
          className="block h-2 rounded-full"
          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
        />
      </span>
    </li>
  );
}

export function StatsPanel({ stats }: { stats: Stats }) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <section className="card p-5">
        <h3 className="mb-1 text-lg">{t('site.timeInColour')}</h3>
        <p className="mb-4 text-xs text-muted">{t('site.readings', { count: stats.count })}</p>
        <ul className="space-y-3">
          {COLOURS.map((c) => (
            <Meter
              key={c}
              pct={stats.colours[c]}
              color={STATUS_HEX[c]}
              label={
                <>
                  <StatusDot colour={c} /> {t(`status.${c}`)}
                </>
              }
              value={`${fmt(stats.colours[c], 1)}%`}
            />
          ))}
        </ul>
      </section>
      <section className="card p-5">
        <h3 className="mb-1 text-lg">{t('site.timeInBand')}</h3>
        <p className="mb-4 text-xs text-muted">WQI</p>
        <ul className="space-y-3">
          {BANDS.map((b, i) => (
            <Meter
              key={b.key}
              pct={stats.wqi_bands[b.key]}
              color={BAND_SHADE[i]}
              label={
                <>
                  {b.key === 'unfit' ? t('band.unfitShort') : t(`band.${b.key}`)}{' '}
                  <span className="text-xs text-muted">({b.range})</span>
                </>
              }
              value={`${fmt(stats.wqi_bands[b.key], 1)}%`}
            />
          ))}
        </ul>
      </section>
      <section className="card overflow-x-auto p-5 md:col-span-2">
        <table className="w-full min-w-[420px] text-sm">
          <caption className="sr-only">{t('site.stats')}</caption>
          <thead>
            <tr className="border-b border-line/10 text-left text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="py-2 font-bold" />
              <th scope="col" className="py-2 text-right font-bold">
                {t('site.min')}
              </th>
              <th scope="col" className="py-2 text-right font-bold">
                {t('site.median')}
              </th>
              <th scope="col" className="py-2 text-right font-bold">
                {t('site.mean')}
              </th>
              <th scope="col" className="py-2 text-right font-bold">
                {t('site.max')}
              </th>
            </tr>
          </thead>
          <tbody>
            {(['ph', 'tds', 'turb', 'temp', 'wqi'] as const).map((p) => (
              <tr key={p} className="border-b border-line/5">
                <th scope="row" className="py-2 text-left font-bold">
                  {t(`param.${p}`)}
                </th>
                {(['min', 'median', 'mean', 'max'] as const).map((m) => (
                  <td key={m} className="py-2 text-right tabular-nums">
                    {fmt(stats.params[p][m], p === 'ph' ? 2 : 1)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
