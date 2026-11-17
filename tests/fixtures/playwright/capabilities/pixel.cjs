const assert = require('node:assert/strict');
const { inflateSync } = require('node:zlib');

// A single pixel has no preceding pixel or row: every PNG filter leaves its
// first RGB samples unchanged. Playwright emits 8-bit RGB or RGBA screenshots.
module.exports = function firstPixel(png) {
  assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  const data = [];
  let channels;
  for (let offset = 8; offset < png.length;) {
    const size = png.readUInt32BE(offset);
    const type = png.subarray(offset + 4, offset + 8).toString();
    const bytes = png.subarray(offset + 8, offset + 8 + size);
    assert.ok(offset + size + 12 <= png.length, 'Truncated screenshot');
    if (type === 'IHDR') {
      assert.equal(bytes.readUInt32BE(0), 1, 'Pixel sample width');
      assert.equal(bytes.readUInt32BE(4), 1, 'Pixel sample height');
      assert.equal(bytes[8], 8, '8-bit screenshot');
      assert.ok([2, 6].includes(bytes[9]), 'RGB or RGBA screenshot');
      assert.equal(bytes[12], 0, 'Non-interlaced screenshot');
      channels = bytes[9] === 2 ? 3 : 4;
    } else if (type === 'IDAT') {
      data.push(bytes);
    }
    offset += size + 12;
  }
  const row = inflateSync(Buffer.concat(data));
  assert.equal(row.length, channels + 1, 'One pixel scanline');
  assert.ok(row[0] <= 4, 'Known PNG filter');
  if (channels === 4) assert.equal(row[4], 255, 'Opaque rendered sample');
  return [...row.subarray(1, 4)];
};
