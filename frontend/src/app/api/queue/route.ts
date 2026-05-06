import { NextResponse } from 'next/server';
import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const READING_DIR = join(homedir(), '.docent', 'data', 'reading');
const CONFIG_PATH = join(homedir(), '.docent', 'config.toml');

function parseDatabaseDir(): string | null {
  try {
    if (!existsSync(CONFIG_PATH)) return null;
    const text = readFileSync(CONFIG_PATH, 'utf-8');
    const match = text.match(/\[reading\][\s\S]*?database_dir\s*=\s*"([^"]+)"/);
    if (!match) return null;
    return match[1].replace(/^~/, homedir());
  } catch {
    return null;
  }
}

function countPdfs(dir: string): number {
  try {
    if (!existsSync(dir) || !statSync(dir).isDirectory()) return 0;
    let count = 0;
    const walk = (d: string) => {
      for (const entry of readdirSync(d, { withFileTypes: true })) {
        const full = join(d, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.name.toLowerCase().endsWith('.pdf')) count++;
      }
    };
    walk(dir);
    return count;
  } catch {
    return 0;
  }
}

export async function GET() {
  try {
    const queuePath = join(READING_DIR, 'queue.json');
    const statePath = join(READING_DIR, 'state.json');

    const entries = existsSync(queuePath)
      ? JSON.parse(readFileSync(queuePath, 'utf-8'))
      : [];

    const stateRaw = existsSync(statePath)
      ? JSON.parse(readFileSync(statePath, 'utf-8'))
      : { queued: 0, reading: 0, done: 0, last_updated: null };

    const dbDir = parseDatabaseDir();
    const database_count = dbDir ? countPdfs(dbDir) : null;

    return NextResponse.json({
      entries,
      banner: {
        queued: stateRaw.queued ?? 0,
        reading: stateRaw.reading ?? 0,
        done: stateRaw.done ?? 0,
      },
      last_updated: stateRaw.last_updated ?? null,
      database_count,
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
