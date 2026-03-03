/**
 * Lightweight static file server for the built React app.
 * Serves /dist as the web root, with SPA fallback to index.html.
 */
import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const DIST = join(__dirname, 'dist');

// Serve static assets with long cache headers
app.use(express.static(DIST, {
  maxAge: '1y',
  etag: true,
  index: false,
}));

// SPA fallback — all non-asset routes serve index.html
// Note: Express 5 + path-to-regexp v8 requires named wildcard '/*splat', not bare '*'
app.get('/*splat', (_req, res) => {
  res.sendFile(join(DIST, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${PORT}`);
});
