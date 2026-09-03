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

  const corridors = useMemo(() => {
    if (!currentPlan) return [];
    const list = Array.from(new Set(currentPlan.blocks.map((b) => b.corridor)));
    return list.sort();
  }, [currentPlan]);

  const filteredCorridors = useMemo(() => {
    if (selectedCorridorFilter === 'ALL') return corridors;
    return corridors.filter((c) => c === selectedCorridorFilter);
  }, [corridors, selectedCorridorFilter]);

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

  const hourTicks = useMemo(() => {
    const ticks = [];
    const current = new Date(minTime);
    while (current <= maxTime) {
      ticks.push(new Date(current));
      current.setHours(current.getHours() + 2);
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
      <div className="text-center py-20 bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
        <Calendar className="w-14 h-14 text-slate-400 mx-auto mb-4" />
        <h3 className="text-base font-bold text-slate-800">No Optimized Schedule Plan Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto mt-2">
          Upload maintenance requests in the Ingestion tab and trigger the Deterministic Bundling Engine to view corridor timelines.
        </p>
        <button
          onClick={() => setActiveTab('ingest')}
          className="mt-6 px-5 py-2.5 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition"
        >
          Go to Document Ingestion
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Alternative Plan Switcher */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-saffron-100 text-saffron-700 border border-saffron-300">
              <Calendar className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold text-navy-950 flex items-center gap-2">
                <span>{currentPlan?.plan_name}</span>
                {currentPlan?.is_recommended && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                    Recommended Plan
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Timezone: <span className="font-mono text-navy-800 font-bold">IST (UTC+5:30)</span> | Generated via Deterministic Batch Optimization
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Plan Switcher & Approval Link */}
        <div className="flex items-center gap-3 flex-wrap">
          {schedulePlan.alternative_plan && (
            <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
              <button
                onClick={() => setSelectedPlanType('recommended')}
                className={`px-3 py-1.5 rounded-lg font-bold transition ${
                  selectedPlanType === 'recommended'
                    ? 'bg-navy-800 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Plan A (Max Bundling)
              </button>
              <button
                onClick={() => setSelectedPlanType('alternative')}
                className={`px-3 py-1.5 rounded-lg font-bold transition ${
                  selectedPlanType === 'alternative'
                    ? 'bg-navy-800 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Plan B (Rapid Turnaround)
              </button>
            </div>
          )}

          <button
            onClick={() => setActiveTab('approval')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Review & Approve Plan</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Jobs Scheduled</div>
          <div className="text-navy-950 font-mono font-black text-xl mt-1">
            {currentPlan?.total_jobs_completed} / {currentPlan?.total_jobs_requested}
          </div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">
            Active Demand Processed
          </div>
        </div>

        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Corridor Downtime</div>
          <div className="text-navy-950 font-mono font-black text-xl mt-1">
            {((currentPlan?.total_corridor_downtime_minutes || 0) / 60).toFixed(1)} hrs
          </div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">
            {currentPlan?.total_corridor_downtime_minutes} total minutes
          </div>
        </div>

        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Line Time Saved</div>
          <div className="text-emerald-700 font-mono font-black text-xl mt-1">
            +{((currentPlan?.blocks.reduce((acc, b) => acc + b.time_saved_minutes, 0) || 0) / 60).toFixed(1)} hrs
          </div>
          <div className="text-[10px] text-emerald-700 font-semibold mt-0.5">
            Through Multi-Dept Bundling
          </div>
        </div>

        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Bundling Synergy</div>
          <div className="text-saffron-700 font-mono font-black text-xl mt-1">
            {currentPlan?.bundling_efficiency_percentage.toFixed(1)}%
          </div>
          <div className="text-[10px] text-saffron-800 font-semibold mt-0.5">
            Closure Consolidation Efficiency
          </div>
        </div>
      </div>

      {/* Plan Executive Rationale Callout */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm flex items-start gap-3">
        <Info className="w-5 h-5 text-saffron-600 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-700 leading-relaxed">
          <span className="font-bold text-navy-950">Batch Engine Summary: </span>
          {currentPlan?.summary_explanation}
        </div>
      </div>

      {/* Gantt Filter Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-700 font-bold">Filter Corridor:</span>
          <select
            value={selectedCorridorFilter}
            onChange={(e) => setSelectedCorridorFilter(e.target.value)}
            className="bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-slate-900 text-xs focus:outline-none focus:border-navy-800 font-semibold"
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
        <div className="hidden sm:flex items-center gap-3 text-[11px] font-semibold text-slate-600">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-700 border border-blue-900"></div>
            <span>Engineering (Civil)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-amber-600 border border-amber-700"></div>
            <span>Electrical (TRD)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-purple-700 border border-purple-900"></div>
            <span>Signal & Telecom</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-gradient-to-r from-saffron-500 to-emerald-600 border border-saffron-400"></div>
            <span className="text-navy-950 font-bold">Bundled Joint Block</span>
          </div>
        </div>
      </div>

      {/* Main Gantt Timeline View */}
      <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
        {/* Timeline Header Row (Hours) */}
        <div className="flex border-b border-slate-200 bg-navy-800 text-[11px] font-mono text-white">
          <div className="w-48 sm:w-60 shrink-0 px-4 py-3 font-sans font-bold border-r border-navy-700 flex items-center justify-between text-white">
            <span>Corridor / Route</span>
            <span className="text-[10px] text-white/80">KM Extent</span>
          </div>

          <div className="flex-1 relative h-10 overflow-hidden">
            {hourTicks.map((tick, idx) => {
              const leftPct = getPositionPercent(tick.toISOString());
              return (
                <div
                  key={idx}
                  style={{ left: `${leftPct}%` }}
                  className="absolute top-0 bottom-0 flex flex-col justify-center border-l border-white/20 pl-1.5"
                >
                  <span className="text-[10px] text-white font-bold whitespace-nowrap">
                    {tick.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                  </span>
                  <span className="text-[8px] text-white/80">
                    {tick.toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Corridor Rows */}
        <div className="divide-y divide-slate-200">
          {filteredCorridors.map((corridor) => {
            const corridorBlocks = (currentPlan?.blocks || []).filter((b) => b.corridor === corridor);

            return (
              <div key={corridor} className="flex min-h-[90px] hover:bg-slate-50 transition group">
                {/* Corridor Label Cell */}
                <div className="w-48 sm:w-60 shrink-0 px-4 py-3 border-r border-slate-200 bg-slate-50 flex flex-col justify-center">
                  <div className="font-extrabold text-navy-950 text-xs sm:text-sm tracking-tight">
                    {corridor}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    {corridorBlocks.length} Block(s) scheduled
                  </div>
                  <div className="text-[9px] text-saffron-700 font-mono font-bold mt-0.5">
                    KM {Math.min(...corridorBlocks.map((b) => b.km_start)).toFixed(1)} –{' '}
                    {Math.max(...corridorBlocks.map((b) => b.km_end)).toFixed(1)}
                  </div>
                </div>

                {/* Timeline Canvas */}
                <div className="flex-1 relative min-h-[90px] py-3 overflow-hidden bg-white">
                  {/* Background Grid Lines */}
                  {hourTicks.map((tick, idx) => {
                    const leftPct = getPositionPercent(tick.toISOString());
                    return (
                      <div
                        key={idx}
                        style={{ left: `${leftPct}%` }}
                        className="absolute top-0 bottom-0 border-l border-slate-100 pointer-events-none"
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
                        className={`absolute top-3 bottom-3 rounded-xl p-2 cursor-pointer shadow-md transition-all duration-200 hover:scale-[1.02] hover:z-20 border flex flex-col justify-between overflow-hidden text-white ${
                          isMultiDept
                            ? 'bg-gradient-to-r from-navy-800 via-saffron-600 to-emerald-700 border-saffron-400 shadow-saffron-500/20'
                            : block.departments.includes('Electrical')
                            ? 'bg-amber-700 border-amber-800 text-white'
                            : block.departments.includes('S&T')
                            ? 'bg-purple-800 border-purple-900 text-white'
                            : 'bg-blue-800 border-blue-900 text-white'
                        }`}
                      >
                        {/* Block Title & Badge */}
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-mono font-black text-[11px] text-white truncate">
                            {block.block_id}
                          </span>
                          <span
                            className={`text-[9px] font-black px-1.5 py-0.2 rounded-full ${
                              isMultiDept
                                ? 'bg-white text-navy-950 shadow-sm'
                                : 'bg-black/30 text-white'
                            }`}
                          >
                            {block.requests.length} {block.requests.length > 1 ? 'Jobs' : 'Job'}
                          </span>
                        </div>

                        {/* Timing & KM */}
                        <div className="text-[10px] text-white/90 font-mono font-bold truncate">
                          {new Date(block.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} –{' '}
                          {new Date(block.scheduled_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} IST
                        </div>

                        <div className="flex items-center justify-between text-[9px] text-white/80 pt-0.5 border-t border-white/20 font-semibold">
                          <span className="truncate">KM {block.km_start.toFixed(1)}–{block.km_end.toFixed(1)}</span>
                          {block.time_saved_minutes > 0 && (
                            <span className="text-white font-black">+{block.time_saved_minutes}m saved</span>
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
