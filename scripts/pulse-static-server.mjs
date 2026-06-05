import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { createServer } from 'node:http';

const root = resolve(process.env.OMNI_FRONTEND_DIST || 'dist');
const port = Number(process.env.OMNI_FRONTEND_PORT || 8088);
const apiTarget = new URL(process.env.OMNI_API_PROXY_TARGET || 'http://127.0.0.1:8090');

const contentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.txt', 'text/plain; charset=utf-8'],
  ['.webmanifest', 'application/manifest+json'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function sendFile(res, filePath) {
  const stream = createReadStream(filePath);
  const cacheControl = filePath.includes(`${sep}assets${sep}`)
    ? 'public, max-age=31536000, immutable'
    : 'no-cache';
  res.writeHead(200, {
    'Content-Type': contentTypes.get(extname(filePath)) || 'application/octet-stream',
    'Cache-Control': cacheControl,
  });
  stream.pipe(res);
}

function staticPath(pathname) {
  const safePath = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, '');
  const candidate = resolve(join(root, safePath));
  if (!candidate.startsWith(root)) return null;
  if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  return resolve(join(root, 'index.html'));
}

async function proxyApi(req, res, pathname) {
  const target = new URL(pathname + (new URL(req.url, 'http://local').search || ''), apiTarget);
  const response = await fetch(target, {
    method: req.method,
    headers: req.headers,
    body: ['GET', 'HEAD'].includes(req.method || 'GET') ? undefined : req,
    duplex: 'half',
  });
  res.writeHead(response.status, Object.fromEntries(response.headers.entries()));
  if (response.body) {
    for await (const chunk of response.body) res.write(chunk);
  }
  res.end();
}

createServer(async (req, res) => {
  try {
    const { pathname } = new URL(req.url || '/', 'http://local');
    if (pathname.startsWith('/api/')) {
      await proxyApi(req, res, pathname);
      return;
    }
    const filePath = staticPath(pathname);
    if (!filePath || !existsSync(filePath)) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not found');
      return;
    }
    sendFile(res, filePath);
  } catch (error) {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
  }
}).listen(port, '0.0.0.0', () => {
  console.log(`Omni Ticket frontend listening on http://0.0.0.0:${port}`);
});
