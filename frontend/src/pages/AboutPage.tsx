import { ArrowDown, ArrowRight, Cloud, Cpu, Globe, ShieldAlert, Waves, Wifi } from 'lucide-react';
import { Fragment } from 'react';
import { useTranslation } from 'react-i18next';
import { Legend } from '../components/Legend';
import { BANDS } from '../lib/format';

const FLOW = [
  { key: 'sensors', Icon: Waves },
  { key: 'station', Icon: Cpu },
  { key: 'wifi', Icon: Wifi },
  { key: 'cloud', Icon: Cloud },
  { key: 'web', Icon: Globe },
] as const;

const PARAMS = [
  { key: 'ph', unit: '—', limit: '6.5 – 8.5' },
  { key: 'tds', unit: 'mg/L', limit: '≤ 500' },
  { key: 'turb', unit: 'NTU', limit: '≤ 5' },
  { key: 'temp', unit: '°C', limit: '—' },
] as const;

export default function AboutPage() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-8 sm:py-14">
      <h1 className="text-[clamp(2.5rem,8vw,5.5rem)] leading-crush">{t('about.title')}</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted">{t('about.lede')}</p>

      <section aria-labelledby="flow-title" className="mt-14">
        <h2 id="flow-title" className="mb-6 text-3xl">
          {t('about.flowTitle')}
        </h2>
        <ol className="flex flex-col items-stretch gap-2 lg:flex-row lg:items-stretch">
          {FLOW.map(({ key, Icon }, i) => (
            <Fragment key={key}>
              <li className="card flex flex-1 flex-col gap-3 p-5">
                <span className="flex h-12 w-12 items-center justify-center border border-line/20">
                  <Icon size={22} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <span className="eyebrow">0{i + 1}</span>
                <span className="font-display text-xl font-bold tracking-tight">
                  {t(`about.flow.${key}`)}
                </span>
                <span className="text-sm text-muted">{t(`about.flow.${key}Text`)}</span>
              </li>
              {i < FLOW.length - 1 && (
                <li aria-hidden="true" className="flex items-center justify-center text-subtle">
                  <ArrowDown size={20} className="lg:hidden" />
                  <ArrowRight size={20} className="hidden lg:block" />
                </li>
              )}
            </Fragment>
          ))}
        </ol>
      </section>

      <section aria-labelledby="params-title" className="mt-16">
        <h2 id="params-title" className="mb-6 text-3xl">
          {t('about.paramsTitle')}
        </h2>
        <div className="grid gap-px border border-line/10 bg-line/10 sm:grid-cols-2">
          {PARAMS.map((p) => (
            <article key={p.key} className="bg-paper p-6">
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <h3 className="text-2xl">{t(`param.${p.key}`)}</h3>
                <span className="text-xs text-muted">
                  {p.unit} · BIS {p.limit}
                </span>
              </div>
              <p className="text-muted">{t(`about.params.${p.key}`)}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="wqi-title" className="mt-16 grid gap-10 lg:grid-cols-2">
        <div className="min-w-0">
          <h2 id="wqi-title" className="mb-4 text-3xl">
            {t('about.wqiTitle')}
          </h2>
          <p className="mb-4">{t('about.wqiText')}</p>
          <pre className="mb-4 overflow-x-auto border border-line/10 bg-surface p-4 text-xs leading-relaxed">
            {`Q(pH)   = 100·(pH−7)/1.5   if pH ≥ 7
        = 100·(7−pH)/0.5   if pH < 7
Q(TDS)  = 100·TDS/500
Q(turb) = 100·NTU/5
WQI     = 0.368·Q(pH) + 0.006·Q(TDS) + 0.626·Q(turb)`}
          </pre>
          <p className="text-sm text-muted">{t('about.wqiNote')}</p>
        </div>
        <div className="min-w-0">
          <h3 className="mb-4 text-2xl">{t('about.bandsTitle')}</h3>
          <table className="w-full text-sm">
            <tbody>
              {BANDS.map((b) => (
                <tr key={b.key} className="border-b border-line/10">
                  <th
                    scope="row"
                    className="py-3 pr-4 text-left font-display text-lg font-bold tabular-nums tracking-tight"
                  >
                    {b.range}
                  </th>
                  <td className="py-3">{t(`band.${b.key}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="colours-title" className="mt-16 grid gap-10 lg:grid-cols-2">
        <div>
          <h2 id="colours-title" className="mb-4 text-3xl">
            {t('about.coloursTitle')}
          </h2>
          <Legend compact />
        </div>
        <div>
          <h2 className="mb-4 text-3xl">{t('about.aiTitle')}</h2>
          <p className="text-muted">{t('about.aiText')}</p>
        </div>
      </section>

      <section
        aria-labelledby="limits-title"
        className="mt-16 border-2 border-ink p-6 sm:p-8"
        data-testid="limitations"
      >
        <h2 id="limits-title" className="mb-4 flex items-center gap-3 text-3xl">
          <ShieldAlert aria-hidden="true" size={28} strokeWidth={1.5} /> {t('about.limitsTitle')}
        </h2>
        <ul className="space-y-3 text-lg">
          <li>{t('about.limits.one')}</li>
          <li className="font-bold">{t('about.limits.two')}</li>
          <li>{t('about.limits.three')}</li>
        </ul>
      </section>
    </div>
  );
}
