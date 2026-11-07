// Send the Arduino's USB readings to the local website:  npm run bridge -- COM5
// Extra options pass through, e.g.  npm run bridge -- COM5 --interval 10 --site ramkund
import path from 'node:path';
import { ROOT, c, run, venvPython } from './lib.mjs';

const [port, ...rest] = process.argv.slice(2);
if (!port) {
  console.log('usage: npm run bridge -- COM5   (find the port in Arduino IDE → Tools → Port)');
  process.exit(2);
}
try {
  run(venvPython(path.join(ROOT, 'backend')), [path.join(ROOT, 'edge', 'serial_bridge.py'), '--port', port, ...rest]);
} catch (e) {
  console.error(c.red(e.message));
  process.exit(1);
}
