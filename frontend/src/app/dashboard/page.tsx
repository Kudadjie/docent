'use client';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';
import { useTour } from '@/hooks/useTour';

export default function DashboardPage() {
  const { dark, toggleDark } = useDarkMode();

  useTour('dashboard', [
    {
      popover: {
        title: 'Welcome to Docent',
        description: "Docent is your grad school AI — a single place to manage your reading, run research, and stay on top of your academic work. Let's take a quick look around.",
      },
    },
    {
      element: 'nav[aria-label="Main navigation"]',
      popover: {
        title: 'Navigate Docent',
        description: 'Reading manages your paper queue and syncs with Mendeley. Studio runs AI-powered research sessions. Ecosystem and Docs cover your tools and guides.',
      },
    },
    {
      popover: {
        title: 'Your overview',
        description: 'As you use Reading and Studio, your activity will appear here as summary cards. Think of Dashboard as your at-a-glance home base.',
      },
    },
  ]);

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
          backgroundImage: `
            ${dark
              ? 'linear-gradient(135deg, rgba(24,226,153,0.07) 0%, rgba(139,92,246,0.04) 45%, transparent 75%)'
              : 'linear-gradient(135deg, rgba(24,226,153,0.22) 0%, rgba(139,92,246,0.13) 45%, transparent 75%)'
            },
            radial-gradient(circle, var(--gray200) 1px, transparent 1px)
          `,
          backgroundSize: 'cover, 24px 24px',
        }}>
          <span style={{ fontSize: 32, opacity: 0.3 }}>◻</span>
          <span style={{ fontSize: 13 }}>Dashboard — coming soon</span>
        </div>
      </main>
    </div>
  );
}
