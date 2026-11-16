#!/usr/bin/env node
'use strict';
const {spawnSync} = require('node:child_process');
const {join, resolve, basename} = require('node:path');
const {existsSync, realpathSync, mkdirSync} = require('node:fs');
const {homedir} = require('node:os');
function fail(message) { console.error(message); process.exit(3); }
if (process.platform !== 'linux') fail('This native recorder supports Linux only.');
const root = join(process.env.XDG_DATA_HOME || join(homedir(), '.local/share'), 'shrutadhara', 'npm-runtime');
const python = join(root, 'bin/python');
function run(command, args, timeout) {
  const result = spawnSync(command, args, {stdio: 'inherit', shell: false, timeout});
  if (result.error) fail(result.error.message);
  return result.status === null ? 3 : result.status;
}
const args = process.argv.slice(2);
if (args[0] === 'setup-native') {
  if (args.length !== 2 || !args[1].endsWith('.whl')) fail('Usage: shruta setup-native /absolute/path/to/shrutadhara-VERSION-py3-none-any.whl');
  const wheel = resolve(args[1]);
  const version = require('./package.json').version;
  if (basename(wheel) !== `shrutadhara-${version}-py3-none-any.whl`) fail(`Setup requires the matching reviewed shrutadhara-${version}-py3-none-any.whl release.`);
  if (!existsSync(wheel)) fail('Local wheel does not exist. Build it from the reviewed source with uv build.');
  console.error('Explicit local setup: system Python/GTK, FFmpeg and pactl are required. No system packages or services will be changed. pip may fetch Python dependencies.');
  mkdirSync(root, {recursive: true, mode: 0o700});
  if (!existsSync(python) && run('/usr/bin/python3', ['-m', 'venv', '--system-site-packages', root], 180000)) process.exit(3);
  process.exit(run(python, ['-m', 'pip', 'install', '--force-reinstall', '--no-input', '--disable-pip-version-check', '--timeout', '10', '--retries', '1', '--only-binary=:all:', wheel], 180000));
}
const override = process.env.SHRUTA_NATIVE_EXECUTABLE;
if (override) {
  if (!override.startsWith('/') || !existsSync(override)) fail('SHRUTA_NATIVE_EXECUTABLE must be an existing absolute native executable.');
  if (realpathSync(override) === realpathSync(__filename)) fail('Refusing recursive launcher configuration.');
  process.exit(run(override, args));
}
if (!existsSync(python)) fail('Native runtime is not configured. Run shruta setup-native /path/to/reviewed.whl, or set SHRUTA_NATIVE_EXECUTABLE to an absolute native meeting command. See npm/README.md.');
process.exit(run(python, ['-m', 'shrutadhara', ...args]));
