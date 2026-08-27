import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  ShieldCheck,
  UserCheck,
  Clock,
  History,
  FileCheck,
  AlertTriangle,
  Send,
  Sparkles,
} from 'lucide-react';
import { SchedulePlan, ApprovalAudit, ActiveTab } from '../types';
import { approveSchedule, rejectSchedule, fetchAudits } from '../services/api';

interface ApprovalHubProps {
  schedulePlan: SchedulePlan | null;
  onPlanStatusChange: (updatedPlan: SchedulePlan) => void;
  setActiveTab: (tab: ActiveTab) => void;
}

export const ApprovalHub: React.FC<ApprovalHubProps> = ({
  schedulePlan,
  onPlanStatusChange,
  setActiveTab,
}) => {
  const [role, setRole] = useState<string>('Chief Controller');
  const [userName, setUserName] = useState<string>('Senior Traffic Controller');
  const [notes, setNotes] = useState<string>(
    'Reviewed corridor occupancy, power isolation alignments, and train path clearances. Recommended maintenance blocks approved for release.'
  );
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [audits, setAudits] = useState<ApprovalAudit[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (schedulePlan) {
      loadAudits(schedulePlan.schedule_id);
    }
  }, [schedulePlan]);

  const loadAudits = async (schedId: string) => {
    try {
      const log = await fetchAudits(schedId);
      setAudits(log);
    } catch {
      // Non-blocking
    }
  };

  const handleApprove = async () => {
    if (!schedulePlan) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const updated = await approveSchedule(schedulePlan.schedule_id, {
        role,
        user_name: userName,
        notes,
      });
      onPlanStatusChange(updated);
      await loadAudits(schedulePlan.schedule_id);
      setMessage({ type: 'success', text: `Schedule ${schedulePlan.schedule_id} approved successfully by ${userName} (${role}).` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to approve plan' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!schedulePlan) return;
    if (!rejectionReason.trim()) {
      alert('Please provide a mandatory reason for rejecting this schedule plan.');
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const updated = await rejectSchedule(schedulePlan.schedule_id, {
        role,
        user_name: userName,
        reason: rejectionReason,
      });
      onPlanStatusChange(updated);
      await loadAudits(schedulePlan.schedule_id);
      setShowRejectModal(false);
      setMessage({ type: 'success', text: `Schedule ${schedulePlan.schedule_id} rejected and returned for revision.` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to reject plan' });
    } finally {
      setSubmitting(false);
    }
  };

  if (!schedulePlan) {
    return (
      <div className="text-center py-20 bg-slate-900/40 border border-slate-800 rounded-3xl p-8">
        <ShieldCheck className="w-14 h-14 text-slate-600 mx-auto mb-4" />
        <h3 className="text-base font-bold text-slate-200">No Active Schedule Plan for Approval</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto mt-2">
          Generate an optimized schedule plan first to perform human planner review and approval.
        </p>
        <button
          onClick={() => setActiveTab('requests')}
          className="mt-6 px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/30 transition"
        >
          Go to Requests Pool
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Status Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-100 font-mono">
                  {schedulePlan.schedule_id}
                </h2>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    schedulePlan.status === 'Approved'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : schedulePlan.status === 'Rejected'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                  }`}
                >
                  Status: {schedulePlan.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Human-in-the-Loop Governance: The AI engine recommends; an authorized railway controller reviews and approves.
              </p>
            </div>
          </div>
        </div>

        {schedulePlan.approved_by && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300">
            <div className="font-bold">Signed by: {schedulePlan.approved_by}</div>
            <div className="text-[10px] text-emerald-400/80">
              Role: {schedulePlan.approval_role} | {schedulePlan.approval_timestamp ? new Date(schedulePlan.approval_timestamp).toLocaleString() : ''}
            </div>
          </div>
        )}
      </div>

      {message && (
        <div
          className={`p-4 rounded-2xl border text-xs flex items-center gap-2 ${
            message.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          {message.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Decision Controls Form */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-5">
        <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-cyan-400" />
          <span>Planner Authorization & Decision Log</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Select Role */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Select Operating Role
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs sm:text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
            >
              <option value="Chief Controller">Chief Controller (Operating Department)</option>
              <option value="Divisional Operations Manager (DOM)">Divisional Operations Manager (DOM)</option>
              <option value="Senior Section Engineer (SSE / P-Way)">Senior Section Engineer (SSE / Civil)</option>
              <option value="Senior Section Engineer (SSE / TRD)">Senior Section Engineer (SSE / Electrical)</option>
              <option value="Chief Yard Master (CYM)">Chief Yard Master (CYM)</option>
            </select>
          </div>

          {/* User Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Planner / Sign-off Name
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="e.g. Senior Traffic Controller"
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs sm:text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Approval Notes */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Decision Notes & Operational Comments
          </label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add operational notes regarding power isolation, traffic diversion, or speed restrictions..."
            className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs sm:text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Action Triggers */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={() => setShowRejectModal(true)}
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-xs font-bold transition disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" />
            <span>Reject / Return Plan</span>
          </button>

          <button
            type="button"
            onClick={handleApprove}
            disabled={submitting}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-extrabold shadow-lg shadow-emerald-600/30 transition disabled:opacity-50"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{submitting ? 'Recording...' : 'Authorize & Release Schedule'}</span>
          </button>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-cyan-400" />
            <h4 className="font-bold text-xs sm:text-sm text-slate-100">
              Audit Trail & Decision History
            </h4>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            {audits.length} recorded event(s)
          </span>
        </div>

        {audits.length > 0 ? (
          <div className="divide-y divide-slate-800/60">
            {audits.map((a) => (
              <div key={a.id} className="p-4 hover:bg-slate-800/30 transition flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        a.action === 'APPROVED'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-rose-500/20 text-rose-300'
                      }`}
                    >
                      {a.action}
                    </span>
                    <span className="font-bold text-slate-200">{a.user_name}</span>
                    <span className="text-slate-400">({a.role})</span>
                  </div>
                  {a.notes && <p className="text-slate-300 mt-1 text-xs">{a.notes}</p>}
                </div>

                <div className="text-[11px] text-slate-500 font-mono shrink-0">
                  {new Date(a.timestamp).toLocaleString()} IST
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-slate-500 text-xs">
            No previous approval actions recorded for this plan.
          </div>
        )}
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertTriangle className="w-5 h-5" />
              <h3 className="font-bold text-sm text-slate-100">Reject Schedule Plan</h3>
            </div>
            <p className="text-xs text-slate-400">
              State the reason for rejecting this schedule. Maintenance requests will be returned to Confirmed status for replanning.
            </p>
            <textarea
              rows={3}
              required
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Corridor NDLS-GZB has high freight precedence tonight; reduce block duration to 120 min."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-rose-500"
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="px-4 py-2 text-xs rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={submitting}
                className="px-5 py-2 text-xs rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold transition disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
