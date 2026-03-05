/**
 * LoginPage — single-password authentication screen.
 *
 * Shown when auth is enabled and the user is not yet authenticated.
 * Matches the dark theme of the main dashboard.
 */

import { useState, type FormEvent } from 'react';
import { Lock, AlertCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

interface LoginPageProps {
  onLogin: (password: string) => Promise<boolean>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim() || loading) return;

    setError(false);
    setLoading(true);

    const ok = await onLogin(password.trim());
    if (!ok) {
      setError(true);
      setLoading(false);
    }
    // On success the parent component will unmount this page.
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo + title */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gray-800/60 border border-gray-700/40 flex items-center justify-center">
            <img
              src="/logo.png"
              alt="Reckoner"
              className="w-9 h-9 rounded-lg object-cover"
              onError={(e) => {
                // Fallback to lock icon if logo not found.
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold text-gray-100">Reckoner</h1>
            <p className="text-sm text-gray-500 mt-0.5">Enter password to continue</p>
          </div>
        </div>

        {/* Login form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <Lock
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (error) setError(false);
              }}
              placeholder="Password"
              autoFocus
              className={clsx(
                'w-full pl-9 pr-4 py-2.5 rounded-xl text-sm',
                'bg-gray-900 border text-gray-100 placeholder-gray-600',
                'focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/60',
                'transition-all duration-150',
                error
                  ? 'border-red-500/60 focus:ring-red-500/40 focus:border-red-500/60'
                  : 'border-gray-700/60',
              )}
            />
          </div>

          {/* Error message */}
          {error && (
            <div className="flex items-center gap-2 text-xs text-red-400">
              <AlertCircle size={12} />
              <span>Incorrect password</span>
            </div>
          )}

          <button
            type="submit"
            disabled={!password.trim() || loading}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium',
              'bg-blue-600 hover:bg-blue-500 text-white',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors duration-150',
            )}
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
