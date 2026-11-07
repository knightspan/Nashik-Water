import { screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';
import { i18n, reading, renderWithProviders, source } from '../test/utils';
import { Legend } from './Legend';
import { OfflineBanner } from './OfflineBanner';
import { SiteCard } from './SiteCard';
import { StatusBadge } from './StatusBadge';
import { SummaryBar } from './SummaryBar';

beforeEach(async () => {
  await i18n.changeLanguage('en');
});

describe('StatusBadge', () => {
  it.each([
    ['GREEN', 'Normal'],
    ['AMBER', 'Natural change'],
    ['RED', 'Contamination'],
    ['GREY', 'No verdict'],
  ] as const)('%s always carries a text label', (colour, text) => {
    renderWithProviders(<StatusBadge colour={colour} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('is translated to Marathi', async () => {
    await i18n.changeLanguage('mr');
    renderWithProviders(<StatusBadge colour="RED" />);
    expect(screen.getByText('प्रदूषण')).toBeInTheDocument();
  });
});

describe('SiteCard', () => {
  it('shows LIVE for a real node with fresh data', () => {
    renderWithProviders(<SiteCard source={source()} />);
    expect(screen.getByText('Live')).toBeInTheDocument();
    expect(screen.queryByText('Simulated')).not.toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/site/ramkund');
  });

  it('shows SIMULATED for a virtual node', () => {
    renderWithProviders(
      <SiteCard
        source={source({ id: 'tapovan', simulated: true, latest: reading({ synthetic: true }) })}
      />,
    );
    expect(screen.getByText('Simulated')).toBeInTheDocument();
  });

  it('shows DATA DELAYED and GREY for a stale real node', () => {
    renderWithProviders(
      <SiteCard
        source={source({
          stale: true,
          status_colour: 'GREY',
          latest: reading({ ts: new Date(Date.now() - 3600_000).toISOString() }),
        })}
      />,
    );
    expect(screen.getByText('Data delayed')).toBeInTheDocument();
    expect(screen.getByText('No verdict')).toBeInTheDocument();
  });

  it('handles a site with no data yet', () => {
    renderWithProviders(
      <SiteCard source={source({ latest: null, stale: true, status_colour: 'GREY' })} />,
    );
    expect(screen.getByText('No data received yet')).toBeInTheDocument();
  });

  it('uses the Marathi site name in Marathi', async () => {
    await i18n.changeLanguage('mr');
    renderWithProviders(<SiteCard source={source()} />);
    expect(screen.getByRole('heading', { name: 'रामकुंड' })).toBeInTheDocument();
  });
});

describe('SummaryBar', () => {
  it('shows counts per colour and active alerts', () => {
    renderWithProviders(
      <SummaryBar
        summary={{
          colours: { GREEN: 4, AMBER: 1, RED: 1, GREY: 1 },
          sites: 7,
          stale_sites: 1,
          active_alerts: 2,
          last_update: new Date().toISOString(),
        }}
      />,
    );
    expect(screen.getByTestId('count-GREEN')).toHaveTextContent('4');
    expect(screen.getByTestId('count-RED')).toHaveTextContent('1');
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Active alerts')).toBeInTheDocument();
  });
});

describe('Legend', () => {
  it('explains all four colours in words', () => {
    renderWithProviders(<Legend />);
    for (const word of ['Normal', 'Natural change', 'Contamination', 'No verdict']) {
      expect(screen.getByText(word)).toBeInTheDocument();
    }
  });
});

describe('OfflineBanner', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('appears when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    renderWithProviders(<OfflineBanner />);
    await waitFor(() => expect(screen.getByTestId('offline-banner')).toHaveTextContent(/Offline/), {
      timeout: 4000,
    });
  });

  it('warns when data is older than 15 minutes', async () => {
    const old = new Date(Date.now() - 20 * 60_000).toISOString();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            colours: {},
            sites: 7,
            stale_sites: 7,
            active_alerts: 0,
            last_update: old,
          }),
          { status: 200 },
        ),
      ),
    );
    renderWithProviders(<OfflineBanner />);
    await waitFor(() =>
      expect(screen.getByTestId('offline-banner')).toHaveTextContent(/Data delayed/),
    );
  });

  it('stays hidden when data is fresh', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          colours: {},
          sites: 7,
          stale_sites: 0,
          active_alerts: 0,
          last_update: new Date().toISOString(),
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    renderWithProviders(<OfflineBanner />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
  });
});
