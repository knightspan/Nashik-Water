import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from 'recharts';
import { DIGITS, fmt, redRuns, STATUS_HEX, UNITS } from '../lib/format';
import type { Param, SeriesPoint } from '../lib/types';

interface Props {
  points: SeriesPoint[];
  param: Param;
  hours: number;
}

function ChartTooltip({
  active,
  payload,
  param,
  lang,
}: TooltipProps<number, string> & { param: Param; lang: string }) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as { t: number; v: number | null; colour: string | null };
  return (
    <div className="rounded-sm border border-line/15 bg-surface px-3 py-2 text-xs shadow-sm">
      <p className="text-muted">
        {new Intl.DateTimeFormat(lang === 'mr' ? 'mr-IN' : 'en-IN', {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'Asia/Kolkata',
        }).format(p.t)}
      </p>
      <p className="font-bold text-ink">
        {fmt(p.v, DIGITS[param])} {UNITS[param]}
      </p>
      {p.colour && <p className="text-muted">{t(`status.${p.colour}`)}</p>}
    </div>
  );
}

/** One parameter over time: 2px ink line, recessive grid, RED periods shaded, crosshair tooltip. */
export function ParamChart({ points, param, hours }: Props) {
  const { t, i18n } = useTranslation();
  const data = useMemo(
    () => points.map((p) => ({ t: new Date(p.ts).getTime(), v: p[param], colour: p.colour })),
    [points, param],
  );
  const runs = useMemo(() => {
    // A one-reading RED period would have zero width: pad it by half a sampling step.
    const step =
      data.length > 1 ? (data[data.length - 1].t - data[0].t) / (data.length - 1) : 60_000;
    return redRuns(data).map(
      ([a, b]) => (a === b ? [a - step / 2, b + step / 2] : [a, b]) as [number, number],
    );
  }, [data]);
  const tickFmt = useMemo(() => {
    const opts: Intl.DateTimeFormatOptions =
      hours <= 24
        ? { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' }
        : { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' };
    const f = new Intl.DateTimeFormat(i18n.language === 'mr' ? 'mr-IN' : 'en-IN', opts);
    return (v: number) => f.format(v);
  }, [hours, i18n.language]);

  const unit = UNITS[param];
  return (
    <figure className="card p-4" data-testid={`chart-${param}`}>
      <figcaption className="mb-2 flex items-baseline justify-between gap-2">
        <span className="font-display text-lg font-bold tracking-tight">{t(`param.${param}`)}</span>
        {unit && <span className="text-xs text-muted">{unit}</span>}
      </figcaption>
      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke="rgb(var(--line) / 0.08)" />
            {runs.map(([a, b]) => (
              <ReferenceArea
                key={a}
                x1={a}
                x2={b}
                fill={STATUS_HEX.RED}
                fillOpacity={0.14}
                strokeOpacity={0}
                ifOverflow="hidden"
              />
            ))}
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={tickFmt}
              tick={{ fontSize: 11, fill: 'rgb(var(--muted))' }}
              axisLine={{ stroke: 'rgb(var(--line) / 0.2)' }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'rgb(var(--muted))' }}
              axisLine={false}
              tickLine={false}
              width={48}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => fmt(v, param === 'ph' ? 1 : 0)}
            />
            {param === 'wqi' && (
              <ReferenceLine
                y={50}
                stroke="rgb(var(--fg))"
                strokeDasharray="5 4"
                strokeWidth={1}
                ifOverflow="extendDomain"
                label={{
                  value: t('site.wqiLimit'),
                  position: 'insideTopRight',
                  fontSize: 10,
                  fill: 'rgb(var(--muted))',
                }}
              />
            )}
            <Tooltip
              content={<ChartTooltip param={param} lang={i18n.language} />}
              cursor={{ stroke: 'rgb(var(--fg))', strokeWidth: 1, strokeDasharray: '3 3' }}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="rgb(var(--fg))"
              strokeWidth={2}
              dot={false}
              activeDot={{
                r: 4,
                stroke: 'rgb(var(--surface))',
                strokeWidth: 2,
                fill: 'rgb(var(--fg))',
              }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
