import { NextRequest, NextResponse } from 'next/server';
import { readFileSync, existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { spawn } from 'child_process';

const CONFIG_PATH = join(homedir(), '.docent', 'config.toml');

function parseReadingSection(): { database_dir: string | null; queue_collection: string } {
  try {
    if (!existsSync(CONFIG_PATH)) return { database_dir: null, queue_collection: 'Reading Queue' };
    const text = readFileSync(CONFIG_PATH, 'utf-8');
    const sectionMatch = text.match(/\[reading\]([\s\S]*?)(?=\n\[|$)/);
    const section = sectionMatch ? sectionMatch[1] : '';
    const dbDir = section.match(/database_dir\s*=\s*"([^"]*)"/)?.[1] ?? null;
    const collection = section.match(/queue_collection\s*=\s*"([^"]*)"/)?.[1] ?? 'Docent-Queue';
    return { database_dir: dbDir, queue_collection: collection };
  } catch {
    return { database_dir: null, queue_collection: 'Reading Queue' };
  }
}

function spawnDocent(args: string[]): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn('docent', args, { shell: true, timeout: 15_000 });
    let stdout = '';
    let stderr = '';
    proc.stdout?.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on('data', (d: Buffer) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(Object.assign(new Error(stderr || stdout || `exit ${code}`), { stdout, stderr }));
    });
    proc.on('error', reject);
  });
}

export async function GET() {
  const reading = parseReadingSection();
  return NextResponse.json({ reading });
}

export async function POST(req: NextRequest) {
  const body = await req.json() as { section: string; key: string; value: string };
  const { section, key, value } = body;

  if (section === 'reading') {
    try {
      await spawnDocent(['reading', 'config-set', '--key', key, '--value', value]);
      const reading = parseReadingSection();
      return NextResponse.json({ ok: true, reading });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      return NextResponse.json({ ok: false, error: msg }, { status: 500 });
    }
  }

  return NextResponse.json({ error: `Unknown section: ${section}` }, { status: 400 });
}
