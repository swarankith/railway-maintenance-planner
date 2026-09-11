import React, { useState } from 'react';
import {
  Search,
  RefreshCw,
  Plus,
  Play,
  AlertTriangle,
  Edit2,
  Trash2,
  CheckCircle,
  FileSpreadsheet,
  Download,
} from 'lucide-react';
import { MaintenanceRequest, RequestStatus } from '../types';
import {
  deleteRequest,
  confirmRequest,
  downloadExport,
  bulkDeleteRequests,
  clearAllRequests,
} from '../services/api';

interface RequestsTableProps {
  requests: MaintenanceRequest[];
  onRefresh: () => void;
  onEdit: (req: MaintenanceRequest) => void;
  onAddNew: () => void;
  onRunOptimization: () => void;
  onCheckConflicts: () => void;
  isOptimizing: boolean;
  isCheckingConflicts: boolean;
}

export const RequestsTable: React.FC<RequestsTableProps> = ({
  requests,
  onRefresh,
  onEdit,
  onAddNew,
  onRunOptimization,
  onCheckConflicts,
  isOptimizing,
  isCheckingConflicts,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedPriority, setSelectedPriority] = useState<string>('ALL');
  const [isExporting, setIsExporting] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [bulkNotice, setBulkNotice] = useState<string | null>(null);

  const handleExport = async (format: 'excel' | 'pdf') => {
    setIsExporting(format);
    try {
      await downloadExport('requests', format);
    } catch (err: any) {
      alert(err.message || 'Export failed');
    } finally {
      setIsExporting(null);
    }
  };

  const filteredRequests = requests.filter((r) => {
    const matchesSearch =
      r.request_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.application_id && r.application_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
      r.corridor.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.work_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.asset.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesDept = selectedDept === 'ALL' || r.department === selectedDept;
    const matchesStatus = selectedStatus === 'ALL' || r.status === selectedStatus;
    const matchesPriority = selectedPriority === 'ALL' || r.priority.toString() === selectedPriority;

    return matchesSearch && matchesDept && matchesStatus && matchesPriority;
  });

  const allFilteredIds = filteredRequests.map((r) => r.request_id);
  const isAllSelected =
    allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedIds.includes(id));

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allFilteredIds.includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...allFilteredIds])));
    }
  };

  const toggleSelectOne = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // FIX: use res.deleted and res.skipped (matches backend BulkDeleteResponse)
  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `Are you sure you want to delete ${selectedIds.length} selected maintenance request(s)?`
      )
    ) {
      return;
    }

    setIsBulkDeleting(true);
    setBulkNotice(null);
    try {
      const res = await bulkDeleteRequests(selectedIds);
      let msg = `Deleted ${res.deleted} request(s).`;
      if (res.skipped && res.skipped.length > 0) {
        msg += ` Skipped ${res.skipped.length} request(s) currently locked in active cycles.`;
      }
      setBulkNotice(msg);
      setSelectedIds([]);
      onRefresh();
      setTimeout(() => setBulkNotice(null), 5000);
    } catch (err: any) {
      alert(err.message || 'Bulk delete failed');
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const getPriorityBadge = (p: number) => {
    switch (p) {
      case 1:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-black bg-rose-100 text-rose-800 border border-rose-300">
            P1 — Emergency
          </span>
        );
      case 2:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
            P2 — High Urgent
          </span>
        );
      case 3:
      default:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-navy-50 text-navy-800 border border-navy-200">
            P3 — Normal
          </span>
        );
    }
  };

  const getStatusBadge = (st: RequestStatus) => {
    switch (st) {
      case 'Needs-Review':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300">
            Needs-Review
          </span>
        );
      case 'Confirmed':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            Confirmed
          </span>
        );
      case 'Optimized':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            Optimized
          </span>
        );
      case 'Approved':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-300">
            Approved
          </span>
        );
      case 'Deferred':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
            Deferred
          </span>
        );
      case 'Manual Review':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-300">
            Manual Review
          </span>
        );
      case 'Isolated-Emergency':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-black bg-rose-600 text-white animate-pulse">
            Isolated-Emergency
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {st}
          </span>
        );
    }
  };

  const handleDelete = async (id: string) => {
    if (window.confirm(`Delete request ${id}?`)) {
      await deleteRequest(id);
      setSelectedIds((prev) => prev.filter((i) => i !== id));
      onRefresh();
    }
  };

  const handleConfirm = async (id: string) => {
    await confirmRequest(id);
    onRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-navy-950 flex items-center gap-2">
            <FileSpreadsheet className="w-6 h-6 text-saffron-600" />
            <span>Maintenance Work Request Pool</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Verified requests ready for conflict validation and deterministic multi-department bundling
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {selectedIds.length > 0 && (
            <button
              onClick={handleBulkDelete}
              disabled={isBulkDeleting}
              className="px-3.5 py-2.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all animate-in fade-in duration-200"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>{isBulkDeleting ? 'Deleting...' : `Delete Selected (${selectedIds.length})`}</span>
            </button>
          )}

          {requests.length > 0 && selectedIds.length === 0 && (
            <button
              onClick={async () => {
                if (window.confirm(`Are you sure you want to clear all ${requests.length} maintenance requests in the pool?`)) {
                  await clearAllRequests();
                  onRefresh();
                }
              }}
              className="px-3.5 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all"
              title="Clear all requests in pool"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Pool</span>
            </button>
          )}

          <button
            onClick={() => handleExport('excel')}
            disabled={isExporting !== null}
            className="px-3.5 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isExporting === 'excel' ? 'Exporting...' : 'Export Excel'}</span>
          </button>

          <button
            onClick={() => handleExport('pdf')}
            disabled={isExporting !== null}
            className="px-3.5 py-2.5 bg-rose-700 hover:bg-rose-800 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isExporting === 'pdf' ? 'Exporting...' : 'Export PDF'}</span>
          </button>

          <button
            onClick={onAddNew}
            className="px-3.5 py-2.5 bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>New Request</span>
          </button>

          <button
            onClick={onCheckConflicts}
            disabled={isCheckingConflicts || requests.length === 0}
            className="px-3.5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-1.5 transition-all disabled:opacity-50"
          >
            <AlertTriangle className="w-4 h-4" />
            <span>{isCheckingConflicts ? 'Checking...' : 'Check Conflicts'}</span>
          </button>

          <button
            onClick={onRunOptimization}
            disabled={isOptimizing || requests.length === 0}
            className="px-4 py-2.5 bg-saffron-500 hover:bg-saffron-600 text-navy-950 text-xs font-black rounded-xl shadow-md flex items-center gap-1.5 transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-navy-950" />
            <span>{isOptimizing ? 'Optimizing...' : 'Run Bundling Engine'}</span>
          </button>

          <button
            onClick={onRefresh}
            title="Refresh Pool"
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl border border-slate-200 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {bulkNotice && (
        <div className="p-3 bg-navy-900 text-white text-xs font-semibold rounded-xl border border-navy-700 flex items-center justify-between">
          <span>{bulkNotice}</span>
          <button
            onClick={() => setBulkNotice(null)}
            className="text-slate-300 hover:text-white font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}

      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-[240px] relative">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by Request ID, App ID, Corridor, Asset, or Work..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-navy-800"
          />
        </div>

        <select
          value={selectedDept}
          onChange={(e) => setSelectedDept(e.target.value)}
          className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none font-semibold"
        >
          <option value="ALL">All Departments</option>
          <option value="Engineering">Engineering</option>
          <option value="Electrical">Electrical</option>
          <option value="S&T">S&T</option>
          <option value="Operations">Operations</option>
        </select>

        <select
          value={selectedPriority}
          onChange={(e) => setSelectedPriority(e.target.value)}
          className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none font-semibold"
        >
          <option value="ALL">All Priorities</option>
          <option value="1">P1 — Emergency</option>
          <option value="2">P2 — High Urgent</option>
          <option value="3">P3 — Normal</option>
        </select>

        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
          className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none font-semibold"
        >
          <option value="ALL">All Statuses</option>
          <option value="Needs-Review">Needs-Review</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Optimized">Optimized</option>
          <option value="Approved">Approved</option>
          <option value="Deferred">Deferred</option>
          <option value="Manual Review">Manual Review</option>
          <option value="Isolated-Emergency">Isolated-Emergency</option>
        </select>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-navy-800 text-white font-bold uppercase tracking-wider text-[11px]">
                <th className="py-3.5 px-4 w-10">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={toggleSelectAll}
                    className="rounded border-slate-400 text-saffron-600 focus:ring-saffron-500 cursor-pointer"
                  />
                </th>
                <th className="py-3.5 px-4">Application ID</th>
                <th className="py-3.5 px-4">Request ID</th>
                <th className="py-3.5 px-4">Department & Asset</th>
                <th className="py-3.5 px-4">Corridor & KM Span</th>
                <th className="py-3.5 px-4">Work Nature</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Required Window</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-400 font-medium">
                    No matching maintenance requests found in database.
                  </td>
                </tr>
              ) : (
                filteredRequests.map((req) => {
                  const isSelected = selectedIds.includes(req.request_id);
                  return (
                    <tr
                      key={req.request_id}
                      className={`hover:bg-saffron-50/40 transition-colors ${
                        isSelected ? 'bg-saffron-50/60' : req.status === 'Needs-Review' ? 'bg-amber-50/30' : ''
                      }`}
                    >
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectOne(req.request_id)}
                          className="rounded border-slate-300 text-saffron-600 focus:ring-saffron-500 cursor-pointer"
                        />
                      </td>

                      <td className="py-3 px-4 font-mono font-bold text-navy-800">
                        {req.application_id || 'APP-LEGACY'}
                      </td>

                      <td className="py-3 px-4 font-bold text-slate-900">
                        {req.request_id}
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900">{req.department}</div>
                        <div className="text-[11px] text-slate-500 truncate max-w-[140px]">
                          {req.asset}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-bold text-navy-900">{req.corridor}</div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          KM {req.km_start.toFixed(1)} – {req.km_end.toFixed(1)}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-900 max-w-[180px] truncate" title={req.work_type}>
                          {req.work_type}
                        </div>
                        {req.required_resources.length > 0 && (
                          <div className="text-[10px] text-slate-400 truncate max-w-[180px]">
                            {req.required_resources.join(', ')}
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-4">{getPriorityBadge(req.priority)}</td>

                      <td className="py-3 px-4">
                        <div className="font-mono text-slate-900 font-semibold">
                          {new Date(req.earliest_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} –{' '}
                          {new Date(req.latest_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {req.duration_minutes} mins
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        {getStatusBadge(req.status)}
                        {req.missing_fields && req.missing_fields.length > 0 && (
                          <div className="text-[10px] text-amber-700 font-semibold mt-0.5">
                            Missing: {req.missing_fields.join(', ')}
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {req.status === 'Needs-Review' && (
                            <button
                              onClick={() => handleConfirm(req.request_id)}
                              title="Quick Confirm"
                              className="p-1.5 text-emerald-700 hover:bg-emerald-50 rounded-lg transition-all"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => onEdit(req)}
                            title="Edit Request"
                            className="p-1.5 text-navy-800 hover:bg-navy-50 rounded-lg transition-all"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(req.request_id)}
                            title="Delete Request"
                            className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
