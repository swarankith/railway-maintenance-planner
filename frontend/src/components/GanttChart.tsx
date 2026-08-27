import React, { useState, useMemo } from 'react';
import {
  Calendar,
  Clock,
  MapPin,
  Sparkles,
  Layers,
  Train,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Sliders,
  Maximize2,
  Info,
} from 'lucide-react';
import { SchedulePlan, MaintenanceBlock, TrainMovement, ActiveTab } from '../types';

interface GanttChartProps {
  schedulePlan: SchedulePlan | null;
  onSelectBlock: (block: MaintenanceBlock) => void;
  setActiveTab: (tab: ActiveTab) => void;
}

export const GanttChart: React.FC<GanttChartProps> = ({
  schedulePlan,
  onSelectBlock,
  setActiveTab,
}) => {
  const [selectedPlanType, setSelectedPlanType] = useState<'recommended' | 'alternative'>('recommended');
  const [selectedCorridorFilter, setSelectedCorridorFilter] = useState<string>('ALL');

  const currentPlan = useMemo(() => {
    if (!schedulePlan) return null;
    if (selectedPlanType === 'alternative' && schedulePlan.alternative_plan) {
      return schedulePlan.alternative_plan;
    }
    return schedulePlan;
  }, [schedulePlan, selectedPlanType]);

  // Extract unique corridors
  const corridors = useMemo(() => {
    if (!currentPlan) return [];
    const list = Array.from(new Set(currentPlan.blocks.map((b) => b.corridor)));
    return list.sort();
  }, [currentPlan]);

  const filteredCorridors = useMemo(() => {
    if (selectedCorridorFilter === 'ALL') return corridors;
    return corridors.filter((c) => c === selectedCorridorFilter);
  }, [corridors, selectedCorridorFilter]);

  // Timeline scale calculation: 24-hour window from baseline
  const { minTime, maxTime, totalDurationMs } = useMemo(() => {
    if (!currentPlan || currentPlan.blocks.length === 0) {
      const now = new Date();
      now.setHours(0, 0, 0, 0);
      return {
        minTime: now,
        maxTime: new Date(now.getTime() + 86400000),
        totalDurationMs: 86400000,
      };
    }

    const startTimes = currentPlan.blocks.map((b) => new Date(b.scheduled_start).getTime());
    const endTimes = currentPlan.blocks.map((b) => new Date(b.scheduled_end).getTime());
    
    // Expand to midnight boundary for neat hourly grid
    const minD = new Date(Math.min(...startTimes));
    minD.setMinutes(0, 0, 0);
    const maxD = new Date(Math.max(...endTimes));
    maxD.setHours(maxD.getHours() + 2, 0, 0, 0);

    const dur = Math.max(86400000, maxD.getTime() - minD.getTime());
    return {
      minTime: minD,
      maxTime: maxD,
      totalDurationMs: dur,
    };
  }, [currentPlan]);

  // Hourly grid markers
  const hourTicks = useMemo(() => {
    const ticks = [];
    const current = new Date(minTime);
    while (current <= maxTime) {
      ticks.push(new Date(current));
      current.setHours(current.getHours() + 2); // 2-hour increments
    }
    return ticks;
  }, [minTime, maxTime]);

  const getPositionPercent = (dateStr: string) => {
    const t = new Date(dateStr).getTime();
    const percent = ((t - minTime.getTime()) / totalDurationMs) * 100;
    return Math.max(0, Math.min(100, percent));
  };

  const getWidthPercent = (startStr: string, endStr: string) => {
    const s = new Date(startStr).getTime();
    const e = new Date(endStr).getTime();
    const percent = ((e - s) / totalDurationMs) * 100;
    return Math.max(1.5, percent);
  };

  if (!schedulePlan || schedulePlan.blocks.length === 0) {
    return (
      <div className="text-center py-20 bg-slate-900/40 border border-slate-800 rounded-3xl p-8">
        <Calendar className="w-14 h-14 text-slate-600 mx-auto mb-4" />
        <h3 className="text-base font-bold text-slate-200">No Optimized Schedule Plan Available</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto mt-2">
          Upload maintenance requests in the Ingestion tab and trigger the CP-SAT optimization engine to generate interactive corridor timelines.
        </p>
        <button
          onClick={() => setActiveTab('ingest')}
          className="mt-6 px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/30 transition"
        >
          Go to Document Ingestion
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Alternative Plan Switcher */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 shadow-xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Calendar className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <span>{currentPlan?.plan_name}</span>
                {currentPlan?.is_recommended && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    Recommended Solution
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Timezone: <span className="font-mono text-cyan-300">Indian Standard Time (IST, UTC+5:30)</span> | Generated via Google OR-Tools CP-SAT
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Plan Switcher & Approval Link */}
        <div className="flex items-center gap-3 flex-wrap">
          {schedulePlan.alternative_plan && (
            <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                onClick={() => setSelectedPlanType('recommended')}
                className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                  selectedPlanType === 'recommended'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Plan A (Max Bundling)
              </button>
              <button
                onClick={() => setSelectedPlanType('alternative')}
                className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                  selectedPlanType === 'alternative'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Plan B (Rapid Turnaround)
              </button>
            </div>
          )}

          <button
            onClick={() => setActiveTab('approval')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Review & Approve Plan</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Jobs Scheduled</div>
          <div className="text-slate-100 font-mono font-extrabold text-xl mt-1">
            {currentPlan?.total_jobs_completed} / {currentPlan?.total_jobs_requested}
          </div>
          <div className="text-[10px] text-emerald-400 font-semibold mt-0.5">
            100% Demand Met
          </div>
        </div>

        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Corridor Downtime</div>
          <div className="text-slate-100 font-mono font-extrabold text-xl mt-1">
            {(currentPlan?.total_corridor_downtime_minutes || 0) / 60} hrs
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
            {currentPlan?.total_corridor_downtime_minutes} total minutes
          </div>
        </div>

        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Line Time Saved</div>
          <div className="text-emerald-400 font-mono font-extrabold text-xl mt-1">
            +{(currentPlan?.blocks.reduce((acc, b) => acc + b.time_saved_minutes, 0) || 0) / 60} hrs
          </div>
          <div className="text-[10px] text-emerald-400/80 font-semibold mt-0.5">
            Through Multi-Dept Bundling
          </div>
        </div>

        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Bundling Synergy</div>
          <div className="text-cyan-300 font-mono font-extrabold text-xl mt-1">
            {currentPlan?.bundling_efficiency_percentage.toFixed(1)}%
          </div>
          <div className="text-[10px] text-cyan-400/80 font-semibold mt-0.5">
            Closure Consolidation Score
          </div>
        </div>
      </div>

      {/* Plan Executive Rationale Callout */}
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl flex items-start gap-3">
        <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-300 leading-relaxed">
          <span className="font-bold text-slate-100">Optimizer Summary: </span>
          {currentPlan?.summary_explanation}
        </div>
      </div>

      {/* Gantt Filter Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400 font-semibold">Filter Corridor:</span>
          <select
            value={selectedCorridorFilter}
            onChange={(e) => setSelectedCorridorFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Corridors ({corridors.length})</option>
            {corridors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Legend */}
        <div className="hidden sm:flex items-center gap-3 text-[11px] font-medium text-slate-400">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-500/80 border border-blue-400"></div>
            <span>Engineering (Civil)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-pink-500/80 border border-pink-400"></div>
            <span>Electrical (TRD)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-purple-500/80 border border-purple-400"></div>
            <span>Signal & Telecom</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-gradient-to-r from-cyan-500 to-emerald-500 border border-cyan-300"></div>
            <span className="text-cyan-300 font-bold">Bundled Joint Block</span>
          </div>
        </div>
      </div>

      {/* Main Gantt Timeline View */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
        {/* Timeline Header Row (Hours) */}
        <div className="flex border-b border-slate-800 bg-slate-950/80 text-[11px] font-mono text-slate-400">
          <div className="w-48 sm:w-60 shrink-0 px-4 py-3 font-sans font-bold border-r border-slate-800 flex items-center justify-between text-slate-300">
            <span>Corridor / Route</span>
            <span className="text-[10px] text-slate-500">KM Extent</span>
          </div>

          <div className="flex-1 relative h-10 overflow-hidden">
            {hourTicks.map((tick, idx) => {
              const leftPct = getPositionPercent(tick.toISOString());
              return (
                <div
                  key={idx}
                  style={{ left: `${leftPct}%` }}
                  className="absolute top-0 bottom-0 flex flex-col justify-center border-l border-slate-800/80 pl-1.5"
                >
                  <span className="text-[10px] text-slate-400 font-bold whitespace-nowrap">
                    {tick.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                  </span>
                  <span className="text-[8px] text-slate-600">
                    {tick.toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Corridor Rows */}
        <div className="divide-y divide-slate-800/60">
          {filteredCorridors.map((corridor) => {
            const corridorBlocks = (currentPlan?.blocks || []).filter((b) => b.corridor === corridor);

            return (
              <div key={corridor} className="flex min-h-[90px] hover:bg-slate-800/20 transition group">
                {/* Corridor Label Cell */}
                <div className="w-48 sm:w-60 shrink-0 px-4 py-3 border-r border-slate-800/80 bg-slate-950/40 flex flex-col justify-center">
                  <div className="font-extrabold text-slate-100 text-xs sm:text-sm tracking-tight">
                    {corridor}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    {corridorBlocks.length} Block(s) scheduled
                  </div>
                  <div className="text-[9px] text-cyan-400/80 font-mono mt-0.5">
                    KM {Math.min(...corridorBlocks.map((b) => b.km_start)).toFixed(1)} -{' '}
                    {Math.max(...corridorBlocks.map((b) => b.km_end)).toFixed(1)}
                  </div>
                </div>

                {/* Timeline Canvas */}
                <div className="flex-1 relative min-h-[90px] py-3 overflow-hidden bg-slate-950/20">
                  {/* Background Grid Lines */}
                  {hourTicks.map((tick, idx) => {
                    const leftPct = getPositionPercent(tick.toISOString());
                    return (
                      <div
                        key={idx}
                        style={{ left: `${leftPct}%` }}
                        className="absolute top-0 bottom-0 border-l border-slate-800/30 pointer-events-none"
                      />
                    );
                  })}

                  {/* Scheduled Block Cards */}
                  {corridorBlocks.map((block) => {
                    const leftPct = getPositionPercent(block.scheduled_start);
                    const widthPct = getWidthPercent(block.scheduled_start, block.scheduled_end);
                    const isMultiDept = block.departments.length > 1;

                    return (
                      <div
                        key={block.block_id}
                        onClick={() => onSelectBlock(block)}
                        style={{
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          minWidth: '130px',
                        }}
                        className={`absolute top-3 bottom-3 rounded-xl p-2 cursor-pointer shadow-lg transition-all duration-200 hover:scale-[1.02] hover:z-20 border flex flex-col justify-between overflow-hidden ${
                          isMultiDept
                            ? 'bg-gradient-to-r from-cyan-900/90 via-emerald-950/90 to-blue-900/90 border-cyan-400/50 shadow-cyan-500/10'
                            : block.departments.includes('Electrical')
                            ? 'bg-pink-950/80 border-pink-500/50 text-pink-100 shadow-pink-500/10'
                            : block.departments.includes('S&T')
                            ? 'bg-purple-950/80 border-purple-500/50 text-purple-100 shadow-purple-500/10'
                            : 'bg-blue-950/80 border-blue-500/50 text-blue-100 shadow-blue-500/10'
                        }`}
                      >
                        {/* Block Title & Badge */}
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-mono font-extrabold text-[11px] text-white truncate">
                            {block.block_id}
                          </span>
                          <span
                            className={`text-[9px] font-extrabold px-1.5 py-0.2 rounded-full ${
                              isMultiDept
                                ? 'bg-emerald-500/30 text-emerald-200 border border-emerald-400/40'
                                : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {block.requests.length} {block.requests.length > 1 ? 'Jobs' : 'Job'}
                          </span>
                        </div>

                        {/* Timing & KM */}
                        <div className="text-[10px] text-slate-200 font-mono truncate">
                          {new Date(block.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} -{' '}
                          {new Date(block.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} IST
                        </div>

                        <div className="flex items-center justify-between text-[9px] text-slate-300 pt-0.5 border-t border-white/10">
                          <span className="truncate">KM {block.km_start.toFixed(1)}-{block.km_end.toFixed(1)}</span>
                          {block.time_saved_minutes > 0 && (
                            <span className="text-emerald-300 font-bold">+{block.time_saved_minutes}m saved</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
