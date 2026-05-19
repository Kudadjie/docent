'use client';

import { useEffect } from 'react';

export function useDarkMode(): { dark: boolean; toggleDark: () => void } {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
  }, []);
  return { dark: true, toggleDark: () => {} };
}
