import { useQueryClient } from '@tanstack/react-query';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from './api';
import type { Source } from './types';

export type LiveMode = 'connecting' | 'live' | 'polling';
const LiveContext = createContext<LiveMode>('connecting');

/** Polling interval used when the SSE stream is not connected. */
export const POLL_MS = 60_000;

/**
 * One EventSource for the whole app. `reading` events patch the cached site list in place
 * (instant marker colour change); `alert` events refresh alert lists. If the stream drops,
 * queries fall back to polling every 60 s (see useRefetchInterval) while the browser retries.
 */
export function LiveProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<LiveMode>('connecting');

  useEffect(() => {
    if (typeof EventSource === 'undefined') {
      setMode('polling');
      return;
    }
    const es = new EventSource(api.streamUrl());
    let failTimer: ReturnType<typeof setTimeout> | undefined;

    es.addEventListener('hello', () => {
      clearTimeout(failTimer);
      setMode('live');
      // Catch up on anything missed while disconnected.
      void qc.invalidateQueries({ queryKey: ['sources'] });
      void qc.invalidateQueries({ queryKey: ['summary'] });
    });
    es.addEventListener('reading', (e) => {
      const src = JSON.parse((e as MessageEvent<string>).data) as Source;
      qc.setQueryData<Source[]>(['sources'], (old) =>
        old ? old.map((s) => (s.id === src.id ? src : s)) : old,
      );
      qc.setQueryData<Source>(['source', src.id], src);
      void qc.invalidateQueries({ queryKey: ['summary'] });
      void qc.invalidateQueries({ queryKey: ['readings', src.id] });
    });
    es.addEventListener('alert', () => {
      void qc.invalidateQueries({ queryKey: ['alerts'] });
      void qc.invalidateQueries({ queryKey: ['summary'] });
    });
    es.onerror = () => {
      clearTimeout(failTimer);
      failTimer = setTimeout(() => setMode('polling'), 3000);
    };
    return () => {
      clearTimeout(failTimer);
      es.close();
    };
  }, [qc]);

  return <LiveContext.Provider value={mode}>{children}</LiveContext.Provider>;
}

export function useLiveMode(): LiveMode {
  return useContext(LiveContext);
}

/** Poll only while the live stream is down. */
export function useRefetchInterval(): number | false {
  return useLiveMode() === 'live' ? false : POLL_MS;
}
