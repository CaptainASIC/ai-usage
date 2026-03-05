/**
 * Formatting utilities for the dashboard.
 */

/**
 * Format a raw credit integer for display (e.g. "142,363 cr").
 */
export function formatCredits(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(Math.round(value)) + ' cr';
}

/**
 * Format a Buzz value for display (e.g. "58,611 buzz").
 */
export function formatBuzz(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(Math.round(value)) + ' buzz';
}

/**
 * Format a USD dollar amount for display.
 */
export function formatUSD(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

/**
 * Format a relative time string (e.g., "2 minutes ago").
 */
export function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 10) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

/**
 * Format a percentage of credits used.
 */
export function formatPercent(used: number | null, total: number | null): string {
  if (used === null || total === null || total === 0) return '—';
  return `${Math.round((used / total) * 100)}%`;
}

/**
 * Get a color class based on remaining balance percentage.
 */
export function getBalanceColor(remaining: number | null, total: number | null): string {
  if (remaining === null || total === null || total === 0) return 'text-gray-400';
  const pct = (remaining / total) * 100;
  if (pct > 50) return 'text-emerald-400';
  if (pct > 20) return 'text-amber-400';
  return 'text-red-400';
}

/**
 * Humanize a credential field name.
 */
export function humanizeField(field: string): string {
  return field
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
