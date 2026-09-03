import React, { useState, useEffect } from 'react';
import {
  History,
  Download,
  Search,
  Filter,
  RefreshCw,
  Calendar,
  CheckCircle2,
  XCircle,
  FileSpreadsheet,
  FileText,
  MapPin,
  Layers,
} from 'lucide-react';
import { ApprovalHistoryItem } from '../types';
import { fetchApprovalHistory, downloadExport } from '../services/api';

export const ApprovalHistoryPortal: React.FC = () => {
  const [history, setHistory] = useState<ApprovalHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [applicationId, setApplicationId] = useState('');
  const [corridor, setCorridor] = useState('');
  const [isExporting, setIsExporting] = useState<string | null>(null);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await fetchApprovalHistory({
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        applicationId: applicationId || undefined,
        corridor: corridor || undefined,
      });
      setHistory(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleExport = async (format: 'excel' | 'pdf') => {
    setIsExporting(format);
    try {
      await downloadExport('approvals', format);
    } catch (err: any) {
      alert(err.message || 'Export failed');
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-navy-950 flex items-center gap-2">
            <History className="w-6 h-6 text-saffron-600" />
            <span>Chief Controller Audit & Approval History</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Complete immutable ledger of all approved and rejected corridor maintenance schedules
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
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
            onClick={loadHistory}
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl border border-slate-200 transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
            Application ID
          </label>
          <input
            type="text"
            placeholder="e.g. APP-2026..."
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-navy-800"
          />
        </div>

        <div>
          <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
            Corridor
          </label>
          <input
            type="text"
            placeholder="e.g. NDLS-GZB..."
            value={corridor}
            onChange={(e) => setCorridor(e.target.value)}
            className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-navy-800"
          />
        </div>

        <div>
          <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
            From Date
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-navy-800"
          />
        </div>

        <div>
          <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1">
            To Date
          </label>
          <div className="flex gap-2">
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-navy-800"
            />
            <button
              onClick={loadHistory}
              className="px-3 py-1.5 bg-navy-800 hover:bg-navy-900 text-white rounded-xl text-xs font-bold transition-all"
            >
              Filter
            </button>
          </div>
        </div>
      </div>

      {/* History Ledger Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-navy-800 text-white font-bold uppercase tracking-wider text-[11px]">
                <th className="py-3.5 px-4">Timestamp (IST)</th>
                <th className="py-3.5 px-4">Application ID</th>
                <th className="py-3.5 px-4">Schedule ID</th>
                <th className="py-3.5 px-4">Decision</th>
                <th className="py-3.5 px-4">Authority & Role</th>
                <th className="py-3.5 px-4">Scope & Corridors</th>
                <th className="py-3.5 px-4">Controller Remarks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {history.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 font-medium">
                    No approval audit history records match your search criteria.
                  </td>
                </tr>
              ) : (
                history.map((item) => (
                  <tr key={item.id} className="hover:bg-saffron-50/40 transition-colors">
                    {/* Timestamp */}
                    <td className="py-3 px-4 font-mono font-semibold text-slate-700">
                      {new Date(item.timestamp).toLocaleString([], {
                        month: 'short',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false,
                      })}
                    </td>

                    {/* Application ID */}
                    <td className="py-3 px-4 font-mono font-bold text-navy-800">
                      {item.application_id}
                    </td>

                    {/* Schedule ID */}
                    <td className="py-3 px-4 font-mono text-slate-600">
                      {item.schedule_id}
                    </td>

                    {/* Decision Badge */}
                    <td className="py-3 px-4">
                      {item.action === 'APPROVED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-black bg-emerald-100 text-emerald-800 border border-emerald-300">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>APPROVED</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-black bg-rose-100 text-rose-800 border border-rose-300">
                          <XCircle className="w-3.5 h-3.5" />
                          <span>REJECTED</span>
                        </span>
                      )}
                    </td>

                    {/* Sign-off User */}
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{item.user_name}</div>
                      <div className="text-[11px] text-slate-500 font-semibold">{item.role}</div>
                    </td>

                    {/* Corridors & Jobs */}
                    <td className="py-3 px-4">
                      <div className="font-bold text-navy-900">
                        {item.corridors.length > 0 ? item.corridors.join(', ') : 'All Corridors'}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {item.total_jobs} tasks in {item.total_blocks} synchronized blocks
                      </div>
                    </td>

                    {/* Notes */}
                    <td className="py-3 px-4 text-slate-600 max-w-[280px]">
                      {item.notes || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
