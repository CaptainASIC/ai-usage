/**
 * Static file server for the built React app.
 *
 * This file is compiled by esbuild into dist/index.js alongside the
 * Vite-built static assets (dist/public/). __dirname therefore resolves
 * to the dist/ directory, and the static files are at dist/public/.
 *
 * Build command:
 *   vite build && esbuild server/index.ts --platform=node --packages=external --bundle --format=esm --outdir=dist
 *
 * Start command:
 *   node dist/index.js
 */

import express from "express";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const server = createServer(app);

  // In production the server is bundled into dist/index.js, so __dirname = dist/
  // and the Vite output is at dist/public/.
  // In dev (ts-node / tsx), __dirname = server/ so we go up one level.
  const staticPath =
    process.env.NODE_ENV === "production"
      ? path.resolve(__dirname, "public")
      : path.resolve(__dirname, "..", "dist", "public");

  console.log(`NODE_ENV: ${process.env.NODE_ENV}`);
  console.log(`Serving static files from: ${staticPath}`);
  console.log(`Starting on port: ${process.env.PORT || 3000}`);

  app.use(express.static(staticPath));

  // SPA fallback — serve index.html for all unmatched routes.
  // Express 5 + path-to-regexp v8 removed the bare '*' wildcard from app.get();
  // use app.use() as the catch-all instead.
  app.use((_req, res) => {
    res.sendFile(path.join(staticPath, "index.html"));
  });

  const port = parseInt(process.env.PORT || "3000", 10);
  server.listen(port, "0.0.0.0", () => {
    console.log(`Frontend server running on http://0.0.0.0:${port}`);
  });
}

startServer().catch(console.error);
