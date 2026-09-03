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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white border border-slate-300 rounded-3xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-navy-800 text-white flex items-center justify-center shadow-md">
              <Layers className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-bold text-navy-950 font-mono">
                  {block.block_id}
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-saffron-100 text-saffron-800 border border-saffron-300">
                  {block.requests.length > 1 ? 'Bundled Multi-Dept Block' : 'Dedicated Single Block'}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Corridor: <span className="font-bold text-navy-900">{block.corridor}</span> | KM {block.km_start.toFixed(1)} to {block.km_end.toFixed(1)}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="overflow-y-auto p-6 space-y-6 flex-1 text-xs">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Scheduled Window</div>
              <div className="text-navy-950 font-mono font-bold text-sm mt-1">
                {new Date(block.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} –{' '}
                {new Date(block.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
              </div>
              <div className="text-[10px] text-navy-800 font-mono font-bold mt-0.5">
                {new Date(block.scheduled_start).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })} (IST)
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Block Duration</div>
              <div className="text-navy-950 font-mono font-bold text-sm mt-1">
                {block.duration_minutes} min
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                {(block.duration_minutes / 60).toFixed(1)} hours closure
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Downtime Saved</div>
              <div className="text-emerald-700 font-mono font-bold text-sm mt-1">
                +{block.time_saved_minutes} min
              </div>
              <div className="text-[10px] text-emerald-700 mt-0.5">
                via joint bundling
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="text-slate-500 text-[10px] uppercase font-bold">Corridor Utilization</div>
              <div className="text-saffron-700 font-mono font-bold text-sm mt-1">
                {block.utilization_score.toFixed(0)}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                {block.departments.length} department(s)
              </div>
            </div>
          </div>

          {/* Explainability Callout */}
          <div className="p-4 bg-saffron-50 border border-saffron-200 rounded-2xl shadow-sm">
            <div className="flex items-center gap-2 mb-2 text-saffron-800 font-bold text-xs">
              <Sparkles className="w-4 h-4 text-saffron-600" />
              <span>AI Bundling & Safety Rationale (Explainable Output)</span>
            </div>
            <p className="text-slate-800 leading-relaxed text-xs">
              {block.bundling_explanation}
            </p>
          </div>

          {/* Machinery & Isolation */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="flex items-center gap-2 text-slate-700 font-bold mb-2">
                <Wrench className="w-4 h-4 text-navy-800" />
                <span>Machinery & Specialized Teams Allocated</span>
              </div>
              {block.resources_allocated && block.resources_allocated.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {block.resources_allocated.map((res, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-800 font-mono text-[11px]"
                    >
                      {res}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 italic">Standard maintenance gang deployed.</p>
              )}
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl">
              <div className="flex items-center gap-2 text-slate-700 font-bold mb-2">
                <Zap className="w-4 h-4 text-amber-600" />
                <span>Track & Power Isolation Applied</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 font-bold text-[11px]">
                  {block.isolation_applied || 'None (Live Track Proximity)'}
                </span>
              </div>
            </div>
          </div>

          {/* Included Jobs Table */}
          <div>
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Bundled Maintenance Requests ({block.requests.length})
            </h4>
            <div className="border border-slate-200 rounded-2xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-800">
                <thead className="bg-navy-800 text-[10px] uppercase text-white font-bold border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2.5">App ID</th>
                    <th className="px-3 py-2.5">Job ID</th>
                    <th className="px-3 py-2.5">Department</th>
                    <th className="px-3 py-2.5">Work Type & Asset</th>
                    <th className="px-3 py-2.5">KM Span</th>
                    <th className="px-3 py-2.5">Duration</th>
                    <th className="px-3 py-2.5">Priority</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {block.requests.map((r) => (
                    <tr key={r.request_id} className="hover:bg-slate-50 transition">
                      <td className="px-3 py-2.5 font-mono text-navy-800 font-semibold">{r.application_id || 'APP-LEGACY'}</td>
                      <td className="px-3 py-2.5 font-mono font-bold text-slate-900">{r.request_id}</td>
                      <td className="px-3 py-2.5 font-semibold">{r.department}</td>
                      <td className="px-3 py-2.5">
                        <div className="font-semibold text-slate-900">{r.work_type}</div>
                        <div className="text-[10px] text-slate-500">{r.asset}</div>
                      </td>
                      <td className="px-3 py-2.5 font-mono">
                        KM {r.km_start.toFixed(1)} – {r.km_end.toFixed(1)}
                      </td>
                      <td className="px-3 py-2.5 font-mono">{r.duration_minutes} min</td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            r.priority === 1
                              ? 'bg-rose-100 text-rose-800'
                              : r.priority === 2
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-navy-50 text-navy-800'
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
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold rounded-xl bg-navy-800 hover:bg-navy-900 text-white transition"
          >
            Close Detail
          </button>
        </div>
      </div>
    </div>
  );
};
