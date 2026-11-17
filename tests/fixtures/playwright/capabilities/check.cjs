const { chromium, firefox, webkit } = require('/opt/playwright/node_modules/playwright');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const pixel = require('./pixel.cjs');
(async () => {
  const rgba = execFileSync('fc-match', ['-f', '%{rgba}', 'monospace'], { encoding: 'utf8' }).trim();
  assert.equal(rgba, '1', 'RGB subpixel font configuration');
  const subject = readFileSync(path.join(__dirname, 'render.html'), 'utf8');
  const versions = {};
  for (const [name, engine] of Object.entries({ chromium, firefox, webkit })) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({ viewport: { width: 640, height: 480 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.setContent(subject);
      await page.click('#proof');
      assert.equal(await page.textContent('#result'), 'passed', `${name} DOM interaction`);
      const font = await page.evaluate(async () => {
        await document.fonts.ready;
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        context.font = '20px monospace';
        return { narrow: context.measureText('iiii').width, wide: context.measureText('WWWW').width,
                 label: document.querySelector('#text').textContent };
      });
      assert.ok(font.narrow > 0 && font.narrow === font.wide, `${name} monospace text metrics`);
      assert.equal(font.label, 'Image tools: café 123');
      const sample = await page.screenshot({ clip: { x: 20, y: 20, width: 1, height: 1 } });
      assert.deepEqual(pixel(sample), [12, 34, 56], `${name} rendered screenshot color`);
      await page.screenshot({ path: `/workspace/${name}.png` });
      assert.deepEqual(errors, [], `${name} page errors`);
      versions[name] = browser.version();
    } finally { await browser.close(); }
  }
  console.log(JSON.stringify({ rgba: Number(rgba), engines: versions,
    checks: ['dom-interaction', 'unicode-text', 'monospace-font', 'rendered-pixel', 'screenshot'] }));
})().catch(error => { console.error(error); process.exit(1); });
