import type { Band, Colour, Site, Source } from './types';

export const STATUS_HEX: Record<Colour, string> = {
  GREEN: '#2e7d32',
  AMBER: '#f9a825',
  RED: '#c62828',
  GREY: '#9e9e9e',
};

/** Text colour on a status fill that meets WCAG AA. */
export const STATUS_ON: Record<Colour, string> = {
  GREEN: '#ffffff',
  AMBER: '#111111',
  RED: '#ffffff',
  GREY: '#111111',
};

const SEVERITY: Record<Colour, number> = { RED: 0, AMBER: 1, GREY: 2, GREEN: 3 };

/** RED first, then AMBER, GREY, GREEN; ties by name. */
export function sortBySeverity(sources: Source[], lang: string): Source[] {
  return [...sources].sort(
    (a, b) =>
      SEVERITY[a.status_colour] - SEVERITY[b.status_colour] ||
      siteName(a, lang).localeCompare(siteName(b, lang)),
  );
}

export function siteName(site: Pick<Site, 'name_en' | 'name_mr'>, lang: string): string {
  return lang === 'mr' ? site.name_mr || site.name_en : site.name_en;
}

export function siteDescription(site: Site, lang: string): string {
  return lang === 'mr' ? site.description_mr || site.description_en : site.description_en;
}

export function fmt(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(digits);
}

export const DIGITS: Record<string, number> = { ph: 2, tds: 0, turb: 1, temp: 1, wqi: 1 };
export const UNITS: Record<string, string> = {
  ph: '',
  tds: 'mg/L',
  turb: 'NTU',
  temp: '°C',
  wqi: '',
};

export function timeAgo(iso: string | null | undefined, lang: string, now = Date.now()): string {
  if (!iso) return '—';
  const diffS = Math.round((new Date(iso).getTime() - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' });
  const abs = Math.abs(diffS);
  if (abs < 45) return rtf.format(0, 'second');
  if (abs < 3600) return rtf.format(Math.round(diffS / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(diffS / 3600), 'hour');
  return rtf.format(Math.round(diffS / 86400), 'day');
}

export function dateTime(iso: string | null | undefined, lang: string): string {
  if (!iso) return '—';
  return new Intl.DateTimeFormat(lang === 'mr' ? 'mr-IN' : 'en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(iso));
}

export function bandOf(wqi: number | null | undefined): Band | null {
  if (wqi === null || wqi === undefined) return null;
  if (wqi <= 25) return 'excellent';
  if (wqi <= 50) return 'good';
  if (wqi <= 75) return 'poor';
  if (wqi <= 100) return 'very_poor';
  return 'unfit';
}

export const BANDS: { key: Band; range: string }[] = [
  { key: 'excellent', range: '0–25' },
  { key: 'good', range: '26–50' },
  { key: 'poor', range: '51–75' },
  { key: 'very_poor', range: '76–100' },
  { key: 'unfit', range: '> 100' },
];

/** Badge to show for a site: simulated data, a live real node, or a delayed real node. */
export function sourceBadge(s: Source): 'simulated' | 'live' | 'delayed' {
  if (s.simulated || s.latest?.synthetic) return 'simulated';
  return s.stale ? 'delayed' : 'live';
}

/** Start/end timestamps of consecutive RED points, for background shading. */
export function redRuns(points: { t: number; colour: string | null }[]): [number, number][] {
  const out: [number, number][] = [];
  let start: number | null = null;
  points.forEach((p, i) => {
    if (p.colour === 'RED' && start === null) start = p.t;
    const endsHere =
      p.colour === 'RED' && (i === points.length - 1 || points[i + 1].colour !== 'RED');
    if (endsHere && start !== null) {
      out.push([start, i + 1 < points.length ? points[i + 1].t : p.t]);
      start = null;
    }
  });
  return out;
}
