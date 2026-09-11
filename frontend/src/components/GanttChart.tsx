import React, { useState, useMemo, useRef } from 'react';
import {
  Calendar,
  Clock,
  Train,
  CheckCircle2,
  AlertTriangle,
  Maximize2,
  Minimize2,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { SchedulePlan, MaintenanceBlock, TrainMovement, ActiveTab, RequestDecision } from '../types';

interface GanttChartProps {
  schedulePlan: SchedulePlan | null;
  trains?: TrainMovement[];
  onSelectBlock: (block: MaintenanceBlock) => void;
  setActiveTab: (tab: ActiveTab) => void;
}

// ---------------------------------------------------------------------------
// Lane-stacking helper.
// Given all blocks on a corridor, assign each block to the first lane where
// it does not overlap an already-placed block on that lane. Returns the lanes
// and a map from block_id to lane index. This prevents overlapping blocks
// from rendering on top of each other.
// ---------------------------------------------------------------------------
function assignLanes(blocks: MaintenanceBlock[]) {
  const sorted = [...blocks].sort(
    (a, b) => new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime()
  );
  const lanes: MaintenanceBlock[][] = [];
  const laneFor: Record<string, number> = {};

  for (const block of sorted) {
    const bStart = new Date(block.scheduled_start).getTime();
    const bEnd = new Date(block.scheduled_end).getTime();
    let placed = false;

    for (let i = 0; i < lanes.length; i++) {
      const last = lanes[i][lanes[i].length - 1];
      const lEnd = new Date(last.scheduled_end).getTime();
      // Small 1-minute gap so touching endpoints don't get merged
      if (bStart >= lEnd - 60000) {
        lanes[i].push(block);
        laneFor[block.block_id] = i;
        placed = true;
        break;
      }
    }

    if (!placed) {
      lanes.push([block]);
      laneFor[block.block_id] = lanes.length - 1;
    }
  }

  return { lanes, laneFor };
}

export const GanttChart: React.FC<GanttChartProps> = ({
  schedulePlan,
  trains = [],
  onSelectBlock,
  setActiveTab,
}) => {
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [selectedCorridorFilter, setSelectedCorridorFilter] = useState<string>('ALL');
  const containerRef = useRef<HTMLDivElement>(null);

  const pixelsPerHour = useMemo(() => Math.round(60 * zoomLevel), [zoomLevel]);

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

  const currentPlan = schedulePlan;

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

  const { minTime, maxTime, totalHours } = useMemo(() => {
    const now = new Date();
    now.setMinutes(0, 0, 0);

    const startTimes: number[] = [];
    const endTimes: number[] = [];

    if (currentPlan && currentPlan.blocks.length > 0) {
      currentPlan.blocks.forEach((b) => {
        startTimes.push(new Date(b.scheduled_start).getTime());
        endTimes.push(new Date(b.scheduled_end).getTime());
      });
    }
    if (trains.length > 0) {
      trains.forEach((t) => {
        startTimes.push(new Date(t.departure_time).getTime());
        endTimes.push(new Date(t.arrival_time).getTime());
      });
    }

    if (startTimes.length === 0) {
      return {
        minTime: now,
        maxTime: new Date(now.getTime() + 86400000),
        totalHours: 24,
      };
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
    const ticks: Date[] = [];
    for (let i = 0; i <= totalHours; i++) {
      ticks.push(new Date(minTime.getTime() + i * 3600000));
    }
    return ticks;
  }, [minTime, totalHours]);

  const getPixelOffset = (dateStr: string) => {
    const t = new Date(dateStr).getTime();
    const diffHours = (t - minTime.getTime()) / (1000 * 60 * 60);
    return Math.max(0, diffHours * pixelsPerHour);
  };

  const getPixelWidth = (startStr: string, endStr: string) => {
    const s = new Date(startStr).getTime();
    const e = new Date(endStr).getTime();
    const diffHours = Math.max(0.1, (e - s) / (1000 * 60 * 60));
    return Math.max(24, diffHours * pixelsPerHour);
  };

  const deferredRequests: RequestDecision[] = currentPlan?.deferred_requests || [];
  const manualReviewRequests: RequestDecision[] = currentPlan?.manual_review_requests || [];
  const isolatedEmergencyRequests: RequestDecision[] = currentPlan?.isolated_emergency_requests || [];

  const hasAnyData =
    !!currentPlan &&
    (currentPlan.blocks.length > 0 ||
      deferredRequests.length > 0 ||
      manualReviewRequests.length > 0 ||
      isolatedEmergencyRequests.length > 0 ||
      trains.length > 0);

  if (!schedulePlan || !hasAnyData) {
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

  // Lane layout constants
  const BLOCK_LANE_HEIGHT = 28;
  const BLOCK_GAP = 4;
  const TRAIN_LANE_HEIGHT = 16;
  const ROW_TOP_PADDING = 4;
  const ROW_BOTTOM_PADDING = 4;
  const GAP_BLOCK_TO_TRAIN = 4;

  return (
    <div ref={containerRef} className={`space-y-6 ${isFullscreen ? 'bg-slate-100 p-6 overflow-y-auto' : ''}`}>
      {/* Top Banner */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-saffron-100 text-saffron-700 border border-saffron-300">
              <Calendar className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold text-navy-950 flex items-center gap-2">
                <span>{currentPlan?.plan_name || 'Schedule Plan'}</span>
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

        <div className="flex items-center gap-2.5 flex-wrap">
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

          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Full Screen' : 'Full Screen'}
            className="p-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl border border-slate-200 transition"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          <button
            onClick={() => setActiveTab('approval')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Review & Approve</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Jobs Handled</div>
          <div className="text-navy-950 font-mono font-black text-xl mt-1">
            {currentPlan?.total_jobs_completed} / {currentPlan?.total_jobs_requested}
          </div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">
            Approved + Isolated Emergency
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
            {(currentPlan?.bundling_efficiency_percentage || 0).toFixed(1)}%
          </div>
          <div className="text-[10px] text-saffron-800 font-semibold mt-0.5">
            Closure Consolidation
          </div>
        </div>
      </div>

      <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-sm flex items-start gap-3">
        <Info className="w-5 h-5 text-saffron-600 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-700 leading-relaxed">
          <span className="font-bold text-navy-950">Deterministic Batch Engine Rationale: </span>
          {currentPlan?.summary_explanation}
        </div>
      </div>

      {/* Filter and Legend */}
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
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold text-slate-600">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-700 border border-blue-900"></div>
            <span>Engineering</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-amber-600 border border-amber-700"></div>
            <span>Electrical</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-purple-700 border border-purple-900"></div>
            <span>S&T</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-gradient-to-r from-navy-800 via-saffron-600 to-emerald-700 border border-saffron-400"></div>
            <span className="text-navy-950 font-bold">Bundled (×N)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-rose-700 border border-rose-900"></div>
            <span className="text-rose-800 font-bold">Isolated Emergency</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className="w-4 h-3 rounded border border-slate-400"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(45deg, #cbd5e1, #cbd5e1 4px, #f1f5f9 4px, #f1f5f9 8px)',
              }}
            ></div>
            <span className="text-slate-700 font-bold">Train Movements</span>
          </div>
        </div>
      </div>

      {/* Gantt Timeline */}
      <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto relative">
          <div style={{ width: `${totalWidthPx + 160}px` }}>
            {/* Hour header */}
            <div className="flex border-b border-slate-200 bg-navy-800 text-[11px] font-mono text-white h-12 sticky top-0 z-30">
              <div className="w-[160px] shrink-0 px-3 py-2 font-sans font-bold border-r border-navy-700 flex items-center justify-between text-white sticky left-0 bg-navy-800 z-40 shadow-sm">
                <span>Corridor</span>
                <span className="text-[9px] text-white/80">Lanes</span>
              </div>
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

            {/* Corridor rows */}
            <div className="divide-y divide-slate-200">
              {filteredCorridors.map((corridor) => {
                const corridorBlocks = (currentPlan?.blocks || []).filter((b) => b.corridor === corridor);
                const corridorTrains = trains.filter((t) => t.corridor === corridor);

                // Lane-stack the blocks so overlapping ones don't cover each other
                const { lanes, laneFor } = assignLanes(corridorBlocks);
                const maxLanes = Math.max(1, lanes.length);

                const blockAreaHeight = maxLanes * BLOCK_LANE_HEIGHT;
                const trainLaneTop = ROW_TOP_PADDING + blockAreaHeight + GAP_BLOCK_TO_TRAIN;
                const rowHeight =
                  ROW_TOP_PADDING +
                  blockAreaHeight +
                  GAP_BLOCK_TO_TRAIN +
                  TRAIN_LANE_HEIGHT +
                  ROW_BOTTOM_PADDING;

                return (
                  <div
                    key={corridor}
                    className="flex hover:bg-slate-50/60 transition group"
                    style={{ height: `${rowHeight}px` }}
                  >
                    {/* Sticky left label */}
                    <div className="w-[160px] shrink-0 px-3 py-1.5 border-r border-slate-200 bg-slate-50 flex flex-col justify-center sticky left-0 z-20 shadow-sm">
                      <div className="font-extrabold text-navy-950 text-xs truncate" title={corridor}>
                        {corridor}
                      </div>
                      <div className="text-[9px] text-slate-500 font-mono mt-0.5 flex items-center justify-between">
                        <span>{corridorBlocks.length} Blocks</span>
                        <span>{maxLanes} {maxLanes > 1 ? 'Lanes' : 'Lane'}</span>
                        <span>{corridorTrains.length} Trains</span>
                      </div>
                    </div>

                    {/* Timeline canvas */}
                    <div
                      className="flex-1 relative overflow-hidden bg-white"
                      style={{ height: `${rowHeight}px` }}
                    >
                      {/* Vertical grid lines */}
                      {hourTicks.map((_, idx) => (
                        <div
                          key={idx}
                          style={{ left: `${idx * pixelsPerHour}px` }}
                          className="absolute top-0 bottom-0 border-l border-slate-100 pointer-events-none"
                        />
                      ))}

                      {/* Block lanes */}
                      {corridorBlocks.map((block) => {
                        const left = getPixelOffset(block.scheduled_start);
                        const width = getPixelWidth(block.scheduled_start, block.scheduled_end);
                        const isMultiDept = block.departments.length > 1;
                        const isEmergency =
                          block.block_id.startsWith('EMG-BLK') ||
                          (block.isolation_applied || '').toLowerCase().includes('emergency');
                        const laneIdx = laneFor[block.block_id] ?? 0;
                        const top = ROW_TOP_PADDING + laneIdx * BLOCK_LANE_HEIGHT;

                        return (
                          <div
                            key={block.block_id}
                            onClick={() => onSelectBlock(block)}
                            style={{
                              left: `${left}px`,
                              width: `${width}px`,
                              top: `${top}px`,
                              height: `${BLOCK_LANE_HEIGHT - BLOCK_GAP}px`,
                            }}
                            title={`${block.block_id} (${block.departments.join(', ')}) | ${block.requests.length} Jobs | KM ${block.km_start}-${block.km_end} | ${block.scheduled_start.slice(11, 16)}-${block.scheduled_end.slice(11, 16)}`}
                            className={`absolute rounded-lg px-2 py-0.5 cursor-pointer shadow-sm border flex items-center justify-between overflow-hidden text-white transition-transform hover:scale-[1.02] hover:z-30 text-[10px] ${
                              isEmergency
                                ? 'bg-rose-700 border-rose-900 text-white font-bold ring-1 ring-rose-400'
                                : isMultiDept
                                ? 'bg-gradient-to-r from-navy-800 via-saffron-600 to-emerald-700 border-2 border-saffron-400'
                                : block.departments.includes('Electrical')
                                ? 'bg-amber-700 border-amber-800 text-white'
                                : block.departments.includes('S&T')
                                ? 'bg-purple-800 border-purple-900 text-white'
                                : 'bg-blue-800 border-blue-900 text-white'
                            }`}
                          >
                            <span className="font-mono font-bold truncate mr-1">
                              {isEmergency && '⚠ '}
                              {block.block_id}
                            </span>
                            <span
                              className={`text-[8px] px-1 py-0.2 rounded shrink-0 font-bold ${
                                block.requests.length > 1
                                  ? 'bg-yellow-300 text-black'
                                  : 'bg-black/30 text-white'
                              }`}
                            >
                              {block.requests.length > 1 ? `×${block.requests.length}` : `${block.requests.length}J`}
                            </span>
                          </div>
                        );
                      })}

                      {/* Train lane */}
                      <div
                        className="absolute left-0 right-0 border-t border-slate-200"
                        style={{
                          top: `${trainLaneTop}px`,
                          height: `${TRAIN_LANE_HEIGHT}px`,
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
                              title={`Train ${tNum} (${tName}) | ${train.departure_time.slice(11, 16)} - ${train.arrival_time.slice(11, 16)}`}
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

      {/* Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Deferred */}
        <div className="bg-white border border-amber-200 rounded-3xl p-5 shadow-sm space-y-3 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-600" />
                <h3 className="font-bold text-sm text-navy-950">
                  Deferred Requests ({deferredRequests.length})
                </h3>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold border border-amber-300">
                Retries &lt; 3
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Requests that could not fit into current corridor windows without violating safety buffers. Eligible for next cycle.
            </p>

            {deferredRequests.length === 0 ? (
              <div className="text-xs text-slate-400 py-4 text-center bg-slate-50 rounded-xl border border-dashed border-slate-200">
                No requests currently deferred in this cycle.
              </div>
            ) : (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {deferredRequests.map((dec: RequestDecision) => (
                  <div key={dec.request_id} className="p-2.5 bg-amber-50/60 border border-amber-200 rounded-xl flex items-start justify-between gap-2 text-xs">
                    <div className="space-y-0.5">
                      <div className="font-bold text-navy-950 flex items-center gap-1.5">
                        <span>{dec.request_id}</span>
                        {dec.bundle_id && (
                          <span className="text-[9px] bg-amber-200/80 text-amber-900 px-1.5 py-0.2 rounded font-mono font-bold">
                            {dec.bundle_id}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-600 leading-tight">{dec.reason}</div>
                    </div>
                    {dec.retry_count !== undefined && dec.retry_count > 0 && (
                      <span className="font-mono text-[10px] font-bold text-amber-800 bg-amber-100 border border-amber-300 px-1.5 py-0.5 rounded shrink-0">
                        Retry #{dec.retry_count}/3
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Manual Review */}
        <div className="bg-white border border-rose-200 rounded-3xl p-5 shadow-sm space-y-3 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <h3 className="font-bold text-sm text-navy-950">
                  Manual Review Required ({manualReviewRequests.length})
                </h3>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 font-bold border border-rose-300">
                Arbitration Required
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Jobs with physical conflicts, Rule C exclusions, unrecognised work types, or retry cap reaching 3.
            </p>

            {manualReviewRequests.length === 0 ? (
              <div className="text-xs text-slate-400 py-4 text-center bg-slate-50 rounded-xl border border-dashed border-slate-200">
                No requests flagged for manual controller arbitration.
              </div>
            ) : (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {manualReviewRequests.map((dec: RequestDecision) => (
                  <div key={dec.request_id} className="p-2.5 bg-rose-50/60 border border-rose-200 rounded-xl flex items-start justify-between gap-2 text-xs">
                    <div className="space-y-0.5">
                      <div className="font-bold text-navy-950 flex items-center gap-1.5">
                        <span>{dec.request_id}</span>
                        <span className="text-[9px] bg-rose-100 text-rose-800 border border-rose-200 px-1.5 py-0.2 rounded font-mono font-bold">
                          Manual Review
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-600 leading-tight">{dec.reason}</div>
                    </div>
                    {dec.retry_count !== undefined && dec.retry_count >= 3 && (
                      <span className="font-mono text-[10px] font-bold text-rose-700 bg-rose-100 border border-rose-300 px-1.5 py-0.5 rounded shrink-0">
                        Cap 3/3
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Isolated Emergencies */}
        <div className="bg-white border border-red-200 rounded-3xl p-5 shadow-sm space-y-3 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-600" />
                <h3 className="font-bold text-sm text-navy-950">
                  Isolated Emergencies ({isolatedEmergencyRequests.length})
                </h3>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-800 font-bold border border-red-300 animate-pulse">
                Pending Human Sign-off
              </span>
            </div>
            <p className="text-xs text-slate-500">
              High-priority emergency tracks isolated on dedicated lanes. Handled as safety-critical blocks on the timeline.
            </p>

            {isolatedEmergencyRequests.length === 0 ? (
              <div className="text-xs text-slate-400 py-4 text-center bg-slate-50 rounded-xl border border-dashed border-slate-200">
                No emergency isolation requests currently active.
              </div>
            ) : (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {isolatedEmergencyRequests.map((dec: RequestDecision) => (
                  <div key={dec.request_id} className="p-2.5 bg-red-50/70 border border-red-200 rounded-xl flex items-start justify-between gap-2 text-xs">
                    <div className="space-y-0.5">
                      <div className="font-bold text-navy-950 flex items-center gap-1.5">
                        <span>{dec.request_id}</span>
                        <span className="text-[9px] bg-red-600 text-white px-1.5 py-0.2 rounded font-mono font-bold">
                          P1 Emergency
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-700 leading-tight">{dec.reason}</div>
                    </div>
                    <span className="font-mono text-[9px] font-bold text-red-700 bg-white border border-red-300 px-1.5 py-0.5 rounded shrink-0">
                      Sign-off Req.
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};