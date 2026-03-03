/**
 * TypeScript types matching the FastAPI backend schemas.
 */

export type ProviderStatus = 'ok' | 'error' | 'unconfigured' | 'stale' | 'disabled';

export interface BalanceSnapshot {
  provider_id: string;
  provider_name: string;
  balance_usd: number | null;
  total_credits: number | null;
  used_credits: number | null;
  remaining_credits: number | null;
  currency: string;
  status: ProviderStatus;
  error_message: string | null;
  fetched_at: string | null;
  raw_data: Record<string, unknown> | null;
}

export interface DashboardResponse {
  providers: BalanceSnapshot[];
  last_updated: string;
  total_usd_balance: number | null;
}

export interface ProviderMeta {
  id: string;
  name: string;
  auth_type: string;
  auth_fields: string[];
  auth_help: string;
  tier: number;
  note: string | null;
  enabled: boolean;
  is_configured: boolean;
  refresh_interval: number;
  last_refresh: string | null;
}

export interface ProviderSettings {
  id: string;
  name: string;
  enabled: boolean;
  auth_type: string;
  auth_fields: string[];
  auth_help: string;
  credentials: Record<string, string | null>;
  refresh_interval: number;
  tier: number;
  note: string | null;
}

export interface RefreshResponse {
  message: string;
  providers_refreshed: string[];
}

export interface HealthResponse {
  status: string;
  version: string;
  db_connected: boolean;
}
