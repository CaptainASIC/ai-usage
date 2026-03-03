/**
 * API client for the AI Credits Tracker backend.
 */

import type {
  DashboardResponse,
  ProviderMeta,
  ProviderSettings,
  RefreshResponse,
  BalanceSnapshot,
  HealthResponse,
} from '../types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error ${response.status}: ${error}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** Get the full dashboard with all provider balances */
  getDashboard: () => request<DashboardResponse>('/credits/'),

  /** Refresh all providers and return updated dashboard */
  refreshAll: () =>
    request<RefreshResponse>('/credits/refresh', { method: 'POST' }),

  /** Refresh a single provider */
  refreshProvider: (providerId: string) =>
    request<BalanceSnapshot>(`/credits/refresh/${providerId}`, { method: 'POST' }),

  /** List all providers with metadata */
  listProviders: () => request<ProviderMeta[]>('/credits/providers'),

  /** Get settings for all providers (credentials masked) */
  getSettings: () => request<ProviderSettings[]>('/settings/providers'),

  /** Update credentials for a provider */
  updateProvider: (
    providerId: string,
    credentials: Record<string, string>,
    enabled: boolean,
    refreshInterval?: number
  ) =>
    request<{ message: string }>(`/settings/providers/${providerId}`, {
      method: 'PUT',
      body: JSON.stringify({
        credentials,
        enabled,
        refresh_interval: refreshInterval,
      }),
    }),

  /** Clear credentials for a provider */
  clearProvider: (providerId: string) =>
    request<{ message: string }>(`/settings/providers/${providerId}/credentials`, {
      method: 'DELETE',
    }),

  /** Health check */
  health: () => request<HealthResponse>('/health'),
};
