import {
  BookOpen,
  Database,
  GraduationCap,
  Languages,
  MapPin,
  Menu,
  Moon,
  Radio,
  Sun,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { API_URL } from '../lib/api';
import { useLiveMode } from '../lib/live';
import { useTheme } from '../lib/theme';
import { OfflineBanner } from './OfflineBanner';

const NAV = [
  { to: '/', key: 'nav.map', end: true },
  { to: '/alerts', key: 'nav.alerts' },
  { to: '/about', key: 'nav.about' },
  { to: '/project', key: 'nav.project' },
  { to: '/admin', key: 'nav.admin' },
];

function LangSwitch() {
  const { t, i18n } = useTranslation();
  const next = i18n.language === 'mr' ? 'en' : 'mr';
  return (
    <button
      type="button"
      onClick={() => void i18n.changeLanguage(next)}
      className="btn-pill !px-3"
      aria-label={`${t('nav.language')}: ${next === 'mr' ? 'मराठी' : 'English'}`}
      data-testid="lang-switch"
    >
      <Languages size={16} aria-hidden="true" />
      <span className="normal-case">{next === 'mr' ? 'मराठी' : 'English'}</span>
    </button>
  );
}

function ThemeToggle() {
  const { t } = useTranslation();
  const { dark, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      className="btn-pill !px-3"
      aria-label={dark ? t('nav.themeLight') : t('nav.themeDark')}
      data-testid="theme-toggle"
    >
      {dark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
    </button>
  );
}

function LiveIndicator() {
  const { t } = useTranslation();
  const mode = useLiveMode();
  if (mode === 'connecting') return null;
  return (
    <p className="hidden items-center gap-1.5 text-xs text-muted xl:flex" aria-live="polite">
      <Radio size={14} aria-hidden="true" className={mode === 'live' ? 'text-status-green' : ''} />
      {mode === 'live' ? t('state.liveOn') : t('state.polling')}
    </p>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-bold uppercase tracking-wide transition-colors duration-150 hover:text-subtle ${isActive ? 'text-ink underline decoration-2 underline-offset-8' : 'text-ink'}`;

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:bg-paper focus:p-2"
      >
        {t('app.skip')}
      </a>
      <header className="sticky top-0 z-[1000] border-b border-line/10 bg-paper/90 backdrop-blur-md">
        <div className="mx-auto flex h-header max-w-7xl items-center justify-between gap-4 px-4 sm:px-8">
          <Link to="/" className="min-w-0">
            <p className="flex items-center gap-2 font-display text-lg font-semibold leading-tight tracking-tight">
              <span aria-hidden="true" className="inline-block h-3 w-3 rounded-full bg-water" />
              {t('app.short')}
            </p>
            <p
              className="hidden max-w-[52ch] truncate text-[11px] text-muted md:block"
              title={t('app.title')}
            >
              {t('app.title')}
            </p>
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-6 lg:flex">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={linkClass}>
                {t(n.key)}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <LiveIndicator />
            <LangSwitch />
            <ThemeToggle />
            <button
              type="button"
              className="btn-pill !px-3 lg:hidden"
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? t('nav.close') : t('nav.menu')}
              onClick={() => setOpen((o) => !o)}
            >
              {open ? <X size={16} aria-hidden="true" /> : <Menu size={16} aria-hidden="true" />}
            </button>
          </div>
        </div>
        {open && (
          <nav
            id="mobile-nav"
            aria-label="Main"
            className="border-t border-line/10 px-4 pb-4 lg:hidden"
          >
            <ul className="flex flex-col">
              {NAV.map((n) => (
                <li key={n.to} className="border-b border-line/10">
                  <NavLink
                    to={n.to}
                    end={n.end}
                    className={({ isActive }) =>
                      `block py-3 font-display text-2xl font-bold tracking-tight ${isActive ? 'text-water' : ''}`
                    }
                  >
                    {t(n.key)}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>
      <OfflineBanner />

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-white/5 bg-[#1e1e1e] text-[#f6f6f6]/60">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:grid-cols-2 sm:px-8 lg:grid-cols-4">
          <div>
            <p className="mb-3 font-display text-xl font-semibold tracking-tight text-[#f6f6f6]">
              {t('app.short')}
            </p>
            <p className="text-sm leading-relaxed">{t('footer.summary')}</p>
          </div>
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-[#f6f6f6]/80">
              {t('footer.explore')}
            </p>
            <ul className="space-y-2 text-sm">
              {NAV.slice(0, 4).map((n) => (
                <li key={n.to}>
                  <Link to={n.to} className="hover:text-[#f6f6f6]">
                    {t(n.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-[#f6f6f6]/80">
              {t('footer.project')}
            </p>
            <ul className="space-y-3 text-sm">
              <li className="flex gap-2">
                <GraduationCap size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                {t('app.college')}
              </li>
              <li className="flex gap-2">
                <BookOpen size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                {t('app.course')}
              </li>
              <li className="flex gap-2">
                <MapPin size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                Nashik, Maharashtra
              </li>
            </ul>
          </div>
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-[#f6f6f6]/80">
              {t('footer.data')}
            </p>
            <ul className="space-y-3 text-sm">
              <li className="flex gap-2">
                <Database size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
                <a
                  href={`${API_URL}/docs`}
                  className="hover:text-[#f6f6f6]"
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('footer.api')}
                </a>
              </li>
              <li className="text-xs leading-relaxed">{t('footer.disclaimer')}</li>
            </ul>
          </div>
        </div>
        <p className="border-t border-white/5 px-4 py-4 text-center text-xs">
          {t('app.college')} · {t('app.course')}
        </p>
      </footer>
    </div>
  );
}
