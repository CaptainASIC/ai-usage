/**
 * Lightweight static file server for the built React app.
 * Serves dist/ as the web root, with SPA fallback to index.html.
 *
 * Path resolution uses import.meta.url so it works regardless of
 * the working directory from which `node server.js` is invoked.
 */
import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';
import { existsSync } from 'fs';

// Resolve the directory that contains this server.js file
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Locate the dist/ folder — try relative to this file, then cwd
let DIST = join(__dirname, 'dist');
if (!existsSync(DIST)) {
  DIST = resolve(process.cwd(), 'dist');
}

console.log(`Serving static files from: ${DIST}`);
console.log(`Starting on port: ${PORT}`);

if (!existsSync(DIST)) {
  console.error(`ERROR: dist/ directory not found at ${DIST}`);
  console.error('Run `pnpm build` first.');
  process.exit(1);
}

// Serve static assets (JS, CSS, images) with long cache headers
app.use(express.static(DIST, {
  maxAge: '1y',
  etag: true,
  index: false,
}));

// SPA fallback — all routes that don't match a static asset serve index.html.
// We use app.use() instead of app.get() to avoid path-to-regexp wildcard issues
// with Express 5 + path-to-regexp v8.
app.use((_req, res) => {
  res.sendFile(join(DIST, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend server running on http://0.0.0.0:${PORT}`);
});
