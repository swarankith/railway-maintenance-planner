import React from 'react';
import {
  Train,
  FileSpreadsheet,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  FileText,
  Clock,
  LogOut,
  UserCheck,
  History,
} from 'lucide-react';
import { ActiveTab, User } from '../types';

interface NavbarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  requestsCount: number;
  conflictsCount: number;
  needsReviewCount: number;
  hasSchedule: boolean;
  currentUser: User | null;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  requestsCount,
  conflictsCount,
  needsReviewCount,
  hasSchedule,
  currentUser,
  onLogout,
}) => {
  return (
    <header className="bg-gradient-to-r from-saffron-500 via-saffron-600 to-amber-600 text-white shadow-xl sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          {/* Brand Logo & Name */}
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-navy-800 text-white rounded-2xl shadow-md border border-white/20">
              <Train className="w-6 h-6 sm:w-7 sm:h-7 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-lg sm:text-2xl tracking-tight text-white drop-shadow">
                  RailBlock AI
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-navy-900/40 text-white border border-white/30 backdrop-blur-sm">
                  Phase 2.0
                </span>
              </div>
              <p className="text-[11px] sm:text-xs font-semibold text-white/90 tracking-wide hidden sm:block">
                Indian Railways Decision-Support & Deterministic Bundling
              </p>
            </div>
          </div>

          {/* Right Status & User Badges */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* User Profile Badge */}
            {currentUser && (
              <div className="flex items-center gap-2 bg-navy-950/80 px-3 py-1.5 rounded-xl border border-white/20 shadow-sm backdrop-blur-md">
                <UserCheck className="w-4 h-4 text-saffron-400" />
                <div className="text-left">
                  <div className="text-xs font-bold text-white leading-tight">
                    {currentUser.username}
                  </div>
                  <div className="text-[9px] font-semibold text-saffron-300 uppercase tracking-wider">
                    {currentUser.role}
                  </div>
                </div>
              </div>
            )}

            {/* Logout Button */}
            {currentUser && (
              <button
                onClick={onLogout}
                title="Sign Out"
                className="p-2 bg-white/20 hover:bg-white/30 text-white rounded-xl transition-all border border-white/20"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 sm:space-x-2 overflow-x-auto pb-2 scrollbar-none">
          <button
            onClick={() => setActiveTab('ingest')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'ingest'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Document Ingestion</span>
          </button>

          <button
            onClick={() => setActiveTab('requests')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'requests'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Requests Pool</span>
            {requestsCount > 0 && (
              <span className="ml-1 text-[10px] px-2 py-0.5 rounded-full font-extrabold bg-white text-navy-900 shadow-sm">
                {requestsCount}
              </span>
            )}
            {needsReviewCount > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-extrabold bg-rose-600 text-white animate-pulse">
                {needsReviewCount} Review
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('conflicts')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'conflicts'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            <span>Conflict Matrix</span>
            {conflictsCount > 0 && (
              <span className="ml-1 text-[10px] px-2 py-0.5 rounded-full font-extrabold bg-rose-600 text-white">
                {conflictsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('gantt')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'gantt'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <Calendar className="w-4 h-4" />
            <span>Corridor Timeline & Gantt</span>
            {hasSchedule && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('approval')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'approval'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Planner Approval Hub</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap ${
              activeTab === 'history'
                ? 'bg-navy-900 text-white shadow-lg border border-white/30'
                : 'text-white/80 hover:bg-white/10 hover:text-white'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Audit History Portal</span>
          </button>
        </nav>
      </div>
    </header>
  );
};
