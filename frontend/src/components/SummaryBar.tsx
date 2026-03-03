/**
 * SummaryBar - top bar showing total balance, refresh button, and settings link.
 */

import { RefreshCw, Zap, Clock, Settings } from 'lucide-react';
import { clsx } from 'clsx';
import type { DashboardResponse } from '../types';
import { formatUSD, formatRelativeTime } from '../utils/format';

interface SummaryBarProps {
  data: DashboardResponse | null;
  loading: boolean;
  refreshing: boolean;
  lastFetch: Date | null;
  onRefresh: () => void;
  onSettingsClick: () => void;
}

export function SummaryBar({
  data,
  loading,
  refreshing,
  lastFetch,
  onRefresh,
  onSettingsClick,
}: SummaryBarProps) {
  const providers  = data?.providers ?? [];
  const configured = providers.filter((p) => p.status === 'ok' || p.status === 'error').length;
  const active     = providers.filter((p) => p.status === 'ok').length;
  const errors     = providers.filter((p) => p.status === 'error').length;

  return (
    <div className="flex items-center justify-between gap-4 px-6 py-4 bg-gray-900/80 border-b border-gray-800/60 backdrop-blur-sm sticky top-0 z-10">
      {/* Left: branding + total */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <span className="font-semibold text-gray-100 text-sm tracking-tight">
            AI Credits
          </span>
        </div>

        {/* Total balance */}
        <div className="hidden sm:block">
          {loading ? (
            <div className="h-7 w-24 bg-gray-800 rounded-lg animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-gray-100 tabular-nums">
                {data?.total_usd_balance !== null && data?.total_usd_balance !== undefined
                  ? formatUSD(data.total_usd_balance)
                  : '—'}
              </span>
              <span className="text-xs text-gray-500">total remaining</span>
            </div>
          )}
        </div>
      </div>

      {/* Center: provider stats */}
      <div className="hidden md:flex items-center gap-4 text-xs">
        <Stat label="Active" value={active} color="text-emerald-400" />
        {errors > 0 && <Stat label="Errors" value={errors} color="text-red-400" />}
        <Stat label="Configured" value={configured} color="text-gray-400" />
      </div>

      {/* Right: last updated + refresh + settings */}
      <div className="flex items-center gap-3">
        {lastFetch && (
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-600">
            <Clock size={11} />
            <span>{formatRelativeTime(lastFetch.toISOString())}</span>
          </div>
        )}

        <div className="flex items-center gap-1.5">
          {/* Connection indicator */}
          <div className={clsx(
            'w-1.5 h-1.5 rounded-full',
            loading || refreshing ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400',
          )} />

          <button
            onClick={onRefresh}
            disabled={refreshing || loading}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium',
              'bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-gray-100',
              'border border-gray-700/60 hover:border-gray-600',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-all duration-150',
            )}
          >
            <RefreshCw size={12} className={clsx(refreshing && 'animate-spin')} />
            {refreshing ? 'Refreshing...' : 'Refresh All'}
          </button>

          <button
            onClick={onSettingsClick}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium',
              'bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-gray-100',
              'border border-gray-700/60 hover:border-gray-600',
              'transition-all duration-150',
            )}
            title="Provider Settings"
          >
            <Settings size={12} />
            <span className="hidden sm:inline">Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className={clsx('font-semibold tabular-nums', color)}>{value}</span>
      <span className="text-gray-600">{label}</span>
    </div>
  );
}
