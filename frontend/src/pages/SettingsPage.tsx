/**
 * SettingsPage — global configuration for all providers.
 *
 * Replaces the per-card settings modal. Shows all providers grouped by
 * category (AI Providers / Cloud Providers) with inline credential forms.
 * Unconfigured providers are shown with a dimmed "Add credentials" state.
 */

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Settings,
  Trash2,
  Eye,
  EyeOff,
  Save,
  X,
  ArrowLeft,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { ProviderSettings, AuthField } from '../types';
import { api } from '../utils/api';

interface SettingsPageProps {
  settings: ProviderSettings[];
  onClose: () => void;
  onSaved: () => void;
}

// ─── Provider logo + fallback ────────────────────────────────────────────────

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
  aws:        '/logos/aws.png',
  gcp:        '/logos/gcp.png',
};

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
  aws:        'from-orange-400 to-yellow-500',
  gcp:        'from-blue-400 to-red-400',
};

function ProviderLogo({ id, name }: { id: string; name: string }) {
  const [err, setErr] = useState(false);
  const src = PROVIDER_LOGOS[id];
  const gradient = PROVIDER_COLORS[id] ?? 'from-gray-500 to-gray-600';
  if (src && !err) {
    return (
      <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center overflow-hidden p-1">
        <img src={src} alt={name} className="w-full h-full object-contain" onError={() => setErr(true)} />
      </div>
    );
  }
  return (
    <div className={clsx('w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-white text-xs font-bold', gradient)}>
      {name.slice(0, 2).toUpperCase()}
    </div>
  );
}

// ─── Single provider row ─────────────────────────────────────────────────────

interface ProviderRowProps {
  provider: ProviderSettings;
  onSaved: () => void;
}

function ProviderRow({ provider, onSaved }: ProviderRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const isConfigured = Object.values(provider.credentials).some((v) => v !== null && v !== '');

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      // Only send fields that have values (don't overwrite with empty)
      const creds: Record<string, string> = {};
      for (const field of provider.auth_fields) {
        const val = values[field.key];
        if (val && val.trim()) creds[field.key] = val.trim();
      }
      await api.updateProvider(provider.id, creds, true);
      setSaveSuccess(true);
      setValues({});
      onSaved();
      setTimeout(() => {
        setSaveSuccess(false);
        setExpanded(false);
      }, 1200);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!confirm(`Clear all credentials for ${provider.name}?`)) return;
    setClearing(true);
    try {
      await api.clearProvider(provider.id);
      onSaved();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Clear failed');
    } finally {
      setClearing(false);
    }
  };

  const toggleSecret = (key: string) =>
    setShowSecret((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className={clsx(
      'rounded-xl border transition-all duration-200',
      isConfigured
        ? 'border-gray-700/60 bg-gray-900/40'
        : 'border-gray-800/40 bg-gray-900/20',
    )}>
      {/* Row header */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <ProviderLogo id={provider.id} name={provider.name} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-200">{provider.name}</span>
            {provider.note && (
              <span className="text-xs text-gray-600 truncate hidden sm:block">{provider.note}</span>
            )}
          </div>
          <span className="text-xs text-gray-500">{provider.auth_help}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isConfigured ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
              <CheckCircle2 size={10} />
              Configured
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-gray-500 bg-gray-700/30 px-2 py-0.5 rounded-full">
              <Settings size={10} />
              Not set
            </span>
          )}
          {expanded ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
        </div>
      </button>

      {/* Expanded form */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-800/60 pt-3 space-y-3">
          {/* Current masked values */}
          {isConfigured && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
              {provider.auth_fields.map((field) => {
                const current = provider.credentials[field.key];
                if (!current) return null;
                return (
                  <div key={field.key} className="text-xs text-gray-500 bg-gray-800/40 rounded-lg px-3 py-2">
                    <span className="text-gray-600">{field.label}: </span>
                    <span className="font-mono text-gray-400">{current}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Input fields */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {(provider.auth_fields as AuthField[]).map((field) => (
              <div key={field.key} className="space-y-1">
                <label className="text-xs font-medium text-gray-400">{field.label}</label>
                <div className="relative">
                  <input
                    type={field.secret && !showSecret[field.key] ? 'password' : 'text'}
                    placeholder={isConfigured ? '(leave blank to keep current)' : field.placeholder}
                    value={values[field.key] ?? ''}
                    onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                    className={clsx(
                      'w-full bg-gray-800/60 border border-gray-700/60 rounded-lg px-3 py-2',
                      'text-sm text-gray-200 placeholder-gray-600',
                      'focus:outline-none focus:border-blue-500/60 focus:bg-gray-800',
                      field.secret && 'pr-9',
                    )}
                  />
                  {field.secret && (
                    <button
                      type="button"
                      onClick={() => toggleSecret(field.key)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                    >
                      {showSecret[field.key] ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Error / success */}
          {saveError && (
            <div className="flex items-center gap-2 text-xs text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
              <AlertCircle size={12} />
              {saveError}
            </div>
          )}
          {saveSuccess && (
            <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-400/10 rounded-lg px-3 py-2">
              <CheckCircle2 size={12} />
              Saved successfully
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium',
                'bg-blue-600 hover:bg-blue-500 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              <Save size={12} />
              {saving ? 'Saving…' : 'Save'}
            </button>
            {isConfigured && (
              <button
                onClick={handleClear}
                disabled={clearing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-400/10 disabled:opacity-50"
              >
                <Trash2 size={12} />
                {clearing ? 'Clearing…' : 'Clear'}
              </button>
            )}
            <button
              onClick={() => setExpanded(false)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-300 hover:bg-gray-800 ml-auto"
            >
              <X size={12} />
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Section ─────────────────────────────────────────────────────────────────

function ProviderSection({
  title,
  providers,
  onSaved,
}: {
  title: string;
  providers: ProviderSettings[];
  onSaved: () => void;
}) {
  const configured = providers.filter((p) =>
    Object.values(p.credentials).some((v) => v !== null && v !== '')
  ).length;

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">{title}</h2>
        <span className="text-xs text-gray-600">{configured} / {providers.length} configured</span>
      </div>
      {providers.map((p) => (
        <ProviderRow key={p.id} provider={p} onSaved={onSaved} />
      ))}
    </section>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export function SettingsPage({ settings, onClose, onSaved }: SettingsPageProps) {
  const aiProviders    = settings.filter((p) => p.category === 'ai');
  const cloudProviders = settings.filter((p) => p.category === 'cloud');

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-gray-950/95 backdrop-blur-sm border-b border-gray-800/60">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={onClose}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to Dashboard
          </button>
          <div className="flex-1" />
          <h1 className="text-sm font-semibold text-gray-200">Provider Settings</h1>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-8 space-y-10">
        <div className="text-sm text-gray-500 bg-gray-900/40 border border-gray-800/40 rounded-xl px-4 py-3">
          Credentials are stored in the app's local database. You can also set them as environment
          variables (see <code className="text-gray-400">.env.example</code>). Environment variables
          take precedence over database values.
        </div>

        {aiProviders.length > 0 && (
          <ProviderSection title="AI Providers" providers={aiProviders} onSaved={onSaved} />
        )}
        {cloudProviders.length > 0 && (
          <ProviderSection title="Cloud Providers" providers={cloudProviders} onSaved={onSaved} />
        )}
      </div>
    </div>
  );
}
