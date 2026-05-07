import { NextRequest, NextResponse } from 'next/server';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

function safeId(id: string): string {
  return id.replace(/[^a-zA-Z0-9_\-./]/g, '');
}

// spawn-based runner: passes args as an array, avoiding shell quoting issues
function spawnDocent(args: string[]): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn('docent', args, { shell: true, timeout: 30_000 });
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

export async function POST(req: NextRequest) {
  const body = await req.json() as Record<string, unknown>;
  const action = body.action as string;
  const id = body.id as string | undefined;

  // edit: use spawn so notes/tags with arbitrary text are passed safely
  if (action === 'edit') {
    if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
    const { status, order, deadline, notes, tags } = body as {
      status?: string; order?: number; deadline?: string; notes?: string; tags?: string[];
    };
    const args = ['reading', 'edit', '--id', id];
    if (status)                args.push('--status', status);
    if (order != null)         args.push('--order', String(order));
    if (deadline !== undefined) args.push('--deadline', deadline);
    if (notes !== undefined)   args.push('--notes', notes);
    if (tags)                  tags.forEach(t => args.push('--tags', t));
    try {
      const { stdout, stderr } = await spawnDocent(args);
      return NextResponse.json({ ok: true, stdout, stderr });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      return NextResponse.json({ ok: false, error: msg }, { status: 500 });
    }
  }

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
    case 'move-up':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      cmd = `docent reading move-up --id "${safeId(id)}"`;
      break;
    case 'move-down':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      cmd = `docent reading move-down --id "${safeId(id)}"`;
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
