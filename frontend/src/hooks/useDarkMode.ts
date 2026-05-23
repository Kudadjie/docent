'use client';

import { useState, useEffect } from 'react';

const DARK_KEY = 'docent:dark';

export function useDarkMode(): { dark: boolean; toggleDark: () => void } {
  const [dark, setDark] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const stored = localStorage.getItem(DARK_KEY);
    if (stored !== null) return stored === 'true';
    // No stored preference — match the OS setting (same as the CSS media query)
    return !window.matchMedia('(prefers-color-scheme: light)').matches;
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }, [dark]);

  function toggleDark() {
    setDark(prev => {
      const next = !prev;
      localStorage.setItem(DARK_KEY, String(next));
      document.documentElement.setAttribute('data-theme', next ? 'dark' : 'light');
      return next;
    });
  }

  return { dark, toggleDark };
}
