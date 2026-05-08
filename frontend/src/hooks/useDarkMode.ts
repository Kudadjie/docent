'use client';

import { useState, useEffect } from 'react';

export function useDarkMode(): { dark: boolean; toggleDark: () => void } {
  const [dark, setDark] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      const saved = localStorage.getItem('docent:dark');
      if (saved === 'true') setDark(true);
      setReady(true);
    });
  }, []);

  // Don't touch data-theme until we've read localStorage — avoids overwriting the inline script
  useEffect(() => {
    if (!ready) return;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
    localStorage.setItem('docent:dark', dark ? 'true' : 'false');
  }, [dark, ready]);

  return { dark, toggleDark: () => setDark(d => !d) };
}
