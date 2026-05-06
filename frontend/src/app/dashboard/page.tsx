import Sidebar from '@/components/Sidebar';

export default function DashboardPage() {
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar active="dashboard" queueCount={0} />
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 8,
          color: 'var(--fg4)',
          fontFamily: 'var(--sans)',
        }}
      >
        <span style={{ fontSize: 32, opacity: 0.3 }}>◻</span>
        <span style={{ fontSize: 13 }}>Dashboard — coming soon</span>
      </main>
    </div>
  );
}
