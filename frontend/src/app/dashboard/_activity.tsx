'use client';

import { dashTokens, BRAND, MONO } from './_tokens';
import { CardShell } from './_primitives';

// Build an 8-week Mon–Fri grid from an array of Unix timestamps (seconds).
// Returns a 5×8 matrix of intensity levels 0–3.
function buildHeatmap(mtimes: number[]): number[][] {
  const now = new Date();
  // Anchor to the start of the current week's Monday
  const todayDay = now.getDay(); // 0=Sun
  const daysSinceMonday = (todayDay + 6) % 7;
  const thisMonday = new Date(now);
  thisMonday.setDate(now.getDate() - daysSinceMonday);
  thisMonday.setHours(0, 0, 0, 0);

  // Count sessions per calendar date key "YYYY-MM-DD"
  const counts: Record<string, number> = {};
  for (const mt of mtimes) {
    const d = new Date(mt * 1000);
    const key = d.toISOString().slice(0, 10);
    counts[key] = (counts[key] ?? 0) + 1;
  }

  // Grid: 5 rows (Mon–Fri), 8 cols (wk-8 → wk-1)
  const grid: number[][] = Array.from({ length: 5 }, () => new Array(8).fill(0));
  for (let col = 0; col < 8; col++) {         // col 0 = 8 weeks ago, col 7 = current week
    for (let row = 0; row < 5; row++) {        // row 0 = Mon, row 4 = Fri
      const d = new Date(thisMonday);
      d.setDate(thisMonday.getDate() - (7 - col) * 7 + row);
      const key = d.toISOString().slice(0, 10);
      const n = counts[key] ?? 0;
      grid[row][col] = n === 0 ? 0 : n < 2 ? 1 : n < 4 ? 2 : 3;
    }
  }
  return grid;
}

function cellColor(level: number): string {
  return ['var(--heat-0)', 'var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)'][level];
}

export default function ActivityHeatmap({ dark, mtimes }: {
  dark: boolean;
  mtimes: number[];
}) {
  const D = dashTokens(dark);
  const grid = buildHeatmap(mtimes);
  const total = mtimes.length;
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

  return (
    <CardShell dark={dark}>
      {/* Header */}
      <div style={{
        padding: '12px 18px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: `1px solid ${D.divider}`,
      }}>
        <span style={{
          fontFamily: MONO, fontSize: 9, fontWeight: 500,
          color: D.sectionLabel, letterSpacing: '0.85px', textTransform: 'uppercase',
        }}>
          Activity — Last 8 Weeks
        </span>
        <span style={{ fontFamily: MONO, fontSize: 10, color: D.dataMuted, letterSpacing: '0.3px' }}>
          <span style={{ color: D.dataBright, fontWeight: 500 }}>{total}</span> sessions total
        </span>
      </div>

      {/* Grid */}
      <div style={{ padding: '16px 18px 14px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 18px)', gridTemplateRows: 'repeat(5, 18px)', gap: 5 }}>
          {grid.map((row, ri) =>
            row.map((level, ci) => {
              const weekLabel = ci === 7 ? 'this week' : `${8 - ci} weeks ago`;
              return (
                <div
                  key={`${ri}-${ci}`}
                  title={`${DAYS[ri]} · ${weekLabel} · ${
                    level === 0 ? 'no' : level === 1 ? '1' : level === 2 ? '2–3' : '4+'
                  } sessions`}
                  style={{
                    width: 18, height: 18,
                    borderRadius: 3,
                    background: cellColor(level),
                    border: level === 0 ? '1px solid var(--border)' : 'none',
                    cursor: 'default',
                    transition: 'opacity 0.1s',
                  }}
                />
              );
            })
          )}
        </div>

        {/* Legend */}
        <div style={{
          marginTop: 14, display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: MONO, fontSize: 9, color: D.sectionLabel,
          textTransform: 'uppercase', letterSpacing: '0.5px',
        }}>
          <span>Less</span>
          {[0, 1, 2, 3].map(l => (
            <div key={l} style={{
              width: 10, height: 10, borderRadius: 2,
              background: cellColor(l),
              border: l === 0 ? '1px solid var(--border-md)' : 'none',
            }} />
          ))}
          <span>More</span>
        </div>
      </div>
    </CardShell>
  );
}
