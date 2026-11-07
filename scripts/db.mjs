// Portable PostgreSQL 17 for local development — no Docker, no installer, no admin rights.
// Binaries come from the `embedded-postgres` npm package; data lives in .devdb/ (git-ignored).
//
//   node scripts/db.mjs start | stop | status | reset
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { DB, ROOT, c, quiet, run, venvPython } from './lib.mjs';

async function binaries() {
  const plat = { win32: 'windows', darwin: 'darwin', linux: 'linux' }[process.platform];
  try {
    return await import(`@embedded-postgres/${plat}-${process.arch}`);
  } catch {
    throw new Error('Portable Postgres is not installed yet. Run:  npm run setup');
  }
}

export async function isRunning() {
  const { pg_ctl } = await binaries();
  return fs.existsSync(DB.data) && quiet(pg_ctl, ['status', '-D', DB.data]).status === 0;
}

async function init() {
  if (fs.existsSync(path.join(DB.data, 'PG_VERSION'))) return;
  const { initdb } = await binaries();
  fs.mkdirSync(DB.dir, { recursive: true });
  const pw = path.join(DB.dir, 'pwfile');
  fs.writeFileSync(pw, DB.password);
  console.log(c.dim('Creating the local database cluster in .devdb/ ...'));
  run(initdb, ['-D', DB.data, '-U', DB.user, `--pwfile=${pw}`, '-E', 'UTF8', '--locale=C', '-A', 'scram-sha-256'], {
    stdio: 'ignore',
  });
  fs.rmSync(pw);
}

/** Create the `water` and `water_test` databases if missing (uses the back end's psycopg). */
function ensureDatabases() {
  const py = venvPython(path.join(ROOT, 'backend'));
  if (!fs.existsSync(py)) return; // setup.mjs calls this again once the venv exists
  const code = `
import psycopg
with psycopg.connect("host=localhost port=${DB.port} user=${DB.user} password=${DB.password} dbname=postgres", autocommit=True) as c:
    for name in ("water", "water_test"):
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')
`;
  run(py, ['-c', code]);
}

export async function start() {
  await init();
  if (!(await isRunning())) {
    const { pg_ctl } = await binaries();
    run(pg_ctl, ['start', '-w', '-D', DB.data, '-l', DB.log, '-o', `-p ${DB.port} -c listen_addresses=localhost`], {
      stdio: 'ignore',
    });
  }
  ensureDatabases();
  console.log(c.green(`✓ Postgres running on localhost:${DB.port}`) + c.dim('  (user water / water)'));
}

export async function stop() {
  if (!(await isRunning())) return console.log(c.dim('Postgres is not running.'));
  const { pg_ctl } = await binaries();
  run(pg_ctl, ['stop', '-m', 'fast', '-D', DB.data], { stdio: 'ignore' });
  console.log(c.green('✓ Postgres stopped'));
}

async function main(cmd) {
  if (cmd === 'start') await start();
  else if (cmd === 'stop') await stop();
  else if (cmd === 'status') console.log((await isRunning()) ? `running on localhost:${DB.port}` : 'stopped');
  else if (cmd === 'reset') {
    await stop();
    fs.rmSync(DB.dir, { recursive: true, force: true });
    console.log(c.green('✓ Local database deleted. `npm run dev` creates a fresh one.'));
  } else {
    console.log('usage: node scripts/db.mjs start | stop | status | reset');
    process.exitCode = 2;
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv[2]).catch((e) => {
    console.error(c.red(e.message));
    process.exit(1);
  });
}
