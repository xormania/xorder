// Resolve this process's memory cgroup inside the container, including host namespaces.
const fs = require('node:fs');
const path = require('node:path').posix;

function probe(reader = fs) {
  const read = filename => {
    try { return reader.readFileSync(filename, 'utf8').trim(); }
    catch { return null; }
  };
  const decode = value => value.replace(/\\([0-7]{3})/g, (_, octal) => String.fromCharCode(parseInt(octal, 8)));
  const membership = read('/proc/self/cgroup');
  const mountinfo = read('/proc/self/mountinfo');
  if (membership === null || mountinfo === null) return { unavailable: 'memory cgroup membership unavailable' };
  const groups = membership.split('\n').map(line => line.split(':'));
  const mounts = mountinfo.split('\n').map(line => {
    const [before, after] = line.split(' - ');
    return { fields: before.split(' '), extra: (after || '').split(' ') };
  });
  for (const version of [2, 1]) {
    const group = groups.find(row => row.length === 3 && (version === 2
      ? row[0] === '0' && row[1] === '' : row[1].split(',').includes('memory')));
    if (!group || !group[2].startsWith('/') || group[2].split('/').includes('..')) continue;
    for (const mount of mounts) {
      const matches = version === 2 ? mount.extra[0] === 'cgroup2'
        : mount.extra[0] === 'cgroup' && (mount.extra[2] || '').split(',').includes('memory');
      if (!matches) continue;
      const root = decode(mount.fields[3] || '');
      const point = decode(mount.fields[4] || '');
      if (!root.startsWith('/') || !point.startsWith('/')) continue;
      const relative = group[2] === root ? '/' : group[2].startsWith(root.replace(/\/$/, '') + '/')
        ? group[2].slice(root.length) : group[2];
      const directory = path.join(point, relative).replace(/\/$/, '') || '/';
      const files = version === 2
        ? ['memory.max', 'memory.current', 'memory.peak', 'memory.events', 'memory.events.local']
        : ['memory.limit_in_bytes', 'memory.usage_in_bytes', 'memory.max_usage_in_bytes', 'memory.oom_control', 'memory.failcnt'];
      const values = Object.fromEntries(files.map(name => [name, read(path.join(directory, name))]));
      if (Object.values(values).some(value => value !== null)) return { version, directory, files: values };
    }
  }
  return { unavailable: 'memory cgroup files unavailable' };
}

module.exports = probe;
