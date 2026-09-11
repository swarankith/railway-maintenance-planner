import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Edit3,
  Check,
  Trash2,
  ArrowRight,
  Train,
  RefreshCw,
  Play,
} from 'lucide-react';
import { MaintenanceRequest, IngestResponse, TrainMovement, ActiveTab } from '../types';
import { ingestDocument, confirmRequest, deleteRequest, clearAllTrains } from '../services/api';

interface UploadModalProps {
  onIngestSuccess: () => void;
  onEditRequest: (req: MaintenanceRequest) => void;
  setActiveTab: (tab: ActiveTab) => void;
  requests: MaintenanceRequest[];
  trains: TrainMovement[];
  onTriggerOptimization: () => void;
  isOptimizing: boolean;
}

type UploadType = 'request' | 'train_movement';

export const UploadModal: React.FC<UploadModalProps> = ({
  onIngestSuccess,
  onEditRequest,
  setActiveTab,
  requests,
  trains,
  onTriggerOptimization,
  isOptimizing,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadType, setUploadType] = useState<UploadType>('request');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // FIX: eligibility matches the backend's get_eligible_requests:
  // only Confirmed, Deferred, Manual Review with cycle_id IS NULL.
  const eligibleRequests = requests.filter(
    (r) =>
      ['Confirmed', 'Deferred', 'Manual Review'].includes(r.status) &&
      !r.cycle_id
  );
  const eligibleTrains = trains.filter((t) => !t.cycle_id);

  const hasRequests = eligibleRequests.length > 0;
  const hasTrains = eligibleTrains.length > 0;

  const handleFileUpload = async (file: File) => {
    if (!file) return;
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx', 'doc', 'txt', 'csv'].includes(ext || '')) {
      setError('Please upload a valid PDF, DOCX, or CSV document.');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const res = await ingestDocument(file, uploadType);
      setIngestResult(res);
      onIngestSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to ingest file');
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleConfirmSingle = async (reqId: string) => {
    try {
      await confirmRequest(reqId);
      onIngestSuccess();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteSingle = async (reqId: string) => {
    try {
      await deleteRequest(reqId);
      onIngestSuccess();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const reviewQueue = requests.filter(
    (r) => r.status === 'Needs-Review' || r.status === 'Ingested'
  );

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-3xl shadow-sm border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-navy-950 flex items-center gap-2">
            <UploadCloud className="w-6 h-6 text-saffron-600" />
            <span>Document Ingestion & Multi-Source Gating</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Phase 2 requires both active Maintenance Requests and Scheduled Train Movements before optimization.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={onTriggerOptimization}
            disabled={isOptimizing || !hasRequests || !hasTrains}
            className="px-5 py-2.5 rounded-xl bg-saffron-500 hover:bg-saffron-600 text-navy-950 text-xs font-black shadow-md flex items-center gap-2 transition disabled:opacity-40 disabled:cursor-not-allowed"
            title={
              !hasRequests
                ? 'Upload maintenance requests first'
                : !hasTrains
                ? 'Upload train movements first'
                : 'Run deterministic optimization engine'
            }
          >
            <Play className="w-4 h-4 fill-navy-950" />
            <span>{isOptimizing ? 'Optimizing...' : 'Run Deterministic Engine'}</span>
          </button>
        </div>
      </div>

      {(!hasRequests || !hasTrains) && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl space-y-2 text-xs text-amber-900">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Engine Eligibility Gating Warning:</span>
          </div>
          <ul className="list-disc list-inside space-y-1 pl-1 text-amber-800">
            {!hasRequests && (
              <li>
                <strong>Maintenance Requests missing:</strong> Maintenance request PDF not uploaded. Upload it first (Tab: Maintenance Requests).
              </li>
            )}
            {!hasTrains && (
              <li>
                <strong>Train Movements missing:</strong> Train movement PDF not uploaded. Upload it first (Tab: Train Movements).
              </li>
            )}
          </ul>
        </div>
      )}

      <div className="flex gap-2 mb-2 flex-wrap items-center">
        <button
          onClick={() => setUploadType('request')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
            uploadType === 'request'
              ? 'bg-navy-900 text-white shadow-md'
              : 'bg-white text-navy-800 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Maintenance Requests</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/20 font-mono">
            {eligibleRequests.length} eligible
          </span>
        </button>

        <button
          onClick={() => setUploadType('train_movement')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
            uploadType === 'train_movement'
              ? 'bg-navy-900 text-white shadow-md'
              : 'bg-white text-navy-800 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <Train className="w-3.5 h-3.5" />
          <span>Train Movements</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/20 font-mono">
            {eligibleTrains.length} eligible
          </span>
        </button>
      </div>

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-3xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-200 bg-white shadow-sm ${
          isDragging
            ? 'border-saffron-500 bg-saffron-50/50 scale-[1.01]'
            : 'border-slate-300 hover:border-saffron-500 hover:bg-slate-50/50'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileUpload(e.target.files[0]);
            }
          }}
          accept=".pdf,.docx,.doc,.txt,.csv"
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-saffron-50 text-saffron-600 flex items-center justify-center border border-saffron-200 shadow-md">
            {uploading ? (
              <RefreshCw className="w-8 h-8 animate-spin" />
            ) : (
              <UploadCloud className="w-8 h-8" />
            )}
          </div>

          <div>
            <h3 className="text-base sm:text-lg font-black text-navy-950">
              {uploading
                ? 'Parsing & Normalizing Document...'
                : uploadType === 'train_movement'
                ? 'Upload Scheduled Train Movement Schedule'
                : 'Upload Maintenance Work Request Circular'}
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-md mx-auto">
              {uploadType === 'train_movement'
                ? 'Drag & drop PDF/CSV containing train numbers, corridors, and scheduled departure/arrival times.'
                : 'Drag & drop any PDF or DOCX circular (Engineering, S&T, Electrical work schedules, tables, or memos).'}
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500 pt-2 font-semibold">
            <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200">PDF Circulars & Tables</span>
            <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200">DOCX Schedules</span>
            <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200">IST Auto-Normalization</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center gap-3 text-rose-700 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {ingestResult && (
        <div className="p-5 bg-white border border-saffron-300 rounded-2xl shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center border border-emerald-300">
              <CheckCircle2 className="w-5 h-5 text-emerald-700" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-bold text-navy-950 text-sm">
                  Extracted from <span className="font-mono text-saffron-700 font-bold">{ingestResult.filename}</span>
                </h4>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-navy-100 text-navy-900 border border-navy-300">
                  {ingestResult.application_id}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {uploadType === 'train_movement' ? (
                  <span className="text-emerald-700 font-bold">
                    Successfully extracted and registered {ingestResult.detected_trains.length} scheduled train movement(s) into corridor constraints!
                  </span>
                ) : (
                  <>
                    Found {ingestResult.total_extracted} total candidate records (
                    <span className="text-emerald-700 font-bold">{ingestResult.confirmed_count} ready</span>,{' '}
                    <span className="text-amber-700 font-bold">{ingestResult.needs_review_count} needs review</span>
                    {ingestResult.detected_trains.length > 0 && `, ${ingestResult.detected_trains.length} train movements`}
                    )
                  </>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('requests')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold shadow-md transition"
            >
              <span>View All Requests</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Train Movements Table */}
      {uploadType === 'train_movement' && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center border border-blue-300">
                <Train className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-navy-950">
                  Scheduled Train Movements Pool ({eligibleTrains.length} Active / {trains.length} Total)
                </h3>
                <p className="text-xs text-slate-500">
                  These scheduled train services form hard safety constraints for corridor possession windows.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {eligibleTrains.length > 0 && (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  ✓ Ready for Engine Optimization
                </span>
              )}
              {trains.length > 0 && (
                <button
                  onClick={async () => {
                    if (window.confirm(`Are you sure you want to clear all ${trains.length} scheduled train movements?`)) {
                      await clearAllTrains();
                      onIngestSuccess();
                    }
                  }}
                  className="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 flex items-center gap-1 transition-all"
                  title="Clear all train movements"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear Trains</span>
                </button>
              )}
            </div>
          </div>

          {trains.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              No train movements loaded yet. Upload a Train Schedule PDF/CSV using the upload zone above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-800">
                <thead className="bg-navy-800 uppercase text-[10px] text-white font-bold border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">Train Number / ID</th>
                    <th className="px-4 py-3">Train Name</th>
                    <th className="px-4 py-3">Corridor</th>
                    <th className="px-4 py-3">Departure (IST)</th>
                    <th className="px-4 py-3">Arrival (IST)</th>
                    <th className="px-4 py-3">KM Span</th>
                    <th className="px-4 py-3">Speed (km/h)</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Eligibility</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trains.map((t, idx) => (
                    <tr key={t.train_id || idx} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono font-bold text-navy-950">
                        {t.train_number || t.train_id}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-800">
                        {t.train_name || 'Express Service'}
                      </td>
                      <td className="px-4 py-3 font-bold text-saffron-700">
                        {t.corridor}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-700">
                        {new Date(t.departure_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-700">
                        {new Date(t.arrival_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        KM {t.km_start.toFixed(1)} – {t.km_end.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {t.speed_kmh ? `${t.speed_kmh} km/h` : '100 km/h'}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-300">
                          {t.train_type || 'Passenger'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {!t.cycle_id ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            Active Eligible
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                            Assigned ({t.cycle_id})
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Review Queue */}
      {reviewQueue.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center border border-amber-300">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-navy-950">
                  Extracted Records Requiring Verification ({reviewQueue.length})
                </h3>
                <p className="text-xs text-slate-500">
                  Review extracted fields and resolve any missing parameters before running optimization.
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-800">
              <thead className="bg-navy-800 uppercase text-[10px] text-white font-bold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">App ID & Req ID</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Corridor & KM</th>
                  <th className="px-4 py-3">Work Type & Asset</th>
                  <th className="px-4 py-3">Duration & Window (IST)</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Validation Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {reviewQueue.map((req) => (
                  <tr
                    key={req.request_id}
                    className={`transition-colors ${
                      req.status === 'Needs-Review' ? 'bg-amber-50/40 hover:bg-amber-50/70' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-mono text-[10px] font-bold text-navy-800">{req.application_id || 'APP-LEGACY'}</div>
                      <div className="font-mono font-bold text-slate-900">{req.request_id}</div>
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-900">{req.department}</td>
                    <td className="px-4 py-3">
                      <div className="font-bold text-navy-900">{req.corridor}</div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        KM {req.km_start.toFixed(1)} – {req.km_end.toFixed(1)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-900">{req.work_type}</div>
                      <div className="text-[11px] text-slate-500">{req.asset}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-900 font-mono">
                        {req.duration_minutes} min ({Math.round((req.duration_minutes / 60) * 10) / 10}h)
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {new Date(req.earliest_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} –{' '}
                        {new Date(req.latest_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} IST
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          req.priority === 1
                            ? 'bg-rose-100 text-rose-800 border border-rose-300'
                            : req.priority === 2
                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                            : 'bg-navy-50 text-navy-800 border border-navy-200'
                        }`}
                      >
                        P{req.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {req.status === 'Needs-Review' ? (
                        <div className="space-y-1">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                            Needs Review
                          </span>
                          {req.missing_fields && req.missing_fields.length > 0 && (
                            <p className="text-[10px] text-amber-800 font-semibold">
                              Missing: {req.missing_fields.join(', ')}
                            </p>
                          )}
                        </div>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                          Ready
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onEditRequest(req)}
                          className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-navy-800 transition"
                          title="Edit / Complete Record"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleConfirmSingle(req.request_id)}
                          className="p-1.5 rounded-lg bg-emerald-100 hover:bg-emerald-200 text-emerald-800 transition"
                          title="Confirm Request"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteSingle(req.request_id)}
                          className="p-1.5 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-800 transition"
                          title="Remove Request"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {requests.length === 0 && trains.length === 0 && !uploading && (
        <div className="text-center py-12 px-4 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <FileText className="w-12 h-12 text-slate-400 mx-auto mb-3" />
          <h4 className="text-sm font-bold text-slate-800">No records in database</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Starts with an empty database. Upload maintenance requests and train movements above to run the deterministic engine.
          </p>
        </div>
      )}
    </div>
  );
};