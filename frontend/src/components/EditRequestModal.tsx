import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, Sparkles, Wrench, Clock, MapPin, Zap } from 'lucide-react';
import { MaintenanceRequest, Department, BlockType } from '../types';

interface EditRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<MaintenanceRequest>) => Promise<void>;
  request: Partial<MaintenanceRequest> | null;
  isNew?: boolean;
}

export const EditRequestModal: React.FC<EditRequestModalProps> = ({
  isOpen,
  onClose,
  onSave,
  request,
  isNew = false,
}) => {
  const [formData, setFormData] = useState<Partial<MaintenanceRequest>>({
    request_id: '',
    application_id: '',
    department: 'Engineering',
    corridor: '',
    km_start: 0,
    km_end: 10,
    asset: 'Track Section',
    work_type: 'Track Tamping',
    priority: 3,
    priority_reason: '',
    block_type: 'Normal',
    duration_minutes: 180,
    earliest_start: new Date(Date.now() + 86400000).toISOString().slice(0, 16),
    latest_end: new Date(Date.now() + 86400000 + 18000000).toISOString().slice(0, 16),
    required_resources: [],
    isolation_requirement: 'None',
    block_shared_allowed: true,
  });

  const [resourceInput, setResourceInput] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (request) {
      const fmtDate = (d?: string) => {
        if (!d) return new Date().toISOString().slice(0, 16);
        try {
          return new Date(d).toISOString().slice(0, 16);
        } catch {
          return new Date().toISOString().slice(0, 16);
        }
      };

      setFormData({
        ...request,
        earliest_start: fmtDate(request.earliest_start),
        latest_end: fmtDate(request.latest_end),
      });
      setResourceInput((request.required_resources || []).join(', '));
    }
  }, [request]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const resources = resourceInput
        .split(',')
        .map((r) => r.trim())
        .filter((r) => r.length > 0);

      await onSave({
        ...formData,
        required_resources: resources,
        km_start: Number(formData.km_start),
        km_end: Number(formData.km_end),
        duration_minutes: Number(formData.duration_minutes),
        priority: Number(formData.priority) in [1, 2, 3] ? Number(formData.priority) : 3,
        corridor: (formData.corridor || '').toUpperCase().trim(),
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save request');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white border border-slate-300 rounded-3xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-saffron-100 text-saffron-700 flex items-center justify-center border border-saffron-300">
              <Wrench className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-navy-950">
                {isNew ? 'Create New Maintenance Request' : `Edit Request ${formData.request_id || ''}`}
              </h2>
              <p className="text-xs text-slate-500">
                {isNew ? 'Manual entry into system' : 'Complete missing fields to verify candidate record'}
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="overflow-y-auto p-6 space-y-4 flex-1">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {formData.missing_fields && formData.missing_fields.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-2 text-amber-800 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <div>
                <span className="font-bold">Missing extracted fields: </span>
                <span>{formData.missing_fields.join(', ')}. Please fill to confirm.</span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Request ID */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Request ID</label>
              <input
                type="text"
                value={formData.request_id || ''}
                onChange={(e) => setFormData({ ...formData, request_id: e.target.value })}
                placeholder="e.g. REQ-ENG-101"
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-bold"
              />
            </div>

            {/* Department */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Department</label>
              <select
                value={formData.department || 'Engineering'}
                onChange={(e) => setFormData({ ...formData, department: e.target.value as Department })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-semibold"
              >
                <option value="Engineering">Engineering (Civil / Track)</option>
                <option value="Electrical">Electrical (TRD / OHE)</option>
                <option value="S&T">Signal & Telecom (S&T)</option>
                <option value="Operations">Operations / Traffic</option>
                <option value="Other">Other</option>
              </select>
            </div>

            {/* Corridor */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Corridor / Section</label>
              <input
                type="text"
                required
                value={formData.corridor || ''}
                onChange={(e) => setFormData({ ...formData, corridor: e.target.value.toUpperCase() })}
                placeholder="e.g. NDLS-GZB or HWH-KGP"
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-bold"
              />
            </div>

            {/* Block Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Block Type</label>
              <select
                value={formData.block_type || 'Normal'}
                onChange={(e) => setFormData({ ...formData, block_type: e.target.value as BlockType })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-semibold"
              >
                <option value="Normal">Normal</option>
                <option value="Emergency">Emergency</option>
                <option value="Planned">Planned / Mega Block</option>
              </select>
            </div>

            {/* KM Start */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">KM Start</label>
              <input
                type="number"
                step="0.1"
                required
                value={formData.km_start ?? 0}
                onChange={(e) => setFormData({ ...formData, km_start: parseFloat(e.target.value) })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-bold"
              />
            </div>

            {/* KM End */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">KM End</label>
              <input
                type="number"
                step="0.1"
                required
                value={formData.km_end ?? 10}
                onChange={(e) => setFormData({ ...formData, km_end: parseFloat(e.target.value) })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-bold"
              />
            </div>

            {/* Asset */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Asset Description</label>
              <input
                type="text"
                required
                value={formData.asset || ''}
                onChange={(e) => setFormData({ ...formData, asset: e.target.value })}
                placeholder="e.g. Track Section, OHE Catenary"
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800"
              />
            </div>

            {/* Work Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Work Type</label>
              <input
                type="text"
                required
                value={formData.work_type || ''}
                onChange={(e) => setFormData({ ...formData, work_type: e.target.value })}
                placeholder="e.g. Track Tamping, OHE Overhaul"
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800"
              />
            </div>

            {/* Priority (Phase 2: 1 = Emergency, 2 = High Urgent, 3 = Normal) */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Priority Scale (Phase 2: 1 = Emergency, 2 = High Urgent, 3 = Normal)
              </label>
              <select
                value={formData.priority || 3}
                onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-bold"
              >
                <option value={1}>P1 — Emergency</option>
                <option value={2}>P2 — High Urgent</option>
                <option value={3}>P3 — Normal</option>
              </select>
            </div>

            {/* Duration Minutes */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Duration (Minutes)</label>
              <input
                type="number"
                required
                min="15"
                step="15"
                value={formData.duration_minutes || 180}
                onChange={(e) => setFormData({ ...formData, duration_minutes: parseInt(e.target.value) })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-bold"
              />
            </div>

            {/* Earliest Start (IST) */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Earliest Start (IST)</label>
              <input
                type="datetime-local"
                required
                value={formData.earliest_start || ''}
                onChange={(e) => setFormData({ ...formData, earliest_start: e.target.value })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-semibold"
              />
            </div>

            {/* Latest End (IST) */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Latest End (IST)</label>
              <input
                type="datetime-local"
                required
                value={formData.latest_end || ''}
                onChange={(e) => setFormData({ ...formData, latest_end: e.target.value })}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-mono font-semibold"
              />
            </div>
          </div>

          {/* Resources */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Required Machinery & Teams (comma-separated)
            </label>
            <input
              type="text"
              value={resourceInput}
              onChange={(e) => setResourceInput(e.target.value)}
              placeholder="e.g. Track Tamper TTM-401, Tower Wagon TW-3, S&T Testing Crew"
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800"
            />
          </div>

          {/* Isolation Requirement */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Isolation Requirement</label>
            <select
              value={formData.isolation_requirement || 'None'}
              onChange={(e) => setFormData({ ...formData, isolation_requirement: e.target.value })}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-navy-800 font-semibold"
            >
              <option value="None">None (Live Track Proximity)</option>
              <option value="Power Block (OHE)">Power Block (OHE 25kV De-energization)</option>
              <option value="Traffic Block">Traffic Block (Full Line Closure)</option>
              <option value="Integrated Mega Block">Integrated Mega Block (Power + Traffic)</option>
            </select>
          </div>

          {/* Block Sharing Toggle */}
          <div className="flex items-center gap-2 pt-2">
            <input
              type="checkbox"
              id="block_shared_allowed"
              checked={formData.block_shared_allowed !== false}
              onChange={(e) => setFormData({ ...formData, block_shared_allowed: e.target.checked })}
              className="w-4 h-4 rounded border-slate-300 text-navy-800 focus:ring-navy-800 bg-slate-50"
            />
            <label htmlFor="block_shared_allowed" className="text-xs font-medium text-slate-700">
              Allow optimizer to bundle this request into a shared corridor block with compatible departments
            </label>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-bold rounded-xl text-slate-600 hover:bg-slate-100 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 text-xs font-bold rounded-xl bg-navy-800 hover:bg-navy-900 text-white shadow-md transition disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save & Confirm Record'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
