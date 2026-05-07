import { NextRequest, NextResponse } from 'next/server';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const USER_PATH = join(homedir(), '.docent', 'user.json');

export interface UserProfile {
  name: string;
  program: string;
  level: string;
}

const EMPTY: UserProfile = { name: '', program: '', level: '' };

export async function GET() {
  try {
    if (!existsSync(USER_PATH)) return NextResponse.json(EMPTY);
    const data = JSON.parse(readFileSync(USER_PATH, 'utf-8')) as UserProfile;
    // Treat old sentinel 'You' (from pre-onboarding skip) as unset
    if (data.name === 'You' && !data.program && !data.level) return NextResponse.json(EMPTY);
    return NextResponse.json({ name: data.name ?? '', program: data.program ?? '', level: data.level ?? '' });
  } catch {
    return NextResponse.json(EMPTY);
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as UserProfile;
    const dir = join(homedir(), '.docent');
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(USER_PATH, JSON.stringify(body, null, 2));
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
