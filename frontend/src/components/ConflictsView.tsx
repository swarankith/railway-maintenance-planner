import React from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Play,
  ArrowRight,
  ShieldAlert,
  Train,
  Wrench,
  Layers,
  Clock,
  MapPin,
  CheckCircle,
} from 'lucide-react';
import { ConflictDetail, ActiveTab } from '../types';

interface ConflictsViewProps {
  conflicts: ConflictDetail[];
  onTriggerOptimization: () => void;
  setActiveTab: (tab: ActiveTab) => void;
  isOptimizing: boolean;
}

export const ConflictsView: React.FC<ConflictsViewProps> = ({
  conflicts,
  onTriggerOptimization,
  setActiveTab,
  isOptimizing,
}) => {
  const hardConflicts = conflicts.filter((c) => c.severity === 'Hard');
  const reviewOpportunities = conflicts.filter((c) => c.severity !== 'Hard');

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-navy-950 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-rose-600" />
            <span>Multi-Dimensional Conflict Analysis Matrix</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluates 4D spatial-time-KM overlaps, machine contention, live train path safety, and Rule C same-asset clashes
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onTriggerOptimization}
            disabled={isOptimizing}
            className="px-4 py-2.5 bg-saffron-500 hover:bg-saffron-600 text-navy-950 text-xs font-black rounded-xl shadow-md flex items-center gap-1.5 transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-navy-950" />
            <span>{isOptimizing ? 'Solving with CP-SAT...' : 'Run Bundling Solver'}</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-100 text-navy-900 flex items-center justify-center font-black">
            {conflicts.length}
          </div>
          <div>
            <div className="text-xs text-slate-500 font-semibold uppercase">Total Overlaps Detected</div>
            <div className="text-sm font-bold text-navy-950">Corridor Interactions</div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-rose-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center font-black">
            {hardConflicts.length}
          </div>
          <div>
            <div className="text-xs text-rose-600 font-semibold uppercase">Hard Incompatibilities</div>
            <div className="text-sm font-bold text-rose-900">Safety & Resource Clashes</div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-saffron-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-saffron-100 text-saffron-800 flex items-center justify-center font-black">
            {reviewOpportunities.length}
          </div>
          <div>
            <div className="text-xs text-saffron-700 font-semibold uppercase">Bundling Opportunities</div>
            <div className="text-sm font-bold text-saffron-950">Synergy Combinations</div>
          </div>
        </div>
      </div>

      {/* Conflict List */}
      {conflicts.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-2xl border border-slate-200 shadow-sm">
          <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-3">
            <CheckCircle className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-slate-800 text-sm">No Unresolved Conflicts Found</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            All submitted work windows are safe or ready to be combined into synchronized corridor blocks.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map((conf) => (
            <div
              key={conf.conflict_id}
              className={`p-5 rounded-2xl border bg-white shadow-sm transition-all ${
                conf.severity === 'Hard'
                  ? 'border-rose-200 border-l-4 border-l-rose-600'
                  : 'border-saffron-200 border-l-4 border-l-saffron-500'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-2 mb-2 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-1 rounded-full text-[11px] font-black uppercase ${
                      conf.severity === 'Hard'
                        ? 'bg-rose-100 text-rose-800 border border-rose-300'
                        : 'bg-saffron-100 text-saffron-800 border border-saffron-300'
                    }`}
                  >
                    {conf.conflict_type}
                  </span>
                  <span className="font-mono text-xs text-slate-400 font-bold">{conf.conflict_id}</span>
                </div>

                <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  {conf.corridor && (
                    <span className="flex items-center gap-1 font-bold text-navy-900">
                      <MapPin className="w-3.5 h-3.5 text-saffron-600" />
                      {conf.corridor}
                    </span>
                  )}
                  {conf.km_overlap_start !== undefined && conf.km_overlap_end !== undefined && (
                    <span className="font-mono text-slate-500">
                      (KM {conf.km_overlap_start.toFixed(1)} – {conf.km_overlap_end.toFixed(1)})
                    </span>
                  )}
                </div>
              </div>

              {/* Conflict Explanation */}
              <p className="text-xs text-slate-800 leading-relaxed font-medium mt-2">
                {conf.explanation}
              </p>

              {/* Suggested Resolution */}
              <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-start gap-2 text-xs">
                <ShieldAlert className="w-4 h-4 text-navy-800 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-navy-950 uppercase tracking-wider text-[10px]">
                    Recommended Solver Action:{' '}
                  </span>
                  <span className="text-slate-700">{conf.suggested_resolution}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
