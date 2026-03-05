/**
 * App — main application with dashboard and settings page.
 *
 * Dashboard shows two sections:
 *   - AI Providers (OpenRouter, OpenAI, Anthropic, xAI, Mistral, Groq, Manus, Warp, Plaud, Gemini)
 *   - Cloud Providers (Railway, Vercel, mem0, Neon, RunPod, AWS, GCP)
 *
 * Only configured providers are shown on the dashboard.
 * Unconfigured providers are only visible in the Settings page.
 */

import { useState } from 'react';
import { Settings } from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useDashboard } from './hooks/useDashboard';
import { useSettings } from './hooks/useSettings';
import { SummaryBar } from './components/SummaryBar';
import { ProviderCard } from './components/ProviderCard';
import { LoginPage } from './pages/LoginPage';
import { SettingsPage } from './pages/SettingsPage';
import type { BalanceSnapshot } from './types';

export default function App() {
  const auth = useAuth();
  const { data, loading, refreshing, error, refresh, lastFetch } = useDashboard();
  const { settings, reload: reloadSettings } = useSettings();
  const [showSettings, setShowSettings] = useState(false);
  const [showLogin, setShowLogin] = useState(false);

  // Only show providers that are configured (have real data or are in ok/error state)
  const visibleProviders = (data?.providers ?? []).filter(
    (p) => p.status !== 'unconfigured' && p.status !== 'disabled'
  );

  const aiProviders    = visibleProviders.filter((p) => p.category === 'ai');
  const cloudProviders = visibleProviders.filter((p) => p.category === 'cloud');

  const handleProviderRefreshed = (_updated: BalanceSnapshot) => {
    // The 60s auto-refresh will pick up changes; manual refresh button handles immediate feedback
  };

  const handleSettingsSaved = async () => {
    await reloadSettings();
    // Trigger a dashboard refresh so newly configured providers appear
    await refresh();
  };

  const handleLogin = async (password: string): Promise<boolean> => {
    const ok = await auth.login(password);
    if (ok) setShowLogin(false);
    return ok;
  };

  // ── Auth loading ───────────────────────────────────────────────────────────
  if (auth.loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-gray-700 border-t-gray-400 rounded-full animate-spin" />
      </div>
    );
  }

  // ── Login gate ─────────────────────────────────────────────────────────────
  // Show login page when:
  //   1. Auth enabled + dashboard protected + not authenticated, OR
  //   2. User explicitly clicked "Sign In" from the SummaryBar
  if (
    (auth.authEnabled && auth.dashboardProtected && !auth.authenticated) ||
    (auth.authEnabled && showLogin && !auth.authenticated)
  ) {
    return <LoginPage onLogin={handleLogin} />;
  }

  // ── Settings page ──────────────────────────────────────────────────────────
  if (showSettings) {
    // Settings always require auth when enabled — prompt login if not authenticated.
    if (auth.authEnabled && !auth.authenticated) {
      return <LoginPage onLogin={handleLogin} />;
    }
    return (
      <SettingsPage
        settings={settings}
        onClose={() => setShowSettings(false)}
        onSaved={handleSettingsSaved}
      />
    );
  }

  // ── Dashboard ──────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Top navigation bar */}
      <SummaryBar
        data={data}
        loading={loading}
        refreshing={refreshing}
        lastFetch={lastFetch}
        onRefresh={refresh}
        onSettingsClick={() => setShowSettings(true)}
        authEnabled={auth.authEnabled}
        authenticated={auth.authenticated}
        onLoginClick={() => setShowLogin(true)}
        onLogout={auth.logout}
      />

      {/* Main content */}
      <main className="flex-1 px-4 sm:px-6 py-6 w-full">
        {/* Error banner */}
        {error && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-800/40 rounded-xl text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !data && (
          <div className="space-y-8">
            {[8, 7].map((count, si) => (
              <div key={si}>
                <div className="h-4 w-28 bg-gray-800/60 rounded mb-4 animate-pulse" />
                <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                  {Array.from({ length: count }).map((_, i) => (
                    <div key={i} className="h-44 rounded-2xl bg-gray-900/60 border border-gray-800/60 animate-pulse" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Provider sections */}
        {data && (
          <div className="space-y-10">

            {/* ── AI Providers ── */}
            {aiProviders.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
                    AI Providers
                  </h2>
                  <span className="text-xs text-gray-600">
                    {aiProviders.filter((p) => p.status === 'ok').length} of {aiProviders.length} active
                  </span>
                </div>
                <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                  {aiProviders.map((snapshot) => (
                    <ProviderCard
                      key={snapshot.provider_id}
                      snapshot={snapshot}
                      onRefreshed={handleProviderRefreshed}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* ── Cloud Providers ── */}
            {cloudProviders.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
                    Cloud Providers
                  </h2>
                  <span className="text-xs text-gray-600">
                    {cloudProviders.filter((p) => p.status === 'ok').length} of {cloudProviders.length} active
                  </span>
                </div>
                <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                  {cloudProviders.map((snapshot) => (
                    <ProviderCard
                      key={snapshot.provider_id}
                      snapshot={snapshot}
                      onRefreshed={handleProviderRefreshed}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Empty state — nothing configured yet */}
            {aiProviders.length === 0 && cloudProviders.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-gray-800/60 flex items-center justify-center">
                  <Settings size={28} className="text-gray-600" />
                </div>
                <div>
                  <p className="text-gray-400 font-medium mb-1">No providers configured</p>
                  <p className="text-sm text-gray-600">
                    Open Settings to add your API keys and credentials.
                  </p>
                </div>
                <button
                  onClick={() => setShowSettings(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-xl font-medium transition-colors"
                >
                  Open Settings
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
