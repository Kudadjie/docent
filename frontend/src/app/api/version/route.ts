import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

function spawnDocent(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn('docent', args, { shell: false, timeout: 10_000 });
    let stdout = '';
    proc.stdout?.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve(stdout.trim());
      else reject(new Error(`exit ${code}`));
    });
    proc.on('error', reject);
  });
}

async function fetchLatestVersion(): Promise<string | null> {
  try {
    const res = await fetch('https://pypi.org/pypi/docent-cli/json', {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    const data = await res.json() as { info: { version: string } };
    return data.info.version ?? null;
  } catch {
    return null;
  }
}

function compareVersions(installed: string, latest: string): boolean {
  // Strip local identifier (+...) and pre/dev suffixes to get the base version.
  // e.g. "1.1.2.dev4+g8434e90" → base "1.1.2"
  const base = installed.split('+')[0].replace(/\.(dev|a|b|rc)\d+$/, '');
  const toInts = (v: string) => v.split('.').map(Number);
  const a = toInts(base);
  const b = toInts(latest);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const ai = a[i] ?? 0, bi = b[i] ?? 0;
    if (ai > bi) return true;
    if (ai < bi) return false;
  }
  // Base equals latest: dev build of the same release is a pre-release (older),
  // but treat as up to date for a local dev workflow.
  return true;
}

export async function GET() {
  try {
    const [versionLine, latest] = await Promise.all([
      spawnDocent(['--version']),
      fetchLatestVersion(),
    ]);
    // "docent 0.1.0" → "0.1.0"
    const installed = versionLine.split(' ').at(-1) ?? versionLine;
    const up_to_date = latest !== null ? compareVersions(installed, latest) : null;
    return NextResponse.json({ installed, latest, up_to_date });
  } catch {
    return NextResponse.json(
      { installed: null, latest: null, up_to_date: null, error: 'Could not determine version' },
      { status: 500 },
    );
  }
}
