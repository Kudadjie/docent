import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

interface ToolResult {
  name: string;
  label: string;
  installed: string | null;
  latest: string | null;
  up_to_date: boolean | null;
  upgrade_cmd: string;
}

function spawnCommand(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const command = process.platform === 'win32' && cmd === 'npm' ? 'npm.cmd' : cmd;
    const proc = spawn(command, args, { shell: false, timeout: 15_000 });
    let stdout = '';
    let stderr = '';
    proc.stdout?.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d: Buffer) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 || stdout) resolve(stdout.trim());
      else reject(new Error(stderr.trim() || `exit ${code}`));
    });
    proc.on('error', reject);
  });
}

async function fetchNpmLatest(pkg: string): Promise<string | null> {
  try {
    const encoded = pkg.replace('@', '%40').replace('/', '%2F');
    const res = await fetch(`https://registry.npmjs.org/${encoded}/latest`, {
      headers: { Accept: 'application/json' },
      next: { revalidate: 0 }, // always fresh on manual check
    });
    if (!res.ok) return null;
    const data = await res.json() as { version?: string };
    return data.version ?? null;
  } catch {
    return null;
  }
}

async function getNpmInstalled(pkg: string): Promise<string | null> {
  try {
    const out = await spawnCommand('npm', ['list', '-g', pkg, '--json', '--depth=0']);
    const data = JSON.parse(out) as { dependencies?: Record<string, { version?: string }> };
    return data.dependencies?.[pkg]?.version ?? null;
  } catch {
    return null;
  }
}

function compareVersions(installed: string, latest: string): boolean {
  const toInts = (v: string) => v.replace(/^v/, '').split('.').map(Number);
  const a = toInts(installed);
  const b = toInts(latest);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const ai = a[i] ?? 0, bi = b[i] ?? 0;
    if (ai > bi) return true;
    if (ai < bi) return false;
  }
  return true;
}

const TOOLS = [
  {
    name: '@companion-ai/feynman',
    label: 'Feynman',
    upgrade_cmd: 'npm install -g @companion-ai/feynman',
  },
];

export async function GET() {
  const results: ToolResult[] = await Promise.all(
    TOOLS.map(async (tool) => {
      const [installed, latest] = await Promise.all([
        getNpmInstalled(tool.name),
        fetchNpmLatest(tool.name),
      ]);
      const up_to_date =
        installed !== null && latest !== null
          ? compareVersions(installed, latest)
          : null;
      return { ...tool, installed, latest, up_to_date };
    }),
  );
  return NextResponse.json(results);
}
