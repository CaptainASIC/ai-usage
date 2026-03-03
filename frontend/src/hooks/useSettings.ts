/**
 * Custom hook for managing provider settings.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../utils/api';
import type { ProviderSettings } from '../types';

interface UseSettingsResult {
  settings: ProviderSettings[];
  loading: boolean;
  saving: string | null;
  error: string | null;
  updateProvider: (
    providerId: string,
    credentials: Record<string, string>,
    enabled: boolean,
    refreshInterval?: number
  ) => Promise<boolean>;
  reload: () => Promise<void>;
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<ProviderSettings[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getSettings();
      setSettings(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const updateProvider = useCallback(
    async (
      providerId: string,
      credentials: Record<string, string>,
      enabled: boolean,
      refreshInterval?: number
    ): Promise<boolean> => {
      setSaving(providerId);
      setError(null);
      try {
        await api.updateProvider(providerId, credentials, enabled, refreshInterval);
        await loadSettings();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to save settings');
        return false;
      } finally {
        setSaving(null);
      }
    },
    [loadSettings]
  );

  return {
    settings,
    loading,
    saving,
    error,
    updateProvider,
    reload: loadSettings,
  };
}
