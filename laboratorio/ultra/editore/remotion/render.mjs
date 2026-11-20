// uso: node render.mjs lavori.json  -> [{id:"Cap916", out:"out/x.png", props:{...}}]
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
// ULTRA: ULTRA_SCALA=0.5 nei giri di allenamento rende a metà risoluzione (più veloce); senza, 1080x1440
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const serveUrl = await bundle({entryPoint: new URL('./src/index.ts', import.meta.url).pathname});
for (const j of jobs) {
  const composition = await selectComposition({serveUrl, id: j.id, inputProps: j.props});
  if (j.media) await renderMedia({composition, serveUrl, outputLocation: j.out, inputProps: j.props, codec: 'h264', crf: 17, scale: Number(process.env.ULTRA_SCALA || 1), audioBitrate: '192k', concurrency: 1, offthreadVideoCacheSizeInBytes: 256 * 1024 * 1024});  // LAB: tetto di memoria 1,5 GB (con i valori predefiniti il render arrivava a 2,3-2,6 GB)
  else await renderStill({composition, serveUrl, output: j.out, inputProps: j.props, imageFormat: 'png'});
  console.log('ok', j.out);
}
