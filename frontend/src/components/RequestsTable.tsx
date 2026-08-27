import React, { useState } from 'react';
import {
  Search,
  Filter,
  Plus,
  Trash2,
  Edit3,
  CheckCircle2,
  AlertTriangle,
  Play,
  Layers,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { MaintenanceRequest, Department, ActiveTab } from '../types';
import { deleteRequest, clearAllRequests } from '../services/api';

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
  const [deptFilter, setDeptFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');

  const filtered = requests.filter((r) => {
    const matchesSearch =
      r.request_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.corridor.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.work_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.asset.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesDept = deptFilter === 'ALL' || r.department === deptFilter;
    const matchesStatus = statusFilter === 'ALL' || r.status === statusFilter;
    const matchesPriority = priorityFilter === 'ALL' || r.priority.toString() === priorityFilter;

    return matchesSearch && matchesDept && matchesStatus && matchesPriority;
  });

  const handleDelete = async (id: string) => {
    if (confirm(`Are you sure you want to delete ${id}?`)) {
      await deleteRequest(id);
      onRefresh();
    }
  };

  const handleClearAll = async () => {
    if (confirm('Are you sure you want to clear all requests in the database?')) {
      await clearAllRequests();
      onRefresh();
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900/60 p-4 rounded-2xl border border-slate-800">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by ID, corridor, work type, or asset..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-9 pr-4 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Quick Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          <button
            onClick={onAddNew}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition shadow-sm"
          >
            <Plus className="w-4 h-4 text-cyan-400" />
            <span>Add Request</span>
          </button>

          <button
            onClick={onCheckConflicts}
            disabled={isCheckingConflicts || requests.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-semibold border border-rose-500/30 transition disabled:opacity-50"
          >
            <AlertTriangle className="w-4 h-4" />
            <span>{isCheckingConflicts ? 'Analyzing...' : 'Check Conflicts'}</span>
          </button>

          <button
            onClick={onRunOptimization}
            disabled={isOptimizing || requests.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 transition disabled:opacity-50"
          >
            {isOptimizing ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4 fill-white" />
            )}
            <span>{isOptimizing ? 'Optimizing...' : 'Run CP-SAT Optimizer'}</span>
          </button>

          {requests.length > 0 && (
            <button
              onClick={handleClearAll}
              className="p-2 rounded-xl bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 border border-slate-700 transition"
              title="Clear all requests"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Dropdowns */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <div className="flex items-center gap-1 text-slate-400 font-semibold px-2">
          <Filter className="w-3.5 h-3.5" />
          <span>Filters:</span>
        </div>

        {/* Department Filter */}
        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-cyan-500 text-xs"
        >
          <option value="ALL">All Departments</option>
          <option value="Engineering">Engineering</option>
          <option value="Electrical">Electrical (TRD)</option>
          <option value="S&T">Signal & Telecom</option>
          <option value="Operations">Operations</option>
        </select>

        {/* Priority Filter */}
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-cyan-500 text-xs"
        >
          <option value="ALL">All Priorities</option>
          <option value="1">P1 - Critical Safety</option>
          <option value="2">P2 - High Urgency</option>
          <option value="3">P3 - Standard</option>
          <option value="4">P4 - Routine</option>
          <option value="5">P5 - Deferrable</option>
        </select>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-cyan-500 text-xs"
        >
          <option value="ALL">All Statuses</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Needs-Review">Needs-Review</option>
          <option value="Optimized">Optimized</option>
          <option value="Approved">Approved</option>
          <option value="Ingested">Ingested</option>
        </select>

        <span className="ml-auto text-slate-500 text-xs font-mono">
          Showing {filtered.length} of {requests.length} requests
        </span>
      </div>

      {/* Main Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 uppercase text-[10px] text-slate-400 font-bold border-b border-slate-800">
              <tr>
                <th className="px-4 py-3">ID & Department</th>
                <th className="px-4 py-3">Corridor & KM Span</th>
                <th className="px-4 py-3">Work Type & Asset</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Duration & Window (IST)</th>
                <th className="px-4 py-3">Machinery / Isolation</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((req) => (
                <tr key={req.request_id} className="hover:bg-slate-800/40 transition">
                  {/* ID & Dept */}
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

                  {/* Corridor & KM */}
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-100">{req.corridor}</div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      KM {req.km_start.toFixed(1)} - {req.km_end.toFixed(1)}
                    </div>
                  </td>

                  {/* Work Type & Asset */}
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-200">{req.work_type}</div>
                    <div className="text-[11px] text-slate-400">{req.asset}</div>
                  </td>

                  {/* Priority */}
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        req.priority === 1
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                          : req.priority === 2
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : req.priority === 3
                          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      P{req.priority}
                    </span>
                  </td>

                  {/* Duration & Window */}
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-200 font-mono">
                      {req.duration_minutes} min ({Math.round((req.duration_minutes / 60) * 10) / 10}h)
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {new Date(req.earliest_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
                      {new Date(req.latest_end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} IST
                    </div>
                  </td>

                  {/* Machinery / Isolation */}
                  <td className="px-4 py-3">
                    <div className="text-slate-300 text-[11px]">
                      {req.required_resources && req.required_resources.length > 0
                        ? req.required_resources.join(', ')
                        : 'Standard Gang'}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {req.isolation_requirement || 'No Isolation'}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        req.status === 'Needs-Review'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : req.status === 'Optimized'
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                          : req.status === 'Approved'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : 'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}
                    >
                      {req.status}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => onEdit(req)}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 transition"
                        title="Edit Request"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(req.request_id)}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition"
                        title="Delete Request"
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

        {filtered.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-xs">
            No maintenance requests match the current filters.
          </div>
        )}
      </div>
    </div>
  );
};
