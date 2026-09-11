import React, { useState } from 'react';
import {
  AlertTriangle,
  Train,
  Zap,
  ShieldAlert,
  Layers,
  MapPin,
  Clock,
  Play,
} from 'lucide-react';
import { ConflictDetail, ActiveTab } from '../types';

interface ConflictsViewProps {
  conflicts: ConflictDetail[];
  onTriggerOptimization: () => void;
  setActiveTab: (tab: ActiveTab) => void;
  isOptimizing: boolean;
}

// Safe number formatter — returns "—" for null/undefined/NaN
const fmt = (val: number | null | undefined, decimals = 1): string => {
  if (val === null || val === undefined) return '—';
  const n = typeof val === 'number' ? val : Number(val);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(decimals);
};

// Safe time formatter — returns "—" for null/undefined
const fmtTime = (val: string | null | undefined): string => {
  if (!val) return '—';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '—';
  }
};

const getConflictIcon = (type: string) => {
  switch (type) {
    case 'TrainMovement':
      return <Train className="w-5 h-5 text-rose-600" />;
    case 'Resource':
      return <Zap className="w-5 h-5 text-amber-600" />;
    case 'SameAssetClash':
      return <Layers className="w-5 h-5 text-purple-700" />;
    case 'Compatibility':
      return <ShieldAlert className="w-5 h-5 text-rose-700" />;
    case 'CompetingEmergency':
      return <ShieldAlert className="w-5 h-5 text-red-600" />;
    default:
      return <AlertTriangle className="w-5 h-5 text-amber-600" />;
  }
};

const getSeverityBadge = (severity: string) => {
  switch (severity) {
    case 'Hard':
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">
          HARD
        </span>
      );
    case 'Warning':
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
          WARNING
        </span>
      );
    default:
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-300">
          REVIEW
        </span>
      );
  }
};

export const ConflictsView: React.FC<ConflictsViewProps> = ({
  conflicts,
  onTriggerOptimization,
  setActiveTab,
  isOptimizing,
}) => {
  // Defensive: never let undefined/null reach .map / .length
  const safeConflicts: ConflictDetail[] = Array.isArray(conflicts) ? conflicts : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-navy-950 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-600" />
            <span>Conflict Analysis Matrix</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Multi-dimensional conflict detection across corridor, time, KM range, resources, and train movements.
          </p>
        </div>

        <button
          onClick={onTriggerOptimization}
          disabled={isOptimizing || safeConflicts.length === 0}
          className="px-5 py-2.5 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-black shadow-md flex items-center gap-2 transition disabled:opacity-50"
        >
          <Play className="w-4 h-4" />
          <span>{isOptimizing ? 'Optimizing...' : 'Run Bundling Engine'}</span>
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Total Conflicts</div>
          <div className="text-navy-950 font-mono font-black text-xl mt-1">{safeConflicts.length}</div>
        </div>
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Hard Conflicts</div>
          <div className="text-rose-700 font-mono font-black text-xl mt-1">
            {safeConflicts.filter((c) => c.severity === 'Hard').length}
          </div>
        </div>
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Train Conflicts</div>
          <div className="text-rose-700 font-mono font-black text-xl mt-1">
            {safeConflicts.filter((c) => c.conflict_type === 'TrainMovement').length}
          </div>
        </div>
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Review Required</div>
          <div className="text-amber-700 font-mono font-black text-xl mt-1">
            {safeConflicts.filter((c) => c.severity === 'ReviewRequired').length}
          </div>
        </div>
      </div>

      {/* Conflicts list */}
      {safeConflicts.length === 0 ? (
        <div className="text-center py-16 bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
          <AlertTriangle className="w-14 h-14 text-slate-400 mx-auto mb-4" />
          <h3 className="text-base font-bold text-slate-800">No Conflicts Detected</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-2">
            The conflict analysis found no overlapping corridor+time+KM combinations, resource contentions, or train movement collisions. You can run the bundling engine.
          </p>
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              onClick={onTriggerOptimization}
              disabled={isOptimizing}
              className="px-5 py-2.5 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition disabled:opacity-50"
            >
              {isOptimizing ? 'Optimizing...' : 'Run Bundling Engine'}
            </button>
            <button
              onClick={() => setActiveTab('requests')}
              className="px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-navy-800 text-xs font-bold border border-slate-200 transition"
            >
              Back to Requests Pool
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {safeConflicts.map((c, idx) => (
            <div
              key={c.conflict_id || idx}
              className={`bg-white border rounded-2xl p-5 shadow-sm ${
                c.severity === 'Hard'
                  ? 'border-rose-200'
                  : c.severity === 'Warning'
                  ? 'border-amber-200'
                  : 'border-blue-200'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className="shrink-0 mt-1">{getConflictIcon(c.conflict_type)}</div>

                <div className="flex-1 space-y-3">
                  {/* Top row: type + severity + ID */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-black text-navy-950 text-sm">{c.conflict_type}</span>
                    {getSeverityBadge(c.severity)}
                    <span className="font-mono text-[10px] text-slate-500">{c.conflict_id}</span>
                  </div>

                  {/* Involved requests / trains */}
                  <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
                    {c.request_ids && c.request_ids.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 font-bold">Requests:</span>
                        <span className="font-mono font-bold text-navy-900">
                          {c.request_ids.join(', ')}
                        </span>
                      </div>
                    )}
                    {c.train_id_involved && (
                      <div className="flex items-center gap-1.5">
                        <Train className="w-3.5 h-3.5 text-rose-600" />
                        <span className="text-slate-500 font-bold">Train:</span>
                        <span className="font-mono font-bold text-rose-700">{c.train_id_involved}</span>
                      </div>
                    )}
                    {c.resource_involved && (
                      <div className="flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5 text-amber-600" />
                        <span className="text-slate-500 font-bold">Resource:</span>
                        <span className="font-semibold text-amber-800">{c.resource_involved}</span>
                      </div>
                    )}
                  </div>

                  {/* Corridor and overlap details */}
                  <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
                    {c.corridor && (
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-slate-500 font-bold">Corridor:</span>
                        <span className="font-semibold text-navy-900">{c.corridor}</span>
                      </div>
                    )}

                    {(c.time_overlap_start || c.time_overlap_end) && (
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-slate-500 font-bold">Time overlap:</span>
                        <span className="font-mono text-slate-800">
                          {fmtTime(c.time_overlap_start)} – {fmtTime(c.time_overlap_end)}
                        </span>
                      </div>
                    )}

                    {(c.km_overlap_start !== null && c.km_overlap_start !== undefined) ||
                    (c.km_overlap_end !== null && c.km_overlap_end !== undefined) ? (
                      <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 font-bold">KM overlap:</span>
                        <span className="font-mono text-slate-800">
                          {fmt(c.km_overlap_start)} – {fmt(c.km_overlap_end)}
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {/* Explanation */}
                  <div className="pt-2 border-t border-slate-100">
                    <p className="text-xs text-slate-700 leading-relaxed">
                      <span className="font-bold text-navy-950">Explanation: </span>
                      {c.explanation}
                    </p>
                  </div>

                  {/* Suggested resolution */}
                  <div className="pt-2">
                    <p className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg p-2.5">
                      <span className="font-bold">Suggested Resolution: </span>
                      {c.suggested_resolution}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};