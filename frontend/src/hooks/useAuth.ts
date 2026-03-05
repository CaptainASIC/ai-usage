/**
 * useAuth — manages authentication state for the Reckoner dashboard.
 *
 * Checks /api/auth/status on mount to determine whether auth is enabled,
 * whether the dashboard is protected, and whether the current token is valid.
 */

import { useState, useEffect, useCallback } from 'react';
import { api, setToken, clearToken, setOnUnauthorized } from '../utils/api';
import type { AuthStatus } from '../types';

interface UseAuthReturn {
  /** True while the initial auth status check is in-flight. */
  loading: boolean;
  /** Whether the backend has auth enabled (RECKONER_PASSWORD is set). */
  authEnabled: boolean;
  /** Whether the dashboard itself requires login (RECKONER_PROTECT_DASHBOARD). */
  dashboardProtected: boolean;
  /** Whether the user is currently authenticated with a valid token. */
  authenticated: boolean;
  /** Attempt login; returns true on success, false on wrong password. */
  login: (password: string) => Promise<boolean>;
  /** Clear token and return to unauthenticated state. */
  logout: () => void;
}

export function useAuth(): UseAuthReturn {
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [dashboardProtected, setDashboardProtected] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  // Check auth status on mount.
  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const status: AuthStatus = await api.authStatus();
        if (cancelled) return;
        setAuthEnabled(status.auth_enabled);
        setDashboardProtected(status.dashboard_protected);
        setAuthenticated(status.authenticated);
      } catch {
        // If the status endpoint fails, assume auth is disabled (safe fallback).
        if (cancelled) return;
        setAuthEnabled(false);
        setAuthenticated(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    check();
    return () => { cancelled = true; };
  }, []);

  // Register the global 401 handler so any API call that gets a 401
  // will reset the authenticated state and force re-login.
  useEffect(() => {
    setOnUnauthorized(() => setAuthenticated(false));
    return () => setOnUnauthorized(null);
  }, []);

  const login = useCallback(async (password: string): Promise<boolean> => {
    try {
      const { token } = await api.login(password);
      setToken(token);
      setAuthenticated(true);
      return true;
    } catch {
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setAuthenticated(false);
  }, []);

  return {
    loading,
    authEnabled,
    dashboardProtected,
    authenticated,
    login,
    logout,
  };
}
