import { readFile, writeFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { createServer } from 'vite';

const server = await createServer({ server: { middlewareMode: true, watch: null, hmr: false }, appType: 'custom', logLevel: 'error' });
try {
  const { runResearch } = await server.ssrLoadModule('/src/engine/research.ts');
  const { archiveDataset, parseArchiveJSON } = await server.ssrLoadModule('/src/engine/archive.ts');
  const { DEFAULT_SETTINGS } = await server.ssrLoadModule('/src/engine/contracts.ts');
  const manifest = JSON.parse(await readFile('src/engine/archive-manifest.json', 'utf8'));
  for (const instrument of ['XAUUSD', 'NAS100']) {
    const bars = [];
    for (const item of manifest[instrument]) {
      const bytes = await readFile(`public/quotes/${item.file}`);
      if (createHash('sha256').update(bytes).digest('hex') !== item.sha256) throw Error(`Archive checksum failed: ${item.file}`);
      const rows = parseArchiveJSON(gunzipSync(bytes).toString('utf8'));
      if (rows.length !== item.rows) throw Error(`Archive row count failed: ${item.file}`);
      bars.push(...rows);
    }
    const source = await archiveDataset(instrument, bars);
    const report = await runResearch(source, DEFAULT_SETTINGS);
    await writeFile(`public/quotes/ready-${instrument}.json`, JSON.stringify(report));
    console.log(JSON.stringify({ instrument, source: source.profile.source_symbol, bars: source.bars.length, last_close: source.bars.at(-1).close, horizons: Object.fromEntries(Object.entries(report.datasets[0].horizons).map(([k, h]) => [k, { n: h.models[0]?.test.n, coverage90: h.models[0]?.test.coverage['0.9'] }])) }));
  }
} finally {
  await server.close();
}
