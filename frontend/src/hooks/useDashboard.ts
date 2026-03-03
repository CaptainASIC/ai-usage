/**
 * Custom hook for fetching and auto-refreshing the dashboard data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../utils/api';
import type { DashboardResponse } from '../types';

const AUTO_REFRESH_INTERVAL = 60_000; // 60 seconds

interface UseDashboardResult {
  data: DashboardResponse | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  lastFetch: Date | null;
}

export function useDashboard(): UseDashboardResult {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDashboard = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setRefreshing(true);
    }
    setError(null);

    try {
      if (isManualRefresh) {
        // Trigger live refresh then fetch updated data
        await api.refreshAll();
      }
      const result = await api.getDashboard();
      setData(result);
      setLastFetch(new Date());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch dashboard';
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDashboard(false);
  }, [fetchDashboard]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      fetchDashboard(false);
    }, AUTO_REFRESH_INTERVAL);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchDashboard]);

  const refresh = useCallback(() => fetchDashboard(true), [fetchDashboard]);

  return { data, loading, refreshing, error, refresh, lastFetch };
}
