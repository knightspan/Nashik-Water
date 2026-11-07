// Shared helpers for the local (no-Docker) dev scripts.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const IS_WIN = process.platform === 'win32';

export const DB = {
  dir: path.join(ROOT, '.devdb'),
  data: path.join(ROOT, '.devdb', 'data'),
  log: path.join(ROOT, '.devdb', 'postgres.log'),
  port: Number(process.env.DEV_DB_PORT || 5433), // 5433 so it never clashes with an installed Postgres
  user: 'water',
  password: 'water',
};

export const LOCAL_DB_URL = `postgresql+psycopg://${DB.user}:${DB.password}@localhost:${DB.port}/water`;
export const LOCAL_TEST_DB_URL = `postgresql+psycopg://${DB.user}:${DB.password}@localhost:${DB.port}/water_test`;

export function venvPython(dir) {
  return path.join(dir, '.venv', IS_WIN ? 'Scripts' : 'bin', IS_WIN ? 'python.exe' : 'python');
}

/** Run a command, streaming its output; throw if it fails. */
export function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (res.error) throw res.error;
  if (res.status !== 0) {
    throw new Error(`${path.basename(cmd)} ${args.join(' ')} exited with ${res.status}`);
  }
  return res;
}

export function quiet(cmd, args, opts = {}) {
  return spawnSync(cmd, args, { encoding: 'utf8', ...opts });
}

/** Minimal KEY=VALUE .env reader (comments and blank lines ignored). */
export function readEnv(file) {
  const out = {};
  if (!fs.existsSync(file)) return out;
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const i = line.indexOf('=');
    out[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^["']|["']$/g, '');
  }
  return out;
}

/** True when DATABASE_URL points at the portable dev database managed by these scripts. */
export function usesLocalDb(databaseUrl) {
  return !databaseUrl || new RegExp(`@(localhost|127\\.0\\.0\\.1):${DB.port}/`).test(databaseUrl);
}

/** First Python ≥ 3.11 found on this machine: [command, ...prefixArgs]. */
export function findPython() {
  const candidates = [
    process.env.PYTHON ? [process.env.PYTHON] : null,
    IS_WIN ? ['py', '-3.11'] : null,
    IS_WIN ? ['py', '-3.12'] : null,
    IS_WIN ? ['py', '-3.13'] : null,
    ['python3'],
    ['python'],
  ].filter(Boolean);
  for (const [cmd, ...pre] of candidates) {
    const r = quiet(cmd, [...pre, '-c', 'import sys; print(sys.version_info >= (3, 11))']);
    if (r.status === 0 && r.stdout.trim() === 'True') return [cmd, ...pre];
  }
  throw new Error('Python 3.11 or newer was not found. Install it from https://www.python.org/ (tick "Add to PATH").');
}

export const c = {
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  cyan: (s) => `\x1b[36m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  magenta: (s) => `\x1b[35m${s}\x1b[0m`,
};
