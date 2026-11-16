#!/usr/bin/env node
'use strict';
const {spawnSync} = require('node:child_process');
const {join, resolve, basename} = require('node:path');
const {existsSync, realpathSync, mkdirSync, readFileSync, lstatSync} = require('node:fs');
const {createHash} = require('node:crypto');
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
function checkRuntime() {
  // Refuse redirected or shared writable managed directories before executing code.
  for (const directory of [join(root, '..'), root, join(root, 'bin')]) {
    if (!existsSync(directory)) continue;
    const st = lstatSync(directory);
    if (st.isSymbolicLink() || !st.isDirectory() || st.uid !== process.getuid() || (st.mode & 0o022)) fail('Unsafe managed runtime directory: ' + directory);
  }
}
const args = process.argv.slice(2);
if (args[0] === 'setup-native') {
  process.umask(0o077);
  if (args.length > 2 || (args[1] && !args[1].endsWith('.whl'))) fail('Usage: shruta setup-native [path/to/reviewed.whl]');
  let wheel;
  if (args[1]) {
    wheel = resolve(args[1]);
  } else {
    const manifestPath = join(__dirname, 'native/manifest.json');
    if (!existsSync(manifestPath)) fail('This source launcher has no bundled wheel. Use a packed release or supply a reviewed local wheel.');
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    if (typeof manifest.filename !== 'string' || basename(manifest.filename) !== manifest.filename || !/^[a-f0-9]{64}$/.test(manifest.sha256)) fail('Invalid bundled wheel manifest.');
    wheel = join(__dirname, 'native', manifest.filename);
    if (!existsSync(wheel) || createHash('sha256').update(readFileSync(wheel)).digest('hex') !== manifest.sha256) fail('Bundled wheel checksum mismatch; reinstall the reviewed npm release.');
  }
  const version = require('./package.json').version;
  if (basename(wheel) !== `shrutadhara-${version}-py3-none-any.whl`) fail(`Setup requires the matching reviewed shrutadhara-${version}-py3-none-any.whl release.`);
  if (!existsSync(wheel)) fail('Local wheel does not exist. Build it from the reviewed source with uv build.');
  console.error('Explicit local setup: system Python/GTK, FFmpeg and pactl are required. No system packages or services will be changed. pip may fetch Python dependencies.');
  checkRuntime();
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
checkRuntime();
if (!existsSync(python)) fail('Native runtime is not configured. Run shruta setup-native, or set SHRUTA_NATIVE_EXECUTABLE to an absolute native shruta command. See npm/README.md.');
process.exit(run(python, ['-m', 'shrutadhara', ...args]));
