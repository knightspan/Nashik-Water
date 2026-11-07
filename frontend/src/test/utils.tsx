import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../i18n';
import type { Reading, Source } from '../lib/types';

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper, ...options });
}

export { i18n };

export function reading(over: Partial<Reading> = {}): Reading {
  return {
    ts: new Date(Date.now() - 2 * 60_000).toISOString(),
    ph: 7.81,
    tds: 331.2,
    turb: 17.8,
    temp: 24.6,
    wqi: 241.6,
    wqi_band: 'unfit',
    label: 'Normal',
    colour: 'GREEN',
    confidence: 97,
    health: 'ok',
    synthetic: false,
    latency_ms: 12.5,
    ...over,
  };
}

export function source(over: Partial<Source> = {}): Source {
  return {
    id: 'ramkund',
    name_en: 'Ramkund (Godavari ghats)',
    name_mr: 'रामकुंड',
    kind: 'river',
    lat: 20.0074,
    lon: 73.7924,
    simulated: false,
    active: true,
    description_en: '',
    description_mr: '',
    latest: reading(),
    stale: false,
    status_colour: 'GREEN',
    ...over,
  };
}
