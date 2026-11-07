import { Cpu, Database, LineChart, Radio, Server, Waves } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { EchoText } from '../components/EchoText';

const TEAM = ['Vishal Shivaji Patil', 'Bhagyashri Sadashiv Patil', 'Kavish Naveen Joshi'];

const STACK = [
  { Icon: Waves, title: 'Sensors', key: 'sensors' },
  { Icon: Cpu, title: 'ESP32-C3 stations', key: 'nodes' },
  { Icon: Radio, title: 'Raspberry Pi 5 (optional)', key: 'pi' },
  { Icon: Server, title: 'FastAPI + PostgreSQL', key: 'api' },
  { Icon: LineChart, title: 'React + Leaflet + Recharts', key: 'web' },
  { Icon: Database, title: 'Vercel · Render · Neon', key: 'hosting' },
];

// From ml/reports/metrics.json (test dataset never used for training or tuning).
const RESULTS = [
  { value: '98.8%', key: 'accuracy' },
  { value: '0.971', key: 'macroF1' },
  { value: '96.8%', key: 'recall' },
  { value: '27 / 27', key: 'events' },
];

export default function ProjectPage() {
  const { t } = useTranslation();
  return (
    <div>
      <section className="overflow-hidden px-4 pb-8 pt-12 text-center sm:px-8">
        <p className="eyebrow mb-4">{t('project.title')}</p>
        <EchoText
          text="NASHIK"
          as="p"
          className="font-display text-[clamp(2.6rem,10vw,8rem)] font-bold tracking-tightest"
        />
        <h1 className="mx-auto mt-8 max-w-4xl text-[clamp(1.5rem,3.6vw,2.75rem)] leading-tight">
          {t('app.title')}
        </h1>
      </section>

      <div className="mx-auto h-16 w-px bg-line/10" aria-hidden="true" />

      <section className="mx-auto max-w-4xl px-4 py-10 text-center sm:px-8">
        <h2 className="sr-only">{t('project.abstractTitle')}</h2>
        <p className="font-display text-[clamp(1.6rem,4vw,3rem)] font-bold leading-tight tracking-tight">
          {t('project.quoteA')}
          <em className="font-serif font-normal italic">{t('project.quoteEm')}</em>
          {t('project.quoteB')}
        </p>
        <p className="mt-8 text-left text-muted sm:text-center">{t('project.abstract')}</p>
      </section>

      <section className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-8 md:grid-cols-3">
        <div>
          <h3 className="mb-2 text-xl">{t('project.team')}</h3>
          <ul className="space-y-1 text-muted">
            {TEAM.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-xl">{t('project.guide')}</h3>
          <p className="text-muted">Prof. M. V. Raut</p>
          <h3 className="mb-2 mt-6 text-xl">{t('project.department')}</h3>
          <p className="text-muted">{t('project.departmentValue')}</p>
        </div>
        <div>
          <h3 className="mb-2 text-xl">{t('project.college')}</h3>
          <p className="text-muted">{t('project.collegeValue')}</p>
          <h3 className="mb-2 mt-6 text-xl">{t('project.course')}</h3>
          <p className="text-muted">{t('project.courseValue')}</p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-8">
        <h2 className="mb-6 text-3xl">{t('project.resultsTitle')}</h2>
        <dl className="grid grid-cols-2 border-l border-t border-line/10 lg:grid-cols-4">
          {RESULTS.map((r) => (
            <div key={r.key} className="border-b border-r border-line/10 p-6">
              <dd className="font-display text-4xl font-bold tracking-tight">{r.value}</dd>
              <dt className="mt-1 text-sm text-muted">{t(`project.results.${r.key}`)}</dt>
            </div>
          ))}
        </dl>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-8">
        <h2 className="mb-6 text-3xl">{t('project.stackTitle')}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {STACK.map(({ Icon, title, key }) => (
            <article key={title} className="card group p-6">
              <span className="mb-4 flex h-16 w-16 items-center justify-center border border-line/20 transition-transform duration-300 group-hover:rotate-12">
                <Icon size={26} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <h3 className="mb-1 text-xl">{title}</h3>
              <p className="text-sm text-muted">{t(`project.stack.${key}`)}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
