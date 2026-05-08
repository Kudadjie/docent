'use client';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';

export default function DashboardPage() {
  const { dark, toggleDark } = useDarkMode();

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="dashboard" queueCount={0} dark={dark} />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} />
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 8,
          color: 'var(--fg4)',
          fontFamily: 'var(--sans)',
        }}>
          <span style={{ fontSize: 32, opacity: 0.3 }}>◻</span>
          <span style={{ fontSize: 13 }}>Dashboard — coming soon</span>
        </div>
      </main>
    </div>
  );
}
