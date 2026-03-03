/**
 * App - main dashboard application.
 * Single-page layout: summary bar + provider grid + settings modal.
 */

import { useState, useCallback } from 'react';
import { useDashboard } from './hooks/useDashboard';
import { useSettings } from './hooks/useSettings';
import { SummaryBar } from './components/SummaryBar';
import { ProviderCard } from './components/ProviderCard';
import { SettingsModal } from './components/SettingsModal';
import type { BalanceSnapshot } from './types';

export default function App() {
  const { data, loading, refreshing, error, refresh, lastFetch } = useDashboard();
  const { settings, saving, updateProvider } = useSettings();
  const [activeSettings, setActiveSettings] = useState<string | null>(null);

  // Update a single provider's snapshot in the local state
  const handleProviderRefreshed = useCallback(
    (_updated: BalanceSnapshot) => {
      // The dashboard hook will pick up the change on next poll
      // For immediate feedback, we could update local state here
      // but the 60s auto-refresh will handle it
    },
    []
  );

  const activeProvider = settings.find((s) => s.id === activeSettings);

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Top navigation bar */}
      <SummaryBar
        data={data}
        loading={loading}
        refreshing={refreshing}
        lastFetch={lastFetch}
        onRefresh={refresh}
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
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-44 rounded-2xl bg-gray-900/60 border border-gray-800/60 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Provider grid */}
        {data && (
          <>
            {/* Section header */}
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-widest">
                Providers
              </h2>
              <span className="text-xs text-gray-600">
                {data.providers.filter((p) => p.status === 'ok').length} of {data.providers.length} active
              </span>
            </div>

            <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
              {data.providers.map((snapshot) => (
                <ProviderCard
                  key={snapshot.provider_id}
                  snapshot={snapshot}
                  onRefreshed={handleProviderRefreshed}
                  onSettingsClick={() => setActiveSettings(snapshot.provider_id)}
                />
              ))}
            </div>

            {/* Empty state */}
            {data.providers.length === 0 && (
              <div className="text-center py-20 text-gray-600">
                <p className="text-sm">No providers configured.</p>
              </div>
            )}
          </>
        )}
      </main>

      {/* Settings modal */}
      {activeSettings && activeProvider && (
        <SettingsModal
          provider={activeProvider}
          onSave={updateProvider}
          onClose={() => setActiveSettings(null)}
          saving={saving === activeSettings}
        />
      )}
    </div>
  );
}
