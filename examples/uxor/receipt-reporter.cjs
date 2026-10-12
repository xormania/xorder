// Additive PW_TEST_REPORTER observer; project reporter configuration is untouched.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

module.exports = class ReceiptReporter {
  constructor() {
    this.file = process.env.XORDER_TEST_EVENT_FILE;
    this.failed = false;
  }
  printsToStdio() { return false; }
  write(event) {
    if (!this.file || this.failed) return;
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      fs.appendFileSync(this.file, JSON.stringify({ ...event, at: new Date().toISOString() }) + '\n');
    } catch {
      this.failed = true;
      process.stderr.write('xorder: run receipt observer could not write events\n');
    }
  }
  test(test, result) {
    return { id: test.id, title: test.title, title_path: test.titlePath(),
      location: test.location, project: test.parent.project()?.name || '',
      retry: result.retry, worker_index: result.workerIndex,
      parallel_index: result.parallelIndex };
  }
  onBegin(config, suite) {
    const seen = new WeakSet();
    const configuration = JSON.stringify(config, (_, value) => {
      if (typeof value === 'function') return String(value);
      if (value instanceof RegExp) return String(value);
      if (value && typeof value === 'object') {
        if (seen.has(value)) return '[shared object]';
        seen.add(value);
      }
      return value;
    });
    this.write({ event: 'begin', selected_test_count: suite.allTests().length,
      configuration_sha256: crypto.createHash('sha256').update(configuration).digest('hex'),
      demo_url: process.env.DEMO_URL || null,
      projects: config.projects.map(project => ({ name: project.name,
        base_url: project.use.baseURL || null, test_dir: project.testDir })),
      reporter_names: config.reporter.map(reporter => reporter[0]) });
  }
  onTestBegin(test, result) { this.write({ event: 'test_begin', ...this.test(test, result) }); }
  onTestEnd(test, result) {
    this.write({ event: 'test_end', ...this.test(test, result), status: result.status,
      expected_status: test.expectedStatus, duration_ms: result.duration,
      trace_attachments: result.attachments.filter(attachment => attachment.name === 'trace').map(attachment => ({ path: attachment.path || null, content_type: attachment.contentType })),
      errors: result.errors.map(error => ({ message: error.message || null })) });
  }
  onError(error) { this.write({ event: 'error', message: error.message || null }); }
  onEnd(result) { this.write({ event: 'end', status: result.status, duration_ms: result.duration }); }
};
