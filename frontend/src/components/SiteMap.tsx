import 'leaflet/dist/leaflet.css';
import { latLngBounds } from 'leaflet';
import { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { Link } from 'react-router-dom';
import { fmt, siteName, STATUS_HEX, timeAgo } from '../lib/format';
import type { Source } from '../lib/types';
import { SourceBadge } from './SourceBadge';
import { StatusBadge } from './StatusBadge';

const NASHIK: [number, number] = [19.99, 73.68];

function FitBounds({ sources }: { sources: Source[] }) {
  const map = useMap();
  const key = sources.map((s) => `${s.id}:${s.lat},${s.lon}`).join('|');
  useEffect(() => {
    if (!sources.length) return;
    map.fitBounds(latLngBounds(sources.map((s) => [s.lat, s.lon])), {
      padding: [36, 36],
      maxZoom: 13,
    });
    // Only refit when the set of sites or their coordinates change, not on every reading.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

export function SiteMap({ sources }: { sources: Source[] }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  // Draw RED last so it sits on top where markers overlap.
  const ordered = useMemo(
    () =>
      [...sources].sort(
        (a, b) => Number(a.status_colour === 'RED') - Number(b.status_colour === 'RED'),
      ),
    [sources],
  );

  return (
    <div
      className="relative isolate h-[58vh] min-h-[340px] w-full md:h-[68vh]"
      role="region"
      aria-label={t('home.mapLabel')}
    >
      <MapContainer center={NASHIK} zoom={11} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds sources={sources} />
        {ordered.map((s) => {
          const r = s.latest;
          const red = s.status_colour === 'RED';
          return (
            <CircleMarker
              key={`${s.id}-${s.status_colour}`}
              center={[s.lat, s.lon]}
              radius={red ? 14 : 11}
              className={`site-marker site-marker--${s.status_colour.toLowerCase()}`}
              pathOptions={{
                color: red ? '#111111' : '#ffffff',
                weight: red ? 3 : 2,
                fillColor: STATUS_HEX[s.status_colour],
                fillOpacity: 0.95,
              }}
            >
              <Popup>
                <div className="min-w-[200px] space-y-2 font-sans text-ink">
                  <p className="font-display text-base font-bold leading-tight">
                    {siteName(s, lang)}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge colour={s.status_colour} size="sm" />
                    <SourceBadge source={s} />
                  </div>
                  {r ? (
                    <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
                      <dt className="text-muted">{t('alerts.label')}</dt>
                      <dd className="font-bold">{t(`label.${r.label}`)}</dd>
                      <dt className="text-muted">{t('param.confidence')}</dt>
                      <dd className="font-bold">
                        {r.confidence ? `${fmt(r.confidence, 0)}%` : '—'}
                      </dd>
                      <dt className="text-muted">WQI</dt>
                      <dd className="font-bold">{fmt(r.wqi, 1)}</dd>
                      <dt className="text-muted">{t('summary.lastUpdate')}</dt>
                      <dd className="font-bold">{timeAgo(r.ts, lang)}</dd>
                    </dl>
                  ) : (
                    <p className="text-xs">{t('home.noData')}</p>
                  )}
                  <Link
                    to={`/site/${s.id}`}
                    className="inline-block text-xs font-bold uppercase tracking-wide !text-water"
                  >
                    {t('home.openSite')} →
                  </Link>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
