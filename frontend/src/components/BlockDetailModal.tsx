import React from 'react';
import {
  X,
  Clock,
  MapPin,
  Sparkles,
  Wrench,
  Zap,
  CheckCircle2,
  Shield,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { MaintenanceBlock } from '../types';

interface BlockDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  block: MaintenanceBlock | null;
}

export const BlockDetailModal: React.FC<BlockDetailModalProps> = ({
  isOpen,
  onClose,
  block,
}) => {
  if (!isOpen || !block) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20 border border-cyan-400/30">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-bold text-slate-100 font-mono">
                  {block.block_id}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  {block.requests.length > 1 ? 'Bundled Multi-Dept Block' : 'Dedicated Single Block'}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Corridor: <span className="font-bold text-slate-200">{block.corridor}</span> | KM {block.km_start.toFixed(1)} to {block.km_end.toFixed(1)}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-6 space-y-6 flex-1 text-xs">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Scheduled Window</div>
              <div className="text-slate-100 font-mono font-bold text-sm mt-1">
                {new Date(block.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                {new Date(block.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div className="text-[10px] text-cyan-400 font-mono mt-0.5">
                {new Date(block.scheduled_start).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })} (IST)
              </div>
            </div>

            <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Block Duration</div>
              <div className="text-slate-100 font-mono font-bold text-sm mt-1">
                {block.duration_minutes} min
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {(block.duration_minutes / 60).toFixed(1)} hours closure
              </div>
            </div>

            <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Downtime Saved</div>
              <div className="text-emerald-400 font-mono font-bold text-sm mt-1">
                +{block.time_saved_minutes} min
              </div>
              <div className="text-[10px] text-emerald-400/80 mt-0.5">
                via joint bundling
              </div>
            </div>

            <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Corridor Utilization</div>
              <div className="text-cyan-300 font-mono font-bold text-sm mt-1">
                {block.utilization_score.toFixed(0)}%
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {block.departments.length} department(s)
              </div>
            </div>
          </div>

          {/* Explainability Callout (Rule 4) */}
          <div className="p-4 bg-gradient-to-r from-cyan-950/30 to-blue-950/30 border border-cyan-500/30 rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 mb-2 text-cyan-300 font-bold text-xs">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>AI Bundling & Safety Rationale (Explainable Output)</span>
            </div>
            <p className="text-slate-200 leading-relaxed text-xs">
              {block.bundling_explanation}
            </p>
          </div>

          {/* Plant & Isolation Detail */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="flex items-center gap-2 text-slate-400 font-bold mb-2">
                <Wrench className="w-4 h-4 text-cyan-400" />
                <span>Machinery & Specialized Teams Allocated</span>
              </div>
              {block.resources_allocated && block.resources_allocated.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {block.resources_allocated.map((res, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 font-mono text-[11px]"
                    >
                      {res}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 italic">Standard maintenance gang deployed.</p>
              )}
            </div>

            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="flex items-center gap-2 text-slate-400 font-bold mb-2">
                <Zap className="w-4 h-4 text-pink-400" />
                <span>Track & Power Isolation Applied</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg bg-pink-500/10 border border-pink-500/30 text-pink-300 font-semibold text-[11px]">
                  {block.isolation_applied || 'None (Live Track Proximity)'}
                </span>
              </div>
            </div>
          </div>

          {/* Included Jobs Table */}
          <div>
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              Bundled Maintenance Requests ({block.requests.length})
            </h4>
            <div className="border border-slate-800 rounded-2xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-[10px] uppercase text-slate-400 font-bold border-b border-slate-800">
                  <tr>
                    <th className="px-3 py-2.5">Job ID</th>
                    <th className="px-3 py-2.5">Department</th>
                    <th className="px-3 py-2.5">Work Type & Asset</th>
                    <th className="px-3 py-2.5">KM Span</th>
                    <th className="px-3 py-2.5">Duration</th>
                    <th className="px-3 py-2.5">Priority</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                  {block.requests.map((r) => (
                    <tr key={r.request_id} className="hover:bg-slate-800/30 transition">
                      <td className="px-3 py-2.5 font-mono font-bold text-slate-100">{r.request_id}</td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            r.department === 'Engineering'
                              ? 'bg-blue-500/20 text-blue-300'
                              : r.department === 'Electrical'
                              ? 'bg-pink-500/20 text-pink-300'
                              : 'bg-purple-500/20 text-purple-300'
                          }`}
                        >
                          {r.department}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-semibold text-slate-200">{r.work_type}</div>
                        <div className="text-[10px] text-slate-400">{r.asset}</div>
                      </td>
                      <td className="px-3 py-2.5 font-mono">
                        KM {r.km_start.toFixed(1)} - {r.km_end.toFixed(1)}
                      </td>
                      <td className="px-3 py-2.5 font-mono">{r.duration_minutes} min</td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            r.priority === 1
                              ? 'bg-rose-500/20 text-rose-300'
                              : r.priority === 2
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          P{r.priority}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            Close Detail
          </button>
        </div>
      </div>
    </div>
  );
};
