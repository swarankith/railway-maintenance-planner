import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Edit3,
  Check,
  Trash2,
  Sparkles,
  ArrowRight,
  Train,
  Clock,
  MapPin,
  RefreshCw,
} from 'lucide-react';
import { MaintenanceRequest, IngestResponse, TrainMovement, ActiveTab } from '../types';
import { ingestDocument, confirmRequest, deleteRequest } from '../services/api';

interface UploadModalProps {
  onIngestSuccess: () => void;
  onEditRequest: (req: MaintenanceRequest) => void;
  setActiveTab: (tab: ActiveTab) => void;
  requests: MaintenanceRequest[];
}

export const UploadModal: React.FC<UploadModalProps> = ({
  onIngestSuccess,
  onEditRequest,
  setActiveTab,
  requests,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (file: File) => {
    if (!file) return;
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx', 'doc', 'txt'].includes(ext || '')) {
      setError('Please upload a valid PDF or DOCX railway maintenance request document.');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const res = await ingestDocument(file);
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

  // Filter requests that are newly ingested or need review
  const reviewQueue = requests.filter(
    (r) => r.status === 'Needs-Review' || r.status === 'Ingested'
  );

  return (
    <div className="space-y-6">
      {/* Upload Drag & Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-3xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-200 ${
          isDragging
            ? 'border-cyan-400 bg-cyan-500/10 scale-[1.01]'
            : 'border-slate-700 hover:border-slate-500 bg-slate-900/50 hover:bg-slate-900/80'
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
          accept=".pdf,.docx,.doc,.txt"
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shadow-lg shadow-cyan-500/10">
            {uploading ? (
              <RefreshCw className="w-8 h-8 animate-spin" />
            ) : (
              <UploadCloud className="w-8 h-8" />
            )}
          </div>

          <div>
            <h3 className="text-base sm:text-lg font-bold text-slate-100">
              {uploading
                ? 'Parsing & Normalizing Maintenance Requests...'
                : 'Upload Maintenance Work Request Documents'}
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-md mx-auto">
              Drag & drop any <span className="text-cyan-300 font-semibold">PDF or DOCX</span> file (Engineering, S&T, Electrical work schedules, tables, or plain prose memos).
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400 pt-2">
            <span className="px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700">PDF Tables & Forms</span>
            <span className="px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700">DOCX Circulars</span>
            <span className="px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700">Train Movement Records</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl flex items-center gap-3 text-rose-300 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Ingest Summary Banner */}
      {ingestResult && (
        <div className="p-5 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-slate-900 border border-cyan-500/30 rounded-2xl shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-300 flex items-center justify-center border border-cyan-500/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h4 className="font-bold text-slate-100 text-sm">
                Extracted from <span className="font-mono text-cyan-300">{ingestResult.filename}</span>
              </h4>
              <p className="text-xs text-slate-400">
                Found {ingestResult.total_extracted} total candidate requests (
                <span className="text-emerald-400 font-medium">{ingestResult.confirmed_count} ready</span>,{' '}
                <span className="text-amber-400 font-medium">{ingestResult.needs_review_count} needs review</span>
                {ingestResult.detected_trains.length > 0 && `, ${ingestResult.detected_trains.length} train movements`}
                )
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('requests')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 transition"
            >
              <span>View All Requests</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Needs Review & Ingested Review Queue */}
      {reviewQueue.length > 0 && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-300 flex items-center justify-center border border-amber-500/30">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-100">
                  Extracted Records Requiring Verification ({reviewQueue.length})
                </h3>
                <p className="text-xs text-slate-400">
                  Review extracted fields and resolve any missing parameters before running optimization.
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 uppercase text-[10px] text-slate-400 font-bold border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3">ID & Dept</th>
                  <th className="px-4 py-3">Corridor & KM</th>
                  <th className="px-4 py-3">Work Type & Asset</th>
                  <th className="px-4 py-3">Duration & Window (IST)</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Validation Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {reviewQueue.map((req) => (
                  <tr
                    key={req.request_id}
                    className={`transition-colors ${
                      req.status === 'Needs-Review'
                        ? 'bg-amber-500/[0.04] hover:bg-amber-500/[0.08]'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-mono font-bold text-slate-100">{req.request_id}</div>
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold mt-1 ${
                          req.department === 'Engineering'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : req.department === 'Electrical'
                            ? 'bg-pink-500/20 text-pink-300 border border-pink-500/30'
                            : 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        }`}
                      >
                        {req.department}
                      </span>
                    </td>

                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-200">{req.corridor}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        KM {req.km_start.toFixed(1)} - {req.km_end.toFixed(1)}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-200">{req.work_type}</div>
                      <div className="text-[11px] text-slate-400">{req.asset}</div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-200 font-mono">
                        {req.duration_minutes} min ({Math.round(req.duration_minutes / 60 * 10) / 10}h)
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {new Date(req.earliest_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                        {new Date(req.latest_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} IST
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          req.priority === 1
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                            : req.priority === 2
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : 'bg-slate-700 text-slate-300'
                        }`}
                      >
                        P{req.priority}
                      </span>
                    </td>

                    <td className="px-4 py-3">
                      {req.status === 'Needs-Review' ? (
                        <div className="space-y-1">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                            Needs Review
                          </span>
                          {req.missing_fields && req.missing_fields.length > 0 && (
                            <p className="text-[10px] text-amber-400/80">
                              Missing: {req.missing_fields.join(', ')}
                            </p>
                          )}
                        </div>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                          Ready
                        </span>
                      )}
                    </td>

                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onEditRequest(req)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 hover:text-cyan-200 transition"
                          title="Edit / Complete Record"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleConfirmSingle(req.request_id)}
                          className="p-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 transition"
                          title="Confirm Request"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteSingle(req.request_id)}
                          className="p-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 transition"
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

      {/* Empty State Prompt */}
      {requests.length === 0 && !uploading && (
        <div className="text-center py-12 px-4 bg-slate-900/30 border border-slate-800/80 rounded-2xl">
          <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h4 className="text-sm font-bold text-slate-300">No maintenance requests in database</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            As specified in Rule 1, the app starts with a completely empty database. Upload a PDF or DOCX document above to begin.
          </p>
        </div>
      )}
    </div>
  );
};
