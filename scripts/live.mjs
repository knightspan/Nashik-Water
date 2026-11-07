// Feed the HOSTED website from this PC:  npm run live -- COM5
//   * bridge:    your Arduino on the USB port -> Ramkund (real, LIVE)
//   * simulator: the 6 virtual sites (SIMULATED)
// Reads REMOTE_API_URL and REMOTE_API_KEY from hosting.env (git-ignored).
// Options:  --no-sim  (only the sensor)   --no-bridge  (only the simulator)
// Ctrl+C stops both.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { IS_WIN, ROOT, c, readEnv, venvPython } from './lib.mjs';

const argv = process.argv.slice(2);
const flags = new Set(argv.filter((a) => a.startsWith('--')));
const port = argv.find((a) => !a.startsWith('--'));
const envFile = path.join(ROOT, 'hosting.env');
const env = readEnv(envFile);
const api = (env.REMOTE_API_URL || '').replace(/\/$/, '');
const key = env.REMOTE_API_KEY || '';

if (!fs.existsSync(envFile) || !api || !key || key.startsWith('paste')) {
  console.error(
    c.red('hosting.env is missing or incomplete.') +
      '\nCopy hosting.env.example to hosting.env and fill in REMOTE_API_URL and REMOTE_API_KEY.',
  );
  process.exit(1);
}
if (!port && !flags.has('--no-bridge')) {
  console.error('usage: npm run live -- COM5      (or: npm run live -- --no-bridge)');
  process.exit(2);
}

const py = venvPython(path.join(ROOT, 'backend'));
const children = [];
let stopping = false;

function launch(name, colour, args, cwd) {
  const child = spawn(py, ['-u', ...args], { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
  const tag = colour(`[${name}]`.padEnd(9));
  for (const s of [child.stdout, child.stderr]) {
    readline.createInterface({ input: s }).on('line', (l) => console.log(`${tag} ${l}`));
  }
  child.on('exit', (code) => !stopping && console.log(`${tag} ${c.red(`stopped (exit ${code})`)}`));
  children.push(child);
}

function stop() {
  stopping = true;
  for (const ch of children) {
    if (ch.exitCode !== null) continue;
    if (IS_WIN) spawnSync('taskkill', ['/pid', String(ch.pid), '/T', '/F'], { stdio: 'ignore' });
    else ch.kill('SIGTERM');
  }
  process.exit(0);
}
process.on('SIGINT', stop);
process.on('SIGTERM', stop);

console.log(`${c.bold('Sending to')} ${api}\n${c.dim('Ctrl+C stops everything.')}\n`);
if (!flags.has('--no-bridge')) {
  launch('sensor', c.green, [path.join(ROOT, 'edge', 'serial_bridge.py'), '--port', port, '--api', api, '--key', key], ROOT);
}
if (!flags.has('--no-sim')) {
  launch('sim', c.magenta, ['replay.py', '--api', api, '--key', key, '--backfill-hours', '48'], path.join(ROOT, 'simulator'));
}
