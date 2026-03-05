/**
 * ProviderCard - displays balance/usage for a single provider.
 *
 * Display priority:
 *   1. remaining_credits / balance_usd  → show as primary + % bar if total known
 *   2. thirty_day_spend_usd             → spend-only APIs (OpenAI admin)
 *   3. usage_monthly                    → unlimited keys (OpenRouter BYOK)
 *   4. used_credits                     → fallback usage
 *   5. error                            → error state
 */

import { useState } from 'react';
import {
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  TrendingUp,
  Minus,
  Activity,
  BarChart2,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { BalanceSnapshot } from '../types';
import { formatUSD, formatCredits, formatRelativeTime } from '../utils/format';
import { api } from '../utils/api';

interface ProviderCardProps {
  snapshot: BalanceSnapshot;
  onRefreshed: (updated: BalanceSnapshot) => void;
}

/** Gradient fallback colours per provider */
const PROVIDER_COLORS: Record<string, string> = {
  openrouter: 'from-violet-500 to-purple-600',
  openai:     'from-emerald-500 to-teal-600',
  anthropic:  'from-orange-500 to-amber-600',
  xai:        'from-blue-500 to-indigo-600',
  mistral:    'from-rose-500 to-pink-600',
  groq:       'from-cyan-500 to-sky-600',
  manus:      'from-lime-500 to-green-600',
  warp:       'from-fuchsia-500 to-violet-600',
  plaud:      'from-sky-500 to-blue-600',
  gemini:     'from-blue-400 to-violet-500',
  railway:    'from-purple-500 to-violet-600',
  vercel:     'from-gray-400 to-gray-600',
  mem0:       'from-teal-500 to-cyan-600',
  neon:       'from-green-400 to-emerald-600',
  runpod:     'from-yellow-500 to-orange-600',
  firecrawl:  'from-orange-500 to-red-500',
  aws:        'from-orange-400 to-yellow-500',
  gcp:        'from-blue-400 to-red-400',
};

/** Map provider IDs to logo file paths in /public/logos/ */
const PROVIDER_LOGOS: Record<string, string> = {
  openrouter: '/logos/openrouter.png',
  openai:     '/logos/openai.png',
  anthropic:  '/logos/anthropic.png',
  xai:        '/logos/xai.png',
  mistral:    '/logos/mistral.png',
  groq:       '/logos/groq.png',
  manus:      '/logos/manus.png',
  warp:       '/logos/warp.png',
  plaud:      '/logos/plaud.png',
  gemini:     '/logos/gemini.png',
  railway:    '/logos/railway.png',
  vercel:     '/logos/vercel.png',
  mem0:       '/logos/mem0.png',
  neon:       '/logos/neon.png',
  runpod:     '/logos/runpod.png',
  firecrawl:  '/logos/firecrawl.png',
  aws:        '/logos/aws.png',
  gcp:        '/logos/gcp.png',
};

/** Colour the balance value based on how much is left */
function balanceColor(value: number, total: number | null): string {
  if (total === null) return 'text-blue-400';
  const pct = value / total;
  if (pct > 0.4) return 'text-emerald-400';
  if (pct > 0.15) return 'text-amber-400';
  return 'text-red-400';
}

/** Colour the progress bar fill */
function barColor(pct: number): string {
  if (pct > 0.4) return 'bg-emerald-500';
  if (pct > 0.15) return 'bg-amber-500';
  return 'bg-red-500';
}

/** Provider logo with graceful fallback to gradient initials */
function ProviderLogo({ providerId, providerName }: { providerId: string; providerName: string }) {
  const [imgError, setImgError] = useState(false);
  const logoSrc = PROVIDER_LOGOS[providerId];
  const gradient = PROVIDER_COLORS[providerId] ?? 'from-gray-500 to-gray-600';

  if (logoSrc && !imgError) {
    return (
      <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center shadow-lg overflow-hidden p-1.5">
        <img
          src={logoSrc}
          alt={`${providerName} logo`}
          className="w-full h-full object-contain"
          onError={() => setImgError(true)}
        />
      </div>
    );
  }

  // Fallback: gradient with initials
  return (
    <div className={clsx(
      'w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center',
      'text-white text-xs font-bold shadow-lg',
      gradient,
    )}>
      {providerName.slice(0, 2).toUpperCase()}
    </div>
  );
}

export function ProviderCard({ snapshot, onRefreshed }: ProviderCardProps) {
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

  const isOk    = snapshot.status === 'ok';
  const isError = snapshot.status === 'error';

  // ── derive display values ──────────────────────────────────────────────────
  const remaining = snapshot.remaining_credits ?? snapshot.balance_usd;
  const total     = snapshot.total_credits;
  const used      = snapshot.used_credits;
  const isCredits = snapshot.currency === 'credits';
  const fmt       = isCredits ? formatCredits : formatUSD;

  const raw = snapshot.raw_data ?? {};
  const thirtyDaySpend = typeof raw.thirty_day_spend_usd === 'number' ? raw.thirty_day_spend_usd : null;
  const usageMonthly   = typeof raw.usage_monthly        === 'number' ? raw.usage_monthly        : null;
  const noteText       = typeof raw.note                 === 'string' ? raw.note                 : null;

  // ── Plaud-specific fields ──────────────────────────────────────────────
  const isPlaud              = snapshot.provider_id === 'plaud';
  const plaudTotalFiles      = typeof raw.plaud_total_files      === 'number' ? raw.plaud_total_files      : null;
  const plaudTotalHours      = typeof raw.plaud_total_hours      === 'number' ? raw.plaud_total_hours      : null;
  const plaudTranscribed     = typeof raw.plaud_total_transcribed_hours === 'number' ? raw.plaud_total_transcribed_hours : null;
  const plaudActiveDays      = typeof raw.plaud_active_days      === 'number' ? raw.plaud_active_days      : null;
  const plaudDailyAvg        = typeof raw.plaud_daily_avg_hours  === 'number' ? raw.plaud_daily_avg_hours  : null;
  const plaudPlanName        = typeof raw.plaud_plan_name        === 'string' ? raw.plaud_plan_name        : null;
  const plaudPlanExpires     = typeof raw.plaud_plan_expires     === 'string' ? raw.plaud_plan_expires     : null;

  // ── Manus-specific three-bucket fields ───────────────────────────────────
  const isManus         = snapshot.provider_id === 'manus';
  const manusMonthlyUsed      = typeof raw.manus_monthly_used      === 'number' ? raw.manus_monthly_used      : null;
  const manusMonthlyRemaining = typeof raw.manus_monthly_remaining === 'number' ? raw.manus_monthly_remaining : null;
  const manusMonthlyTotal = typeof raw.manus_monthly_total === 'number' ? raw.manus_monthly_total : null;
  const manusDailyUsed      = typeof raw.manus_daily_used      === 'number' ? raw.manus_daily_used      : null;
  const manusDailyRemaining = typeof raw.manus_daily_remaining === 'number' ? raw.manus_daily_remaining : null;
  const manusDailyTotal     = typeof raw.manus_daily_total     === 'number' ? raw.manus_daily_total     : null;
  const manusAddonBalance = typeof raw.manus_addon_balance === 'number' ? raw.manus_addon_balance : null;
  const manusTotalBalance = typeof raw.manus_total_balance === 'number' ? raw.manus_total_balance : null;

  // Usage percentage for the progress bar (0–1)
  let usagePct: number | null = null;
  if (remaining !== null && total !== null && total > 0) {
    usagePct = Math.min(remaining / total, 1);
  } else if (used !== null && total !== null && total > 0) {
    usagePct = Math.max(0, Math.min(1 - used / total, 1));
  }

  // ── determine primary display mode ────────────────────────────────────────
  type Mode = 'balance' | 'spend' | 'usage_monthly' | 'used' | 'manus' | 'plaud' | 'none';
  let mode: Mode = 'none';
  if (isOk) {
    if (isPlaud && plaudTotalFiles !== null)
                                      mode = 'plaud';
    else if (isManus && (manusMonthlyTotal !== null || manusDailyTotal !== null || manusAddonBalance !== null))
                                      mode = 'manus';
    else if (remaining !== null)      mode = 'balance';
    else if (thirtyDaySpend !== null) mode = 'spend';
    else if (usageMonthly !== null)   mode = 'usage_monthly';
    else if (used !== null)           mode = 'used';
  }

  return (
    <div
      className={clsx(
        'relative rounded-2xl border p-5 flex flex-col gap-3 transition-all duration-200',
        'bg-gray-900/60 backdrop-blur-sm',
        isOk    && 'border-gray-700/60 hover:border-gray-600/80 hover:bg-gray-900/80',
        isError && 'border-red-900/60',
      )}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ProviderLogo providerId={snapshot.provider_id} providerName={snapshot.provider_name} />
          <div>
            <h3 className="font-semibold text-gray-100 text-sm leading-tight">
              {snapshot.provider_name}
            </h3>
            <StatusBadge status={snapshot.status} />
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className={clsx(
            'p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800',
            'disabled:opacity-40 disabled:cursor-not-allowed',
            refreshing && 'animate-spin text-blue-400',
          )}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 space-y-2">

        {mode === 'balance' && remaining !== null && (
          <>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Remaining</p>
              <p className={clsx('text-2xl font-bold tabular-nums', balanceColor(remaining, total))}>
                {fmt(remaining)}
              </p>
            </div>
            {total !== null && (
              <p className="text-xs text-gray-500">
                of {fmt(total)} total
                {used !== null ? ` · ${fmt(used)} used` : ''}
              </p>
            )}
            {total === null && used !== null && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <TrendingUp size={11} />
                <span>{fmt(used)} used</span>
              </div>
            )}
          </>
        )}

        {mode === 'spend' && thirtyDaySpend !== null && (
          <>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">30-Day Spend</p>
              <p className="text-2xl font-bold tabular-nums text-blue-400">
                {formatUSD(thirtyDaySpend)}
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <BarChart2 size={11} />
              <span>No balance endpoint — spend only</span>
            </div>
          </>
        )}

        {mode === 'usage_monthly' && usageMonthly !== null && (
          <>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Monthly Usage</p>
              <p className="text-2xl font-bold tabular-nums text-blue-400">
                {formatUSD(usageMonthly)}
              </p>
            </div>
            {used !== null && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Activity size={11} />
                <span>{formatUSD(used)} lifetime</span>
              </div>
            )}
          </>
        )}

        {mode === 'used' && used !== null && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Total Used</p>
            <p className="text-2xl font-bold tabular-nums text-blue-400">
              {formatUSD(used)}
            </p>
          </div>
        )}

        {mode === 'none' && isOk && (
          <div className="space-y-1">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Balance</p>
            <p className="text-2xl font-bold tabular-nums text-gray-500">—</p>
            <p className="text-xs text-gray-600">No data returned for this key type.</p>
          </div>
        )}

        {/* ── Plaud usage layout ── */}
        {mode === 'plaud' && (
          <div className="space-y-2.5">
            {/* Plan badge */}
            {plaudPlanName && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                  bg-sky-500/15 text-sky-300 border border-sky-500/30">
                  {plaudPlanName}
                </span>
                {plaudPlanExpires && (
                  <span className="text-xs text-gray-600">expires {plaudPlanExpires}</span>
                )}
              </div>
            )}

            {/* 3-column stats: Days / Recordings / Hours */}
            <div className="grid grid-cols-3 gap-2">
              <div className="text-center">
                <p className="text-lg font-bold tabular-nums text-gray-100">
                  {plaudActiveDays !== null ? plaudActiveDays : '—'}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Days</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold tabular-nums text-gray-100">
                  {plaudTotalFiles !== null ? plaudTotalFiles : '—'}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Recordings</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold tabular-nums text-gray-100">
                  {plaudTotalHours !== null ? plaudTotalHours : '—'}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Hours</p>
              </div>
            </div>

            {/* Transcribed + daily avg */}
            <div className="border-t border-gray-800/60 pt-1.5 space-y-1">
              {plaudTranscribed !== null && (
                <p className="text-xs text-gray-500">{plaudTranscribed} hrs transcribed</p>
              )}
              {plaudDailyAvg !== null && plaudDailyAvg > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <TrendingUp size={11} />
                  <span>{plaudDailyAvg} hrs/day avg (30d)</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Manus three-bucket layout ── */}
        {mode === 'manus' && (
          <div className="space-y-3">

            {/* Monthly quota */}
            {manusMonthlyTotal !== null && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span className="uppercase tracking-wide">Monthly</span>
                  <span className="tabular-nums font-medium">
                    {manusMonthlyRemaining !== null
                      ? `${manusMonthlyRemaining.toLocaleString()} / ${manusMonthlyTotal.toLocaleString()}`
                      : manusMonthlyUsed !== null
                        ? `${manusMonthlyUsed.toLocaleString()} / ${manusMonthlyTotal.toLocaleString()}`
                        : `0 / ${manusMonthlyTotal.toLocaleString()}`
                    }
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
                  {manusMonthlyTotal > 0 && (manusMonthlyRemaining !== null || manusMonthlyUsed !== null) && (
                    <div
                      className={clsx('h-full rounded-full transition-all duration-500',
                        barColor((manusMonthlyRemaining ?? 0) / manusMonthlyTotal))}
                      style={{ width: `${Math.min(100, Math.round(((manusMonthlyRemaining ?? 0) / manusMonthlyTotal) * 100))}%` }}
                    />
                  )}
                </div>
              </div>
            )}

            {/* Daily refresh */}
            {manusDailyTotal !== null && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span className="uppercase tracking-wide">Daily Refresh</span>
                  <span className="tabular-nums font-medium">
                    {manusDailyRemaining !== null
                      ? `${manusDailyRemaining.toLocaleString()} / ${manusDailyTotal.toLocaleString()}`
                      : manusDailyUsed !== null
                        ? `${Math.round(manusDailyUsed).toLocaleString()} / ${manusDailyTotal.toLocaleString()}`
                        : `0 / ${manusDailyTotal.toLocaleString()}`
                    }
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
                  {manusDailyTotal > 0 && (
                    <div
                      className={clsx('h-full rounded-full transition-all duration-500',
                        barColor((manusDailyRemaining ?? 0) / manusDailyTotal))}
                      style={{ width: `${Math.min(100, Math.round(((manusDailyRemaining ?? 0) / manusDailyTotal) * 100))}%` }}
                    />
                  )}
                </div>
              </div>
            )}

            {/* Add-on balance */}
            {manusAddonBalance !== null && (
              <div className="flex justify-between text-xs text-gray-400 pt-0.5">
                <span className="uppercase tracking-wide">Add-on Credits</span>
                <span className="tabular-nums font-semibold text-blue-400">
                  {manusAddonBalance.toLocaleString()}
                </span>
              </div>
            )}

            {/* Total balance */}
            {manusTotalBalance !== null && (
              <div className="flex justify-between text-xs text-gray-500 border-t border-gray-800/60 pt-2">
                <span>Total balance</span>
                <span className={clsx('tabular-nums font-semibold',
                  manusMonthlyTotal && balanceColor(manusTotalBalance, manusMonthlyTotal + (manusAddonBalance ?? 0)))
                }>
                  {manusTotalBalance.toLocaleString()} cr
                </span>
              </div>
            )}
          </div>
        )}

        {/* Usage progress bar */}
        {isOk && mode !== 'manus' && usagePct !== null && (
          <div className="space-y-1 pt-1">
            <div className="flex justify-between text-xs text-gray-600">
              <span>{Math.round(usagePct * 100)}% remaining</span>
              {total !== null && <span>{fmt(total)} limit</span>}
            </div>
            <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all duration-500', barColor(usagePct))}
                style={{ width: `${Math.round(usagePct * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Note */}
        {noteText && (
          <p className="text-xs text-gray-600 italic">{noteText}</p>
        )}

        {/* Error state */}
        {isError && (
          <div className="flex items-start gap-2 text-red-500/80">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <p className="text-xs leading-relaxed">{snapshot.error_message}</p>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      {snapshot.fetched_at && (
        <div className="flex items-center gap-1.5 text-xs text-gray-600 border-t border-gray-800/60 pt-2">
          <Clock size={10} />
          <span>{formatRelativeTime(snapshot.fetched_at)}</span>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    ok:    { label: 'Live',  color: 'text-emerald-400 bg-emerald-400/10', icon: CheckCircle2 },
    error: { label: 'Error', color: 'text-red-400 bg-red-400/10',         icon: AlertCircle  },
    stale: { label: 'Stale', color: 'text-amber-400 bg-amber-400/10',     icon: Clock        },
  }[status] ?? { label: status, color: 'text-gray-500 bg-gray-500/10', icon: Minus };

  const Icon = config.icon;
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-md font-medium',
      config.color,
    )}>
      <Icon size={9} />
      {config.label}
    </span>
  );
}
