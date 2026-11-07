// Viva demo: trigger an event on a simulated site while `npm run dev` is running.
//   npm run demo:contamination        (Tapovan turns RED, one alert)
//   npm run demo:rain                 (Nandini turns AMBER)
//   node scripts/demo.mjs contamination ugamsthan 45   (kind, site, minutes)
import path from 'node:path';
import { ROOT, c, readEnv, run, venvPython } from './lib.mjs';

const [kind = 'contamination', site = 'tapovan', minutes] = process.argv.slice(2);
const env = readEnv(path.join(ROOT, 'backend', '.env'));
const args = ['replay.py', '--api', 'http://localhost:8000', '--key', env.INGEST_API_KEY ?? '', '--event', kind, '--site', site];
if (minutes) args.push('--minutes', minutes);
try {
  run(venvPython(path.join(ROOT, 'backend')), args, { cwd: path.join(ROOT, 'simulator') });
} catch (e) {
  console.error(c.red(e.message));
  process.exit(1);
}
