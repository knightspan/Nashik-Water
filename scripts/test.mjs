// Run the website's test suites locally (no Docker):  npm test
//   back end (pytest, against the portable Postgres) · simulator · front end (Vitest)
import path from 'node:path';
import { IS_WIN, LOCAL_TEST_DB_URL, ROOT, c, run, venvPython } from './lib.mjs';

const py = venvPython(path.join(ROOT, 'backend'));
const db = await import('./db.mjs');
const wasRunning = await db.isRunning();
let failed = false;

function suite(name, fn) {
  console.log(`\n${c.bold(c.cyan(`== ${name}`))}`);
  try {
    fn();
  } catch {
    failed = true;
    console.log(c.red(`✗ ${name} failed`));
  }
}

await db.start();
suite('Back end (pytest)', () =>
  run(py, ['-m', 'pytest', '-q', '-p', 'no:logging'], {
    cwd: path.join(ROOT, 'backend'),
    env: { ...process.env, TEST_DATABASE_URL: process.env.TEST_DATABASE_URL ?? LOCAL_TEST_DB_URL },
  }),
);
suite('Simulator (pytest)', () => run(py, ['-m', 'pytest', '-q', '-p', 'no:cacheprovider'], { cwd: path.join(ROOT, 'simulator') }));
suite('Front end (Vitest)', () =>
  run(IS_WIN ? 'npm.cmd' : 'npm', ['test'], { cwd: path.join(ROOT, 'frontend'), shell: IS_WIN }),
);
if (!wasRunning) await db.stop();

console.log(failed ? c.red('\nSome tests failed.') : c.green('\nAll tests passed.'));
process.exit(failed ? 1 : 0);
