'use client';

import { useState, useEffect } from 'react';

const DARK_KEY = 'docent:dark';

export function useDarkMode(): { dark: boolean; toggleDark: () => void } {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(DARK_KEY);
    const isDark = stored === null ? true : stored === 'true';
    setDark(isDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }, []);

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
