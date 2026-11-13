// Come render.mjs, più: "frame" per i fermi immagine a un fotogramma preciso, "frames" [da, a] per un pezzo di video.
// uso: node render-lab.mjs lavori.json  -> [{id, out, props, media?, frame?, frames?}]
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const serveUrl = await bundle({entryPoint: new URL('./src/index.ts', import.meta.url).pathname});
for (const j of jobs) {
  const composition = await selectComposition({serveUrl, id: j.id, inputProps: j.props});
  if (j.media) await renderMedia({composition, serveUrl, outputLocation: j.out, inputProps: j.props, codec: 'h264', crf: 17, audioBitrate: '192k', concurrency: 2, ...(j.frames ? {frameRange: j.frames} : {})});
  else await renderStill({composition, serveUrl, output: j.out, inputProps: j.props, imageFormat: 'png', frame: j.frame ?? 0});
  console.log('ok', j.out);
}
