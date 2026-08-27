import React, { useState } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  Clock,
  MapPin,
  Train,
  Wrench,
  Layers,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Filter,
} from 'lucide-react';
import { ConflictDetail, ConflictType, ActiveTab } from '../types';

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
  const [selectedType, setSelectedType] = useState<string>('ALL');

  const filteredConflicts = conflicts.filter((c) => {
    if (selectedType === 'ALL') return true;
    return c.conflict_type === selectedType;
  });

  const countByType = {
    SpatialTimeKM: conflicts.filter((c) => c.conflict_type === 'SpatialTimeKM').length,
    ResourceOverlap: conflicts.filter((c) => c.conflict_type === 'ResourceOverlap').length,
    TrainMovementConflict: conflicts.filter((c) => c.conflict_type === 'TrainMovementConflict').length,
    DepartmentIncompatibility: conflicts.filter((c) => c.conflict_type === 'DepartmentIncompatibility').length,
  };

  const getConflictBadge = (type: ConflictType) => {
    switch (type) {
      case 'TrainMovementConflict':
        return {
          label: 'Train Path Collision (Critical Hard Constraint)',
          color: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
          icon: Train,
        };
      case 'ResourceOverlap':
        return {
          label: 'Resource Double-Booking',
          color: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
          icon: Wrench,
        };
      case 'DepartmentIncompatibility':
        return {
          label: 'Department Safety Incompatibility',
          color: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
          icon: ShieldAlert,
        };
      case 'SpatialTimeKM':
      default:
        return {
          label: 'Spatial & Temporal Overlap (Bundling Candidate)',
          color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
          icon: Layers,
        };
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertTriangle className="w-5 h-5" />
            </span>
            <h2 className="text-lg font-bold text-slate-100">Multi-Dimensional Conflict Analysis</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Conflict status is strictly calculated from corridor, time window (IST), and KM range overlap (Section 5).
            The CP-SAT optimization engine automatically resolves these conflicts by sequencing work or bundling compatible tasks.
          </p>
        </div>

        <button
          onClick={onTriggerOptimization}
          disabled={isOptimizing}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-bold shadow-lg shadow-cyan-600/30 transition disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" />
          <span>{isOptimizing ? 'Optimizing...' : 'Resolve & Bundle with Optimizer'}</span>
        </button>
      </div>

      {/* Categorized Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        <button
          onClick={() => setSelectedType('ALL')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap border ${
            selectedType === 'ALL'
              ? 'bg-slate-800 text-slate-100 border-slate-600'
              : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800'
          }`}
        >
          <span>All Conflicts</span>
          <span className="px-1.5 py-0.5 rounded-full bg-slate-950 text-[10px] font-mono">
            {conflicts.length}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('TrainMovementConflict')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap border ${
            selectedType === 'TrainMovementConflict'
              ? 'bg-rose-500/20 text-rose-300 border-rose-500/50'
              : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800'
          }`}
        >
          <Train className="w-3.5 h-3.5 text-rose-400" />
          <span>Train Collisions</span>
          <span className="px-1.5 py-0.5 rounded-full bg-slate-950 text-[10px] font-mono text-rose-300">
            {countByType.TrainMovementConflict}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('ResourceOverlap')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap border ${
            selectedType === 'ResourceOverlap'
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/50'
              : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800'
          }`}
        >
          <Wrench className="w-3.5 h-3.5 text-amber-400" />
          <span>Resource Double-Booking</span>
          <span className="px-1.5 py-0.5 rounded-full bg-slate-950 text-[10px] font-mono text-amber-300">
            {countByType.ResourceOverlap}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('SpatialTimeKM')}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap border ${
            selectedType === 'SpatialTimeKM'
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
              : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span>Spatial-Time-KM Overlap</span>
          <span className="px-1.5 py-0.5 rounded-full bg-slate-950 text-[10px] font-mono text-cyan-300">
            {countByType.SpatialTimeKM}
          </span>
        </button>
      </div>

      {/* Conflicts Cards Grid */}
      {filteredConflicts.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredConflicts.map((c) => {
            const badge = getConflictBadge(c.conflict_type);
            const Icon = badge.icon;

            return (
              <div
                key={c.conflict_id}
                className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl hover:border-slate-700 transition flex flex-col justify-between"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="p-1.5 rounded-lg bg-slate-800 text-slate-300 font-mono text-[10px] font-bold">
                        {c.conflict_id}
                      </span>
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border ${badge.color}`}>
                        <Icon className="w-3 h-3" />
                        <span>{badge.label}</span>
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                        c.severity === 'Hard'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      }`}
                    >
                      {c.severity}
                    </span>
                  </div>

                  {/* Plain Language Explanation */}
                  <p className="text-xs font-medium text-slate-200 leading-relaxed mb-4">
                    {c.explanation}
                  </p>

                  {/* Overlap Details Box */}
                  <div className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-2 text-[11px] font-mono text-slate-300 mb-4">
                    {c.corridor && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Corridor / Section:</span>
                        <span className="font-semibold text-slate-200">{c.corridor}</span>
                      </div>
                    )}
                    {c.time_overlap_start && c.time_overlap_end && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Overlap Window:</span>
                        <span className="text-cyan-300">
                          {new Date(c.time_overlap_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                          {new Date(c.time_overlap_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} IST
                        </span>
                      </div>
                    )}
                    {c.km_overlap_start !== undefined && c.km_overlap_end !== undefined && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">KM Span:</span>
                        <span className="text-amber-300">
                          KM {c.km_overlap_start.toFixed(1)} - {c.km_overlap_end.toFixed(1)}
                        </span>
                      </div>
                    )}
                    {c.resource_involved && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Contended Plant/Team:</span>
                        <span className="text-rose-300 font-sans font-bold">{c.resource_involved}</span>
                      </div>
                    )}
                    {c.train_id_involved && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Conflicting Train:</span>
                        <span className="text-rose-400 font-sans font-bold">{c.train_id_involved}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Suggested Resolution */}
                <div className="pt-3 border-t border-slate-800/80">
                  <div className="text-[11px] text-slate-400">
                    <span className="font-bold text-slate-300">Recommended Resolution: </span>
                    <span>{c.suggested_resolution}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-16 bg-slate-900/30 border border-slate-800 rounded-3xl">
          <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-200">Zero Unresolved Conflicts Detected</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
            All maintenance requests are spatially, temporally, and resource-compatible. You can run the CP-SAT optimizer to bundle them into blocks.
          </p>
        </div>
      )}
    </div>
  );
};
