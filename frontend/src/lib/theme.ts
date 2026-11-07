import { useCallback, useEffect, useState } from 'react';

/** Light/dark mode. The inline script in index.html applies the saved choice before paint. */
export function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    document
      .querySelector('meta[name="color-scheme"]')
      ?.setAttribute('content', dark ? 'dark' : 'light');
  }, [dark]);

  const toggle = useCallback(() => {
    setDark((d) => {
      try {
        localStorage.setItem('theme', d ? 'light' : 'dark');
      } catch {
        /* storage blocked */
      }
      return !d;
    });
  }, []);

  return { dark, toggle };
}
