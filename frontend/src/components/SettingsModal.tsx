/**
 * SettingsModal - configure credentials for a single provider.
 */

import { useState, useEffect } from 'react';
import { X, Eye, EyeOff, Save } from 'lucide-react';
import { clsx } from 'clsx';
import type { ProviderSettings } from '../types';
import { humanizeField } from '../utils/format';

interface SettingsModalProps {
  provider: ProviderSettings;
  onSave: (
    providerId: string,
    credentials: Record<string, string>,
    enabled: boolean,
    refreshInterval?: number
  ) => Promise<boolean>;
  onClose: () => void;
  saving: boolean;
}

export function SettingsModal({ provider, onSave, onClose, saving }: SettingsModalProps) {
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState(provider.enabled);
  const [refreshInterval, setRefreshInterval] = useState(provider.refresh_interval);
  const [showFields, setShowFields] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // Initialize with empty strings for each required field
    const initial: Record<string, string> = {};
    for (const field of provider.auth_fields) {
      initial[field] = '';
    }
    setCredentials(initial);
  }, [provider]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Filter out empty strings - don't overwrite existing with blank
    const nonEmpty: Record<string, string> = {};
    for (const [k, v] of Object.entries(credentials)) {
      if (v.trim()) nonEmpty[k] = v.trim();
    }
    const success = await onSave(provider.id, nonEmpty, enabled, refreshInterval);
    if (success) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  const toggleShow = (field: string) => {
    setShowFields((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const isSensitive = (field: string) =>
    field.includes('key') || field.includes('cookie') || field.includes('token') || field.includes('secret');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg bg-gray-900 border border-gray-700/60 rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-gray-100">
              Configure {provider.name}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Tier {provider.tier} — {provider.auth_type.replace(/_/g, ' ')}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Auth help text */}
          <div className="bg-blue-950/40 border border-blue-800/40 rounded-xl p-3">
            <p className="text-xs text-blue-300 leading-relaxed">{provider.auth_help}</p>
          </div>

          {/* Provider note */}
          {provider.note && (
            <div className="bg-amber-950/30 border border-amber-800/30 rounded-xl p-3">
              <p className="text-xs text-amber-300 leading-relaxed">{provider.note}</p>
            </div>
          )}

          {/* Credential fields */}
          <div className="space-y-3">
            {provider.auth_fields.map((field) => {
              const isSecret = isSensitive(field);
              const shown = showFields[field] ?? false;
              const currentMasked = provider.credentials[field];

              return (
                <div key={field}>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">
                    {humanizeField(field)}
                    {currentMasked && (
                      <span className="ml-2 text-gray-600 font-normal">
                        (current: {currentMasked})
                      </span>
                    )}
                  </label>
                  <div className="relative">
                    <input
                      type={isSecret && !shown ? 'password' : 'text'}
                      value={credentials[field] ?? ''}
                      onChange={(e) =>
                        setCredentials((prev) => ({ ...prev, [field]: e.target.value }))
                      }
                      placeholder={currentMasked ? 'Leave blank to keep existing' : `Enter ${humanizeField(field)}`}
                      className={clsx(
                        'w-full bg-gray-800/60 border border-gray-700/60 rounded-xl px-3 py-2.5',
                        'text-sm text-gray-100 placeholder-gray-600',
                        'focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/30',
                        isSecret && 'pr-10',
                      )}
                    />
                    {isSecret && (
                      <button
                        type="button"
                        onClick={() => toggleShow(field)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                      >
                        {shown ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Settings */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Refresh Interval (seconds)
              </label>
              <input
                type="number"
                min={60}
                max={86400}
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                className={clsx(
                  'w-full bg-gray-800/60 border border-gray-700/60 rounded-xl px-3 py-2.5',
                  'text-sm text-gray-100',
                  'focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/30',
                )}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Status
              </label>
              <button
                type="button"
                onClick={() => setEnabled((v) => !v)}
                className={clsx(
                  'w-full py-2.5 rounded-xl text-sm font-medium border transition-colors',
                  enabled
                    ? 'bg-emerald-900/40 border-emerald-700/60 text-emerald-400 hover:bg-emerald-900/60'
                    : 'bg-gray-800/60 border-gray-700/60 text-gray-500 hover:bg-gray-800',
                )}
              >
                {enabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-800">
            <button
              type="submit"
              disabled={saving}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium',
                'transition-colors',
                saved
                  ? 'bg-emerald-600 text-white'
                  : 'bg-blue-600 hover:bg-blue-500 text-white',
                saving && 'opacity-60 cursor-not-allowed',
              )}
            >
              <Save size={14} />
              {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
