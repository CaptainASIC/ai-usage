/**
 * Footer — links to GitHub repo, Ko-fi, and GitHub Sponsors.
 */

import { Github, Heart, Coffee } from 'lucide-react';

const LINKS = {
  repo: 'https://github.com/CaptainASIC/Reckoner',
  github: 'https://github.com/CaptainASIC',
  kofi: 'https://ko-fi.com/captasic',
  sponsor: 'https://github.com/sponsors/CaptainASIC',
};

export function Footer() {
  return (
    <footer className="border-t border-gray-800/60 py-4 px-6 mt-auto">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-600">
        {/* Left: attribution + repo */}
        <div className="flex items-center gap-1.5">
          <span>
            &copy; {new Date().getFullYear()}{' '}
            <a
              href={LINKS.github}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              CaptainASIC
            </a>
          </span>
          <span className="text-gray-800">·</span>
          <a
            href={LINKS.repo}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <Github size={11} />
            Source
          </a>
        </div>

        {/* Right: support links */}
        <div className="flex items-center gap-2">
          <a
            href={LINKS.kofi}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 hover:text-amber-300 transition-all"
          >
            <Coffee size={11} />
            Ko-fi
          </a>
          <a
            href={LINKS.sponsor}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-pink-500/10 border border-pink-500/20 text-pink-400 hover:bg-pink-500/20 hover:text-pink-300 transition-all"
          >
            <Heart size={11} />
            Sponsor
          </a>
        </div>
      </div>
    </footer>
  );
}
