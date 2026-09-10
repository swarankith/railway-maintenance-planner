import React, { useState, useMemo, useRef } from 'react';
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
  Minimize2,
  Info,
  ZoomIn,
  ZoomOut,
  HelpCircle,
  FileText,
} from 'lucide-react';
import { SchedulePlan, MaintenanceBlock, TrainMovement, ActiveTab, MaintenanceRequest } from '../types';

interface GanttChartProps {
  schedulePlan: SchedulePlan | null;
  trains?: TrainMovement[];
  onSelectBlock: (block: MaintenanceBlock) => void;
  setActiveTab: (tab: ActiveTab) => void;
}

export const GanttChart: React.FC<GanttChartProps> = ({
  schedulePlan,
  trains = [],
  onSelectBlock,
  setActiveTab,
}) => {
  const [selectedPlanType, setSelectedPlanType] = useState<'recommended' | 'alternative'>('recommended');
  const [selectedCorridorFilter, setSelectedCorridorFilter] = useState<string>('ALL');
  const [zoomLevel, setZoomLevel] = useState<number>(1); // 0.5x, 1x, 2x
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const pixelsPerHour = useMemo(() => {
    return Math.round(60 * zoomLevel);
  }, [zoomLevel]);

  const toggleFullscreen = () => {
    if (!isFullscreen) {
      if (containerRef.current?.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
      setIsFullscreen(false);
    }
  };

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
    if (trains.length > 0) {
      trains.forEach((t) => {
        if (!list.includes(t.corridor)) list.push(t.corridor);
      });
    }
    return list.sort();
  }, [currentPlan, trains]);

  const filteredCorridors = useMemo(() => {
    if (selectedCorridorFilter === 'ALL') return corridors;
    return corridors.filter((c) => c === selectedCorridorFilter);
  }, [corridors, selectedCorridorFilter]);

  // Timeline bounds calculation
  const { minTime, maxTime, totalHours } = useMemo(() => {
    if (!currentPlan || currentPlan.blocks.length === 0) {
      const now = new Date();
      now.setHours(0, 0, 0, 0);
      return {
        minTime: now,
        maxTime: new Date(now.getTime() + 86400000),
        totalHours: 24,
      };
    }

    const startTimes = currentPlan.blocks.map((b) => new Date(b.scheduled_start).getTime());
    const endTimes = currentPlan.blocks.map((b) => new Date(b.scheduled_end).getTime());

    if (trains && trains.length > 0) {
      trains.forEach((t) => {
        startTimes.push(new Date(t.departure_time).getTime());
        endTimes.push(new Date(t.arrival_time).getTime());
      });
    }

    const minD = new Date(Math.min(...startTimes));
    minD.setMinutes(0, 0, 0);
    const maxD = new Date(Math.max(...endTimes));
    maxD.setHours(maxD.getHours() + 2, 0, 0, 0);

    const hours = Math.max(24, Math.ceil((maxD.getTime() - minD.getTime()) / (1000 * 60 * 60)));
    return {
      minTime: minD,
      maxTime: new Date(minD.getTime() + hours * 3600000),
      totalHours: hours,
    };
  }, [currentPlan, trains]);

  const totalWidthPx = totalHours * pixelsPerHour;

  const hourTicks = useMemo(() => {
    const ticks = [];
    for (let i = 0; i <= totalHours; i++) {
      const d = new Date(minTime.getTime() + i * 3600000);
      ticks.push(d);
    }
    return ticks;
  }, [minTime, totalHours]);

  const getPixelOffset = (dateStr: string) => {
    const t = new Date(dateStr).getTime();
    const diffMs = t - minTime.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    return Math.max(0, diffHours * pixelsPerHour);
  };

  const getPixelWidth = (startStr: string, endStr: string) => {
    const s = new Date(startStr).getTime();
    const e = new Date(endStr).getTime();
    const diffHours = Math.max(0.1, (e - s) / (1000 * 60 * 60));
    return Math.max(24, diffHours * pixelsPerHour);
  };

  const deferredRequests = currentPlan?.deferred_requests || [];
  const manualReviewRequests = currentPlan?.manual_review_requests || [];

  if (!schedulePlan || schedulePlan.blocks.length === 0) {
    return (
      <div className="text-center py-20 bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
        <Calendar className="w-14 h-14 text-slate-400 mx-auto mb-4" />
        <h3 className="text-base font-bold text-slate-800">No Optimized Schedule Plan Available</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto mt-2">
          Upload maintenance requests and train movements in the Ingestion tab and trigger the Deterministic Engine to view corridor timelines.
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
    <div ref={containerRef} className={`space-y-6 ${isFullscreen ? 'bg-slate-100 p-6 overflow-y-auto' : ''}`}>
      {/* Top Banner & Plan Switcher */}
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
                Timezone: <span className="font-mono text-navy-800 font-bold">IST (UTC+5:30)</span> | Deterministic Multi-Department Schedule
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Zoom, Fullscreen, Plan Switcher */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Zoom Buttons */}
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
            <button
              onClick={() => setZoomLevel(0.5)}
              className={`px-2.5 py-1 rounded-lg font-bold transition ${
                zoomLevel === 0.5 ? 'bg-navy-800 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              0.5x
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              className={`px-2.5 py-1 rounded-lg font-bold transition ${
                zoomLevel === 1 ? 'bg-navy-800 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              1x
            </button>
            <button
              onClick={() => setZoomLevel(2)}
              className={`px-2.5 py-1 rounded-lg font-bold transition ${
                zoomLevel === 2 ? 'bg-navy-800 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              2x
            </button>
          </div>

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Full Screen' : 'Full Screen'}
            className="p-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl border border-slate-200 transition"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

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
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Review & Approve</span>
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
            Active Requests Packaged
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
            Closure Consolidation
          </div>
        </div>
      </div>

      {/* Rationale Callout */}
      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm flex items-start gap-3">
        <Info className="w-5 h-5 text-saffron-600 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-700 leading-relaxed">
          <span className="font-bold text-navy-950">Deterministic Batch Engine Rationale: </span>
          {currentPlan?.summary_explanation}
        </div>
      </div>

      {/* Filter and Legend Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
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
        <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold text-slate-600">
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
            <div className="w-3 h-3 rounded bg-gradient-to-r from-navy-800 to-saffron-600 border border-saffron-400"></div>
            <span className="text-navy-950 font-bold">Bundled Joint Block (28px)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className="w-4 h-3 rounded border border-slate-400"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(45deg, #cbd5e1, #cbd5e1 4px, #f1f5f9 4px, #f1f5f9 8px)',
              }}
            ></div>
            <span className="text-slate-700 font-bold">Train Movements (16px Hatched)</span>
          </div>
        </div>
      </div>

      {/* Main Gantt Timeline View with Sticky Corridor Column */}
      <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto relative">
          <div style={{ width: `${totalWidthPx + 160}px` }}>
            {/* Header Row */}
            <div className="flex border-b border-slate-200 bg-navy-800 text-[11px] font-mono text-white h-12 sticky top-0 z-30">
              {/* Sticky Corridor Column Header */}
              <div className="w-[160px] shrink-0 px-3 py-2 font-sans font-bold border-r border-navy-700 flex items-center justify-between text-white sticky left-0 bg-navy-800 z-40 shadow-sm">
                <span>Corridor</span>
                <span className="text-[9px] text-white/80">Lanes</span>
              </div>

              {/* Time Ruler */}
              <div className="flex-1 relative h-12 overflow-hidden">
                {hourTicks.map((tick, idx) => {
                  const leftPx = idx * pixelsPerHour;
                  return (
                    <div
                      key={idx}
                      style={{ left: `${leftPx}px`, width: `${pixelsPerHour}px` }}
                      className="absolute top-0 bottom-0 flex flex-col justify-center border-l border-white/20 pl-1"
                    >
                      <span className="text-[10px] text-white font-bold whitespace-nowrap">
                        {tick.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                      </span>
                      <span className="text-[8px] text-white/70">
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
                const corridorTrains = trains.filter((t) => t.corridor === corridor);

                return (
                  <div key={corridor} className="flex h-[56px] hover:bg-slate-50/60 transition group">
                    {/* Sticky Left Corridor Cell (160px) */}
                    <div className="w-[160px] shrink-0 px-3 py-1.5 border-r border-slate-200 bg-slate-50 flex flex-col justify-center sticky left-0 z-20 shadow-sm">
                      <div className="font-extrabold text-navy-950 text-xs truncate" title={corridor}>
                        {corridor}
                      </div>
                      <div className="text-[9px] text-slate-500 font-mono mt-0.5 flex items-center justify-between">
                        <span>{corridorBlocks.length} Blocks</span>
                        <span>{corridorTrains.length} Trains</span>
                      </div>
                    </div>

                    {/* Timeline Canvas with Maintenance Lane (28px) and Train Lane (16px) */}
                    <div className="flex-1 relative h-[56px] overflow-hidden bg-white">
                      {/* Vertical Hour Grid Lines */}
                      {hourTicks.map((tick, idx) => {
                        const leftPx = idx * pixelsPerHour;
                        return (
                          <div
                            key={idx}
                            style={{ left: `${leftPx}px` }}
                            className="absolute top-0 bottom-0 border-l border-slate-100 pointer-events-none"
                          />
                        );
                      })}

                      {/* Maintenance Lane (Top: 4px, Height: 28px) */}
                      <div className="absolute top-1 left-0 right-0 h-[28px]">
                        {corridorBlocks.map((block) => {
                          const left = getPixelOffset(block.scheduled_start);
                          const width = getPixelWidth(block.scheduled_start, block.scheduled_end);
                          const isMultiDept = block.departments.length > 1;

                          return (
                            <div
                              key={block.block_id}
                              onClick={() => onSelectBlock(block)}
                              style={{ left: `${left}px`, width: `${width}px` }}
                              title={`${block.block_id} (${block.departments.join(', ')}) | ${block.requests.length} Jobs | KM ${block.km_start}-${block.km_end}`}
                              className={`absolute top-0 bottom-0 rounded-lg px-2 py-0.5 cursor-pointer shadow-sm border flex items-center justify-between overflow-hidden text-white transition-transform hover:scale-[1.02] hover:z-30 text-[10px] ${
                                isMultiDept
                                  ? 'bg-gradient-to-r from-navy-800 via-saffron-600 to-emerald-700 border-saffron-400'
                                  : block.departments.includes('Electrical')
                                  ? 'bg-amber-700 border-amber-800 text-white'
                                  : block.departments.includes('S&T')
                                  ? 'bg-purple-800 border-purple-900 text-white'
                                  : 'bg-blue-800 border-blue-900 text-white'
                              }`}
                            >
                              <span className="font-mono font-bold truncate mr-1">{block.block_id}</span>
                              <span className="text-[8px] bg-black/30 px-1 py-0.2 rounded shrink-0">
                                {block.requests.length}J
                              </span>
                            </div>
                          );
                        })}
                      </div>

                      {/* Train Lane (Top: 34px, Height: 16px) with Diagonal Hatched Background */}
                      <div
                        className="absolute top-[34px] left-0 right-0 h-[16px] border-t border-slate-200"
                        style={{
                          backgroundImage:
                            'repeating-linear-gradient(45deg, #f8fafc, #f8fafc 6px, #f1f5f9 6px, #f1f5f9 12px)',
                        }}
                      >
                        {corridorTrains.map((train) => {
                          const left = getPixelOffset(train.departure_time);
                          const width = getPixelWidth(train.departure_time, train.arrival_time);
                          const tNum = train.train_number || train.train_id;
                          const tName = train.train_name || train.train_type || 'Train';

                          return (
                            <div
                              key={train.train_id || tNum}
                              style={{ left: `${left}px`, width: `${width}px` }}
                              title={`Train ${tNum} (${tName}) | ${train.departure_time.slice(11, 16)} - ${train.arrival_time.slice(11, 16)} | Speed: ${train.speed_kmh || 80} km/h`}
                              className="absolute top-0 bottom-0 bg-slate-700 border border-slate-800 rounded px-1 flex items-center gap-1 text-[9px] text-white overflow-hidden shadow-xs cursor-default"
                            >
                              <Train className="w-2.5 h-2.5 shrink-0 text-saffron-300" />
                              <span className="font-mono font-bold truncate">{tNum}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Placeholders for Deferred and Manual Review Requests */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Deferred Requests */}
        <div className="bg-white border border-amber-200 rounded-3xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-600" />
              <h3 className="font-bold text-sm text-navy-950">
                Deferred Requests ({deferredRequests.length})
              </h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold border border-amber-300">
              Retries &lt; 3 (Roll to next cycle)
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Requests that could not fit into current corridor windows without violating safety buffers or emergency precedence. Eligible for immediate replay.
          </p>

          {deferredRequests.length === 0 ? (
            <div className="text-xs text-slate-400 py-3 text-center bg-slate-50 rounded-xl border border-dashed border-slate-200">
              No requests currently deferred in this cycle.
            </div>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {deferredRequests.map((req: MaintenanceRequest) => (
                <div
                  key={req.request_id}
                  className="p-2.5 bg-amber-50/50 border border-amber-200 rounded-xl flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-bold text-navy-950 flex items-center gap-1.5">
                      <span>{req.request_id}</span>
                      <span className="text-[10px] text-slate-500 font-normal">({req.department})</span>
                    </div>
                    <div className="text-[11px] text-slate-600">
                      {req.corridor} | KM {req.km_start.toFixed(1)}–{req.km_end.toFixed(1)} | {req.work_type}
                    </div>
                  </div>
                  <span className="font-mono text-[10px] font-bold text-amber-800">
                    Retry #{req.retry_count || 1}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Manual Review Requests */}
        <div className="bg-white border border-rose-200 rounded-3xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              <h3 className="font-bold text-sm text-navy-950">
                Manual Review Required ({manualReviewRequests.length})
              </h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 font-bold border border-rose-300">
              Retries &ge; 3 / Rule C Exclusions
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Jobs that exceeded the retry threshold or have hard physical incompatibility conflicts requiring manual controller arbitration.
          </p>

          {manualReviewRequests.length === 0 ? (
            <div className="text-xs text-slate-400 py-3 text-center bg-slate-50 rounded-xl border border-dashed border-slate-200">
              No requests flagged for manual controller arbitration.
            </div>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {manualReviewRequests.map((req: MaintenanceRequest) => (
                <div
                  key={req.request_id}
                  className="p-2.5 bg-rose-50/50 border border-rose-200 rounded-xl flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-bold text-navy-950 flex items-center gap-1.5">
                      <span>{req.request_id}</span>
                      <span className="text-[10px] text-slate-500 font-normal">({req.department})</span>
                    </div>
                    <div className="text-[11px] text-slate-600">
                      {req.corridor} | KM {req.km_start.toFixed(1)}–{req.km_end.toFixed(1)} | {req.work_type}
                    </div>
                  </div>
                  <span className="font-mono text-[10px] font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded">
                    Needs Manual Plan
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
