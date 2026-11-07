// Run the whole website locally in ONE terminal — no Docker:  npm run dev
//   database (portable Postgres) -> migrations -> API :8000 -> simulator -> web :5173
// Ctrl+C stops everything.
//
// Options:  --no-sim        don't start the simulator (e.g. when the real Pi is posting)
//           --include-ramkund   also simulate the real node (demo without hardware)
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { IS_WIN, ROOT, c, readEnv, run, usesLocalDb, venvPython } from './lib.mjs';

const args = new Set(process.argv.slice(2));
const BACKEND = path.join(ROOT, 'backend');
const FRONTEND = path.join(ROOT, 'frontend');
const SIM = path.join(ROOT, 'simulator');
const py = venvPython(BACKEND);
const children = [];
let localDb = false;
let stopping = false;

function needSetup(what) {
  console.error(c.red(`${what} is missing. Run first:  npm run setup`));
  process.exit(1);
}

function launch(name, colour, cmd, cmdArgs, opts) {
  const child = spawn(cmd, cmdArgs, { ...opts, stdio: ['ignore', 'pipe', 'pipe'] });
  const tag = colour(`[${name}]`.padEnd(6));
  for (const stream of [child.stdout, child.stderr]) {
    readline.createInterface({ input: stream }).on('line', (line) => console.log(`${tag} ${pretty(line)}`));
  }
  child.on('exit', (code) => {
    if (!stopping) {
      console.log(`${tag} ${c.red(`stopped (exit ${code})`)}`);
      if (name === 'api' || name === 'web') shutdown(1);
    }
  });
  children.push(child);
  return child;
}

/** Make the API's JSON log lines readable in the terminal. */
function pretty(line) {
  if (!line.startsWith('{')) return line;
  try {
    const j = JSON.parse(line);
    if (j.msg === 'request') return c.dim(`${j.method} ${j.path} ${j.status} ${j.ms} ms`);
    const extra = Object.entries(j)
      .filter(([k]) => !['ts', 'level', 'logger', 'msg', 'exc'].includes(k))
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' ');
    const lvl = j.level === 'ERROR' || j.level === 'CRITICAL' ? c.red(j.level) : j.level === 'WARNING' ? c.yellow(j.level) : '';
    return [lvl, j.msg, c.dim(extra), j.exc ? `\n${j.exc}` : ''].filter(Boolean).join(' ');
  } catch {
    return line;
  }
}

function killTree(child) {
  if (child.exitCode !== null) return;
  if (IS_WIN) spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
  else child.kill('SIGTERM');
}

async function shutdown(code = 0) {
  if (stopping) return;
  stopping = true;
  console.log(c.dim('\nStopping ...'));
  children.forEach(killTree);
  if (localDb) await (await import('./db.mjs')).stop();
  process.exit(code);
}

async function main() {
  if (!fs.existsSync(py)) needSetup('backend/.venv');
  if (!fs.existsSync(path.join(FRONTEND, 'node_modules'))) needSetup('frontend/node_modules');
  const envFile = path.join(BACKEND, '.env');
  if (!fs.existsSync(envFile)) needSetup('backend/.env');
  const env = readEnv(envFile);

  process.on('SIGINT', () => shutdown(0));
  process.on('SIGTERM', () => shutdown(0));

  if (usesLocalDb(env.DATABASE_URL)) {
    await (await import('./db.mjs')).start();
    localDb = true;
  } else {
    console.log(c.dim('Using the external database from backend/.env'));
  }

  console.log(c.dim('Applying database migrations ...'));
  run(py, ['-m', 'alembic', 'upgrade', 'head'], { cwd: BACKEND, stdio: ['ignore', 'ignore', 'inherit'] });
  run(py, ['-m', 'app.cli', 'bootstrap'], { cwd: BACKEND, stdio: ['ignore', 'ignore', 'inherit'] });

  launch('api', c.cyan, py, ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'], { cwd: BACKEND });

  if (!args.has('--no-sim')) {
    const simArgs = ['replay.py', '--api', 'http://localhost:8000', '--key', env.INGEST_API_KEY ?? '', '--backfill-hours', '48'];
    if (args.has('--include-ramkund')) simArgs.push('--include-ramkund');
    launch('sim', c.magenta, py, simArgs, { cwd: SIM });
  }

  const vite = path.join(FRONTEND, 'node_modules', 'vite', 'bin', 'vite.js');
  launch('web', c.green, process.execPath, [vite, '--port', '5173', '--strictPort'], {
    cwd: FRONTEND,
    env: { ...process.env, VITE_API_URL: 'http://localhost:8000' },
  });

  console.log(`
${c.bold('Nashik Water Watch is starting')}
  Website   ${c.bold('http://localhost:5173')}
  API docs  http://localhost:8000/docs
  Admin     ${env.ADMIN_EMAIL ?? '(see backend/.env)'} / ${env.ADMIN_PASSWORD ? '(password in backend/.env)' : ''}
  Demo      ${c.dim('in a second terminal:')} npm run demo:contamination
  ${c.dim('Press Ctrl+C to stop everything.')}
`);
}

main().catch(async (e) => {
  console.error(c.red(e.message));
  await shutdown(1);
});
