'use client';

import { useEffect } from 'react';
import type { DriveStep } from 'driver.js';
import { tourHasSeen, tourMarkSeen, type TourKey } from '@/lib/tour';

export function useTour(key: TourKey, steps: DriveStep[], delayMs = 800): void {
  useEffect(() => {
    if (tourHasSeen(key)) return;

    let cancelled = false;
    const timer = setTimeout(async () => {
      if (cancelled) return;
      const { driver } = await import('driver.js');
      await import('driver.js/dist/driver.css');
      if (cancelled) return;

      const d = driver({
        showProgress: true,
        allowClose: true,
        steps,
        onDestroyed: () => tourMarkSeen(key),
        onDestroyStarted: () => { tourMarkSeen(key); d.destroy(); },
      });
      d.drive();
    }, delayMs);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []); // intentionally empty — fire once on first mount
}
