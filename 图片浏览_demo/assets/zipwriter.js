// Minimal dependency-free ZIP writer (STORE method, no compression).
// PNG/JSON payloads are added as-is; store mode avoids needing a deflate lib
// and works offline. Supports UTF-8 filenames (GP flag bit 11).
// Exposes window.createZipBlob(entries) where entries = [{path, data:Uint8Array}].
(function () {
  const CRC_TABLE = (function () {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(buf) {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function dosDateTime(d) {
    const date = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    const time = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
    return { date: date & 0xffff, time: time & 0xffff };
  }

  const enc = new TextEncoder();

  // createZipBlob(entries): entries = [{ path: string, data: Uint8Array }]
  window.createZipBlob = function createZipBlob(entries) {
    const { date, time } = dosDateTime(new Date());
    const chunks = [];
    const central = [];
    let offset = 0;

    for (const entry of entries) {
      const nameBytes = enc.encode(entry.path);
      const data = entry.data instanceof Uint8Array ? entry.data : new Uint8Array(entry.data);
      const crc = crc32(data);
      const size = data.length;

      // Local file header (30 bytes + name)
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); // local file header signature
      lh.setUint16(4, 20, true); // version needed
      lh.setUint16(6, 0x0800, true); // GP flag: bit 11 => UTF-8 filename
      lh.setUint16(8, 0, true); // method 0 = store
      lh.setUint16(10, time, true);
      lh.setUint16(12, date, true);
      lh.setUint32(14, crc, true);
      lh.setUint32(18, size, true); // compressed size (== size for store)
      lh.setUint32(22, size, true); // uncompressed size
      lh.setUint16(26, nameBytes.length, true);
      lh.setUint16(28, 0, true); // extra len

      chunks.push(new Uint8Array(lh.buffer), nameBytes, data);

      // Central directory record (46 bytes + name)
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); // central dir signature
      ch.setUint16(4, 20, true); // version made by
      ch.setUint16(6, 20, true); // version needed
      ch.setUint16(8, 0x0800, true); // GP flag UTF-8
      ch.setUint16(10, 0, true); // method store
      ch.setUint16(12, time, true);
      ch.setUint16(14, date, true);
      ch.setUint32(16, crc, true);
      ch.setUint32(20, size, true);
      ch.setUint32(24, size, true);
      ch.setUint16(28, nameBytes.length, true);
      ch.setUint16(30, 0, true); // extra len
      ch.setUint16(32, 0, true); // comment len
      ch.setUint16(34, 0, true); // disk number start
      ch.setUint16(36, 0, true); // internal attrs
      ch.setUint32(38, 0, true); // external attrs
      ch.setUint32(42, offset, true); // local header offset
      central.push(new Uint8Array(ch.buffer), nameBytes);

      offset += 30 + nameBytes.length + size;
    }

    const centralStart = offset;
    let centralSize = 0;
    for (const c of central) centralSize += c.length;

    const eocd = new DataView(new ArrayBuffer(22));
    eocd.setUint32(0, 0x06054b50, true); // EOCD signature
    eocd.setUint16(4, 0, true); // disk number
    eocd.setUint16(6, 0, true); // disk with central dir
    eocd.setUint16(8, entries.length, true); // entries on this disk
    eocd.setUint16(10, entries.length, true); // total entries
    eocd.setUint32(12, centralSize, true);
    eocd.setUint32(16, centralStart, true);
    eocd.setUint16(20, 0, true); // comment len

    return new Blob([...chunks, ...central, new Uint8Array(eocd.buffer)], {
      type: "application/zip",
    });
  };
})();
