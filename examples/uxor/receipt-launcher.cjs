// Keep a cancellable process group in the container; Docker client exit alone
// does not guarantee that its exec payload has stopped.
const fs = require('node:fs');
const path = require('node:path');
const { constants: { signals } } = require('node:os');
const { spawn } = require('node:child_process');
const args = process.argv.slice(2);
const stopping = args[0] === '--stop';
const directory = stopping ? args[1] : process.env.XORDER_TEST_CONTROL_DIR;
if (!directory) throw new Error('xorder test control directory is required');
fs.mkdirSync(directory, { recursive: true });
const record = path.join(directory, 'process.json');
const cancelled = path.join(directory, 'cancelled');
function startTime(pid) {
  try { return fs.readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' ')[19]; }
  catch { return null; }
}
function groupState(pid) {
  try { process.kill(-pid, 0); } catch (error) { return error.code === 'ESRCH' ? 'stopped' : 'unknown'; }
  try {
    let found = false;
    let unreadable = false;
    for (const entry of fs.readdirSync('/proc')) {
      if (!/^\d+$/.test(entry)) continue;
      let state;
      try { state = fs.readFileSync(`/proc/${entry}/stat`, 'utf8').split(') ')[1].split(' '); }
      catch { unreadable = true; continue; }
      if (Number(state[2]) !== pid) continue;
      found = true;
      if (state[0] !== 'Z' && state[0] !== 'X') return 'running';
    }
    return found && !unreadable ? 'stopped' : 'unknown';
  } catch { return 'unknown'; }
}
if (stopping) {
  fs.writeFileSync(cancelled, 'cancelled\n');
  if (!fs.existsSync(record)) process.exit(1);
  const target = JSON.parse(fs.readFileSync(record, 'utf8'));
  if (!Number.isSafeInteger(target.pid) || target.pid < 2 || !target.start_time) process.exit(1);
  const currentStart = startTime(target.pid);
  if (currentStart && currentStart !== target.start_time) process.exit(1);
  if (groupState(target.pid) === 'stopped') process.exit(0);
  try { process.kill(-target.pid, 'SIGTERM'); } catch (error) { process.exit(error.code === 'ESRCH' ? 0 : 1); }
  const began = Date.now();
  let killed = false;
  const timer = setInterval(() => {
    if (groupState(target.pid) === 'stopped') { clearInterval(timer); process.exit(0); }
    if (Date.now() - began > 10000 && !killed) {
      killed = true;
      try { process.kill(-target.pid, 'SIGKILL'); } catch {}
    }
    if (Date.now() - began > 15000) {
      clearInterval(timer);
      process.exit(1);
    }
  }, 50);
} else {
  if (fs.existsSync(cancelled)) process.exit(130);
  const child = spawn('npx', ['playwright', 'test', ...args], { stdio: 'inherit', detached: true });
  let timer;
  function stop() {
    try { process.kill(-child.pid, 'SIGTERM'); } catch {}
    timer ||= setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL'); } catch {} }, 10000);
  }
  child.on('spawn', () => {
    fs.writeFileSync(record, JSON.stringify({ pid: child.pid, start_time: startTime(child.pid) }));
    if (fs.existsSync(cancelled)) stop();
  });
  child.on('error', error => { process.stderr.write(`xorder test launcher: ${error.message}\n`); process.exitCode = 64; });
  child.on('close', (code, signal) => {
    if (timer) clearTimeout(timer);
    process.exitCode = code === null ? 128 + (signals[signal] || 0) : code;
  });
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  process.on('SIGHUP', stop);
}
