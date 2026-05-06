import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

function safeId(id: string): string {
  return id.replace(/[^a-zA-Z0-9_\-./]/g, '');
}

export async function POST(req: NextRequest) {
  const body = await req.json() as { action: string; id?: string };
  const { action, id } = body;

  let cmd: string;
  switch (action) {
    case 'done':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      cmd = `docent reading done --id "${safeId(id)}"`;
      break;
    case 'start':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      cmd = `docent reading start --id "${safeId(id)}"`;
      break;
    case 'remove':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      cmd = `docent reading remove --id "${safeId(id)}"`;
      break;
    case 'scan':
      cmd = 'docent reading scan';
      break;
    case 'sync':
      cmd = 'docent reading sync-from-mendeley';
      break;
    default:
      return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  }

  try {
    const { stdout, stderr } = await execAsync(cmd, { timeout: 30_000 });
    return NextResponse.json({ ok: true, stdout, stderr });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
