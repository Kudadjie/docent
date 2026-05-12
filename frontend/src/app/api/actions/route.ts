import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';

// spawn-based runner: passes args as an array, avoiding shell quoting issues
function spawnDocent(args: string[], timeoutMs = 30_000): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn('docent', args, { shell: false, timeout: timeoutMs });
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

  let args: string[];
  let timeoutMs = 30_000;
  switch (action) {
    case 'done':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      args = ['reading', 'done', '--id', id];
      break;
    case 'start':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      args = ['reading', 'start', '--id', id];
      break;
    case 'remove':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      args = ['reading', 'remove', '--id', id];
      break;
    case 'move-up':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      args = ['reading', 'move-up', '--id', id];
      break;
    case 'move-down':
      if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 });
      args = ['reading', 'move-down', '--id', id];
      break;
    case 'sync':
      // Sync can take 60-120s: start Mendeley MCP, list folders, list docs, reconcile.
      args = ['reading', 'sync-from-mendeley'];
      timeoutMs = 120_000;
      break;
    case 'queue-clear':
      args = ['reading', 'queue-clear', '--yes'];
      break;
    default:
      return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  }

  try {
    const { stdout, stderr } = await spawnDocent(args, timeoutMs);
    return NextResponse.json({ ok: true, stdout, stderr });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
