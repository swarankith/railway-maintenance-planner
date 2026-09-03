import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { UploadModal } from './components/UploadModal';
import { RequestsTable } from './components/RequestsTable';
import { ConflictsView } from './components/ConflictsView';
import { GanttChart } from './components/GanttChart';
import { BlockDetailModal } from './components/BlockDetailModal';
import { ApprovalHub } from './components/ApprovalHub';
import { EditRequestModal } from './components/EditRequestModal';
import { ApprovalHistoryPortal } from './components/ApprovalHistoryPortal';
import { LoginView } from './components/LoginView';
import {
  MaintenanceRequest,
  ConflictDetail,
  SchedulePlan,
  MaintenanceBlock,
  ActiveTab,
  User,
} from './types';
import {
  fetchRequests,
  checkConflicts,
  optimizeSchedule,
  createRequest,
  updateRequest,
  getAuthToken,
  getStoredUser,
  clearAuthToken,
  fetchMe,
} from './services/api';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [activeTab, setActiveTab] = useState<ActiveTab>('ingest');
  const [requests, setRequests] = useState<MaintenanceRequest[]>([]);
  const [conflicts, setConflicts] = useState<ConflictDetail[]>([]);
  const [schedulePlan, setSchedulePlan] = useState<SchedulePlan | null>(null);

  const [selectedBlock, setSelectedBlock] = useState<MaintenanceBlock | null>(null);
  const [isBlockModalOpen, setIsBlockModalOpen] = useState(false);

  const [editingRequest, setEditingRequest] = useState<Partial<MaintenanceRequest> | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isNewRequest, setIsNewRequest] = useState(false);

  const [loading, setLoading] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isCheckingConflicts, setIsCheckingConflicts] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Check auth session on load
  useEffect(() => {
    const token = getAuthToken();
    const stored = getStoredUser();
    if (token && stored) {
      setCurrentUser(stored);
      fetchMe()
        .then((user) => setCurrentUser(user))
        .catch(() => {
          clearAuthToken();
          setCurrentUser(null);
        })
        .finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, []);

  const loadAllData = async () => {
    if (!getAuthToken()) return;
    setLoading(true);
    try {
      const reqList = await fetchRequests();
      setRequests(reqList);
    } catch (err: any) {
      if (err.message.includes('Session expired') || err.message.includes('Authentication required')) {
        clearAuthToken();
        setCurrentUser(null);
      } else {
        showToast(err.message || 'Failed to load requests', 'error');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      loadAllData();
    }
  }, [currentUser]);

  const handleLoginSuccess = (user: User) => {
    setCurrentUser(user);
    showToast(`Welcome back, ${user.username} (${user.role})!`, 'success');
  };

  const handleLogout = () => {
    clearAuthToken();
    setCurrentUser(null);
    showToast('Logged out successfully.', 'info');
  };

  const handleTriggerConflictCheck = async () => {
    setIsCheckingConflicts(true);
    try {
      const result = await checkConflicts();
      setConflicts(result);
      setActiveTab('conflicts');
      showToast(`Detected ${result.length} interaction(s) in matrix.`, 'info');
    } catch (err: any) {
      showToast(err.message || 'Conflict check failed', 'error');
    } finally {
      setIsCheckingConflicts(false);
    }
  };

  const handleTriggerOptimization = async () => {
    setIsOptimizing(true);
    try {
      const plan = await optimizeSchedule();
      setSchedulePlan(plan);
      await loadAllData();
      setActiveTab('gantt');
      showToast('Optimization complete! Bundled blocks generated with Deterministic Engine.', 'success');
    } catch (err: any) {
      showToast(err.message || 'Optimization failed', 'error');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleSaveRequest = async (data: Partial<MaintenanceRequest>) => {
    if (isNewRequest) {
      await createRequest(data);
      showToast('Request created successfully', 'success');
    } else if (data.request_id) {
      await updateRequest(data.request_id, data);
      showToast(`Request ${data.request_id} updated`, 'success');
    }
    await loadAllData();
  };

  const openEditModal = (req: MaintenanceRequest) => {
    setEditingRequest(req);
    setIsNewRequest(false);
    setIsEditModalOpen(true);
  };

  const openNewRequestModal = () => {
    setEditingRequest(null);
    setIsNewRequest(true);
    setIsEditModalOpen(true);
  };

  const openBlockModal = (block: MaintenanceBlock) => {
    setSelectedBlock(block);
    setIsBlockModalOpen(true);
  };

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center text-slate-600 font-semibold text-sm">
        Initializing RailBlock AI Portal...
      </div>
    );
  }

  // If not logged in, show Login Screen
  if (!currentUser) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  const needsReviewCount = requests.filter((r) => r.status === 'Needs-Review').length;

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 flex flex-col selection:bg-saffron-500 selection:text-white">
      {/* Header Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        requestsCount={requests.length}
        conflictsCount={conflicts.length}
        needsReviewCount={needsReviewCount}
        hasSchedule={schedulePlan !== null}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div
            className={`px-4 py-3 rounded-2xl shadow-2xl border text-xs font-bold backdrop-blur-md ${
              toast.type === 'success'
                ? 'bg-emerald-900/90 text-emerald-200 border-emerald-500/50 shadow-emerald-900/20'
                : toast.type === 'error'
                ? 'bg-rose-900/90 text-rose-200 border-rose-500/50 shadow-rose-900/20'
                : 'bg-navy-950/90 text-saffron-300 border-saffron-500/40 shadow-navy-950/30'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {activeTab === 'ingest' && (
          <UploadModal
            onIngestSuccess={loadAllData}
            onEditRequest={openEditModal}
            setActiveTab={setActiveTab}
            requests={requests}
          />
        )}

        {activeTab === 'requests' && (
          <RequestsTable
            requests={requests}
            onRefresh={loadAllData}
            onEdit={openEditModal}
            onAddNew={openNewRequestModal}
            onRunOptimization={handleTriggerOptimization}
            onCheckConflicts={handleTriggerConflictCheck}
            isOptimizing={isOptimizing}
            isCheckingConflicts={isCheckingConflicts}
          />
        )}

        {activeTab === 'conflicts' && (
          <ConflictsView
            conflicts={conflicts}
            onTriggerOptimization={handleTriggerOptimization}
            setActiveTab={setActiveTab}
            isOptimizing={isOptimizing}
          />
        )}

        {activeTab === 'gantt' && (
          <GanttChart
            schedulePlan={schedulePlan}
            onSelectBlock={openBlockModal}
            setActiveTab={setActiveTab}
          />
        )}

        {activeTab === 'approval' && (
          <ApprovalHub
            schedulePlan={schedulePlan}
            onPlanStatusChange={(updated) => setSchedulePlan(updated)}
            setActiveTab={setActiveTab}
          />
        )}

        {activeTab === 'history' && <ApprovalHistoryPortal />}
      </main>

      {/* Modals */}
      <EditRequestModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSave={handleSaveRequest}
        request={editingRequest}
        isNew={isNewRequest}
      />

      <BlockDetailModal
        isOpen={isBlockModalOpen}
        onClose={() => setIsBlockModalOpen(false)}
        block={selectedBlock}
      />
    </div>
  );
};
