// Renders scene segments from a manifest. One process, one bundle, one browser:
// the per-render startup cost is paid once, however many scenes are dirty.
//
//   node render-segments.mjs <manifest.json>
//
// manifest: { storageRoot, mode: "draft" | "final", jobs: [{ id, outKey, props }] }
//
// Progress is written to stdout as one JSON object per line:
//   {event:"start"|"progress"|"done"|"error"|"all_done", ...}
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bundle } from '@remotion/bundler';
import { ensureBrowser, openBrowser, renderMedia, selectComposition } from '@remotion/renderer';

const here = path.dirname(fileURLToPath(import.meta.url));
const emit = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');

// When a render fails, Remotion's cleanup can throw a harmless EBADF from killing a
// child process that has already gone. Left unhandled it crashes Node and hides the
// real error, so ignore that one case and let the render's own error come through.
process.on('uncaughtException', (err) => {
  if (err?.code === 'EBADF' && err?.syscall === 'kill') return;
  emit({ event: 'error', id: null, message: String(err?.stack ?? err) });
  process.exit(1);
});

const MODES = {
  // Draft: half scale and the fastest encoder preset, for quick checks.
  draft: { scale: 0.5, crf: 28, x264Preset: 'ultrafast' },
  final: { scale: 1, crf: 20, x264Preset: 'fast' },
};

const MIME = {
  '.mp4': 'video/mp4',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.m4a': 'audio/mp4',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
};

// Serves the storage folder, with Range support so video seeking works.
function serveStorage(root) {
  const base = path.resolve(root);
  const server = http.createServer((req, res) => {
    try {
      const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '');
      const file = path.resolve(base, rel);
      if (!file.startsWith(base + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404).end();
        return;
      }
      const size = fs.statSync(file).size;
      const headers = {
        'Content-Type': MIME[path.extname(file).toLowerCase()] ?? 'application/octet-stream',
        'Accept-Ranges': 'bytes',
        'Access-Control-Allow-Origin': '*',
      };
      const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? '');
      if (range) {
        const start = range[1] ? Number(range[1]) : size - Number(range[2]);
        const end = range[1] && range[2] ? Number(range[2]) : size - 1;
        res.writeHead(206, {
          ...headers,
          'Content-Range': `bytes ${start}-${end}/${size}`,
          'Content-Length': end - start + 1,
        });
        fs.createReadStream(file, { start, end }).pipe(res);
      } else {
        res.writeHead(200, { ...headers, 'Content-Length': size });
        fs.createReadStream(file).pipe(res);
      }
    } catch {
      res.writeHead(400).end();
    }
  });
  return new Promise((resolve) =>
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port })),
  );
}

// Reuse the bundle while the sources are unchanged.
async function getBundle() {
  const srcDir = path.join(here, 'src');
  const hash = createHash('sha1');
  for (const f of fs.readdirSync(srcDir).sort()) {
    hash.update(f).update(fs.readFileSync(path.join(srcDir, f)));
  }
  const outDir = path.join(here, '.bundle');
  const stamp = path.join(outDir, '.hash');
  const digest = hash.digest('hex');
  if (fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8') === digest) return outDir;
  const out = await bundle({ entryPoint: path.join(srcDir, 'index.ts'), outDir });
  fs.writeFileSync(stamp, digest);
  return out;
}

// Remotion probes audio with a bundled ffprobe.exe. On Windows machines with an
// Application Control policy (Smart App Control and similar) that unsigned binary can
// be blocked, which makes every render with audio hang. In that case build a local
// copy of Remotion's binaries folder with the system ffprobe in its place.
// Returns the folder to pass as `binariesDirectory`, or undefined when not needed.
function resolveBinariesDirectory() {
  if (process.env.REMOTION_BINARIES_DIR) return process.env.REMOTION_BINARIES_DIR;
  if (process.platform !== 'win32') return undefined;

  const pkgJson = createRequire(import.meta.url).resolve(
    `@remotion/compositor-win32-${process.arch}-msvc/package.json`,
  );
  const bundled = path.dirname(pkgJson);
  try {
    execFileSync(path.join(bundled, 'ffprobe.exe'), ['-version'], { stdio: 'ignore' });
    return undefined; // the bundled one runs fine
  } catch {
    // fall through to the workaround
  }

  const target = path.join(here, '.binaries');
  const marker = path.join(target, 'ffprobe.exe');
  if (!fs.existsSync(marker)) {
    const systemProbe =
      process.env.FFPROBE_BIN && fs.existsSync(process.env.FFPROBE_BIN)
        ? process.env.FFPROBE_BIN
        : execFileSync('where', ['ffprobe'], { encoding: 'utf8' }).split(/\r?\n/)[0].trim();
    if (!systemProbe) throw new Error('Remotion\'s ffprobe is blocked and no system ffprobe was found');
    fs.cpSync(bundled, target, { recursive: true });
    fs.copyFileSync(systemProbe, marker);
  }
  return target;
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const mode = MODES[manifest.mode];
  if (!mode) throw new Error(`unknown mode: ${manifest.mode}`);

  const binariesDirectory = resolveBinariesDirectory();
  await ensureBrowser();
  const { server, port } = await serveStorage(manifest.storageRoot);
  const baseUrl = `http://127.0.0.1:${port}`;
  const serveUrl = await getBundle();
  const logLevel = process.env.REMOTION_LOG ?? 'warn';
  const browser = await openBrowser('chrome', { logLevel });

  let failed = false;
  try {
    for (const job of manifest.jobs) {
      const started = Date.now();
      emit({ event: 'start', id: job.id });
      try {
        const inputProps = { ...job.props, baseUrl };
        const composition = await selectComposition({
          serveUrl,
          id: 'Scene',
          inputProps,
          puppeteerInstance: browser,
          binariesDirectory,
        });
        const out = path.join(manifest.storageRoot, ...job.outKey.split('/'));
        fs.mkdirSync(path.dirname(out), { recursive: true });
        // Render to a temp name so a crash never leaves a half-written segment in the cache.
        const tmp = `${out}.part.mp4`;
        await renderMedia({
          composition,
          serveUrl,
          inputProps,
          codec: 'h264',
          audioCodec: 'aac',
          pixelFormat: 'yuv420p',
          outputLocation: tmp,
          puppeteerInstance: browser,
          logLevel,
          binariesDirectory,
          concurrency: process.env.REMOTION_CONCURRENCY
            ? Number(process.env.REMOTION_CONCURRENCY)
            : null,
          scale: mode.scale,
          crf: mode.crf,
          x264Preset: mode.x264Preset,
          onProgress: ({ progress }) => emit({ event: 'progress', id: job.id, progress }),
        });
        fs.renameSync(tmp, out);
        emit({ event: 'done', id: job.id, seconds: (Date.now() - started) / 1000 });
      } catch (err) {
        failed = true;
        emit({ event: 'error', id: job.id, message: String(err?.message ?? err) });
        break;
      }
    }
  } finally {
    await browser.close({ silent: true }).catch(() => {});
    server.close();
  }
  emit({ event: 'all_done', ok: !failed });
  process.exit(failed ? 1 : 0);
}

main().catch((err) => {
  emit({ event: 'error', id: null, message: String(err?.stack ?? err) });
  process.exit(1);
});
