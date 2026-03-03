/**
 * ProviderCard - displays balance information for a single AI provider.
 *
 * Status matrix:
 *   ok + balance/remaining  → show balance in green/amber/red
 *   ok + null balance       → show usage/spend data (usage-only key or spend-only API)
 *   unconfigured            → prompt to configure
 *   error                   → show error message
 *   disabled                → dimmed disabled state
 */

import { useState } from 'react';
import {
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Settings,
  Clock,
  TrendingUp,
  Minus,
  Activity,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { BalanceSnapshot } from '../types';
import { formatUSD, formatRelativeTime } from '../utils/format';
import { api } from '../utils/api';

interface ProviderCardProps {
  snapshot: BalanceSnapshot;
  onRefreshed: (updated: BalanceSnapshot) => void;
  onSettingsClick: () => void;
}

const PROVIDER_COLORS: Record<string, string> = {
  openrouter: 'from-violet-500 to-purple-600',
  openai: 'from-emerald-500 to-teal-600',
  anthropic: 'from-orange-500 to-amber-600',
  xai: 'from-blue-500 to-indigo-600',
  mistral: 'from-rose-500 to-pink-600',
  groq: 'from-cyan-500 to-sky-600',
  manus: 'from-lime-500 to-green-600',
  warp: 'from-fuchsia-500 to-violet-600',
};

const PROVIDER_INITIALS: Record<string, string> = {
  openrouter: 'OR',
  openai: 'OAI',
  anthropic: 'ANT',
  xai: 'xAI',
  mistral: 'MST',
  groq: 'GRQ',
  manus: 'MNS',
  warp: 'WRP',
};

export function ProviderCard({ snapshot, onRefreshed, onSettingsClick }: ProviderCardProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const updated = await api.refreshProvider(snapshot.provider_id);
      onRefreshed(updated);
    } catch (err) {
      console.error('Refresh failed:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const isOk = snapshot.status === 'ok';
  const isUnconfigured = snapshot.status === 'unconfigured';
  const isError = snapshot.status === 'error';
  const isDisabled = snapshot.status === 'disabled';

  const gradient = PROVIDER_COLORS[snapshot.provider_id] || 'from-gray-500 to-gray-600';
  const initials = PROVIDER_INITIALS[snapshot.provider_id] || snapshot.provider_name.slice(0, 3).toUpperCase();

  // Primary balance value — prefer remaining_credits, then balance_usd
  const primaryValue = snapshot.remaining_credits ?? snapshot.balance_usd;
  const usedValue = snapshot.used_credits;

  // For ok-but-no-balance providers: extract spend/usage from raw_data
  const thirtyDaySpend = snapshot.raw_data?.thirty_day_spend_usd as number | undefined;
  const usageMonthly = snapshot.raw_data?.usage_monthly as number | undefined;
  const usageTotal = snapshot.raw_data?.usage as number | undefined;
  const hasUsageData = usedValue !== null || thirtyDaySpend !== undefined || usageMonthly !== undefined || usageTotal !== undefined;

  return (
    <div
      className={clsx(
        'relative rounded-2xl border p-5 flex flex-col gap-4 transition-all duration-200',
        'bg-gray-900/60 backdrop-blur-sm',
        isOk && 'border-gray-700/60 hover:border-gray-600/80 hover:bg-gray-900/80',
        isUnconfigured && 'border-gray-800/60 opacity-75',
        isError && 'border-red-900/60',
        isDisabled && 'border-gray-800/40 opacity-50',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={clsx(
              'w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center',
              'text-white text-xs font-bold shadow-lg',
              gradient,
            )}
          >
            {initials}
          </div>
          <div>
            <h3 className="font-semibold text-gray-100 text-sm leading-tight">
              {snapshot.provider_name}
            </h3>
            <StatusBadge status={snapshot.status} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleRefresh}
            disabled={refreshing || isDisabled}
            className={clsx(
              'p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800',
              'disabled:opacity-40 disabled:cursor-not-allowed',
              refreshing && 'animate-spin text-blue-400',
            )}
            title="Refresh"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={onSettingsClick}
            className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800"
            title="Configure"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>

      {/* Balance / data display */}
      <div className="flex-1">
        {isOk && primaryValue !== null && primaryValue !== undefined ? (
          /* Has a real balance/remaining value */
          <div className="space-y-2">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                {snapshot.remaining_credits !== null ? 'Remaining' : 'Balance'}
              </p>
              <p className={clsx(
                'text-2xl font-bold tabular-nums',
                primaryValue > 10 ? 'text-emerald-400' :
                primaryValue > 2 ? 'text-amber-400' : 'text-red-400',
              )}>
                {formatUSD(primaryValue)}
              </p>
            </div>
            {usedValue !== null && usedValue !== undefined && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <TrendingUp size={11} />
                <span>{formatUSD(usedValue)} used</span>
              </div>
            )}
            {snapshot.raw_data?.note !== undefined && (
              <p className="text-xs text-gray-600 italic">
                {String(snapshot.raw_data.note)}
              </p>
            )}
          </div>
        ) : isOk && hasUsageData ? (
          /* Ok but no balance — show usage/spend data */
          <div className="space-y-2">
            {thirtyDaySpend !== undefined && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">30-day Spend</p>
                <p className="text-2xl font-bold tabular-nums text-blue-400">
                  {formatUSD(thirtyDaySpend)}
                </p>
              </div>
            )}
            {usageMonthly !== undefined && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Monthly Usage</p>
                <p className="text-2xl font-bold tabular-nums text-blue-400">
                  {formatUSD(usageMonthly / 1000000)}
                </p>
              </div>
            )}
            {usedValue !== null && usedValue !== undefined && usedValue > 0 && thirtyDaySpend === undefined && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Used</p>
                <p className="text-2xl font-bold tabular-nums text-blue-400">
                  {formatUSD(usedValue)}
                </p>
              </div>
            )}
            {usageTotal !== undefined && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Activity size={11} />
                <span>{formatUSD(usageTotal / 1000000)} lifetime usage</span>
              </div>
            )}
            {snapshot.raw_data?.note !== undefined && (
              <p className="text-xs text-gray-600 italic">
                {String(snapshot.raw_data.note)}
              </p>
            )}
          </div>
        ) : isOk ? (
          /* Ok but truly no data at all */
          <div className="space-y-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Balance</p>
            <p className="text-2xl font-bold tabular-nums text-gray-500">—</p>
            <p className="text-xs text-gray-600">No balance data available for this key type.</p>
          </div>
        ) : isUnconfigured ? (
          <div className="flex items-start gap-2 text-gray-600">
            <Minus size={14} className="mt-0.5 shrink-0" />
            <p className="text-xs">Not configured. Click <Settings size={10} className="inline" /> to add credentials.</p>
          </div>
        ) : isError ? (
          <div className="flex items-start gap-2 text-red-500/80">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <p className="text-xs leading-relaxed">{snapshot.error_message}</p>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-gray-600">
            <Minus size={14} />
            <p className="text-xs">Disabled</p>
          </div>
        )}
      </div>

      {/* Footer: last updated */}
      {snapshot.fetched_at && (
        <div className="flex items-center gap-1.5 text-xs text-gray-600 border-t border-gray-800/60 pt-3">
          <Clock size={10} />
          <span>{formatRelativeTime(snapshot.fetched_at)}</span>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    ok: { label: 'Live', color: 'text-emerald-400 bg-emerald-400/10', icon: CheckCircle2 },
    error: { label: 'Error', color: 'text-red-400 bg-red-400/10', icon: AlertCircle },
    unconfigured: { label: 'Setup needed', color: 'text-gray-500 bg-gray-500/10', icon: Settings },
    stale: { label: 'Stale', color: 'text-amber-400 bg-amber-400/10', icon: Clock },
    disabled: { label: 'Disabled', color: 'text-gray-600 bg-gray-600/10', icon: Minus },
  }[status] ?? { label: status, color: 'text-gray-500 bg-gray-500/10', icon: Minus };

  const Icon = config.icon;

  return (
    <span className={clsx('inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-md font-medium', config.color)}>
      <Icon size={9} />
      {config.label}
    </span>
  );
}
