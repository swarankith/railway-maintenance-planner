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
import {
  MaintenanceRequest,
  TrainMovement,
  ConflictDetail,
  SchedulePlan,
  MaintenanceBlock,
  ActiveTab,
} from './types';
import {
  fetchRequests,
  fetchTrains,
  checkConflicts,
  optimizeSchedule,
  createRequest,
  updateRequest,
} from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('ingest');
  const [requests, setRequests] = useState<MaintenanceRequest[]>([]);
  const [trains, setTrains] = useState<TrainMovement[]>([]);
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

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [reqList, trainList] = await Promise.all([
        fetchRequests().catch(() => []),
        fetchTrains().catch(() => []),
      ]);
      setRequests(reqList);
      setTrains(trainList);
    } catch (err: any) {
      showToast(err.message || 'Failed to load initial data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

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
            trains={trains}
            onTriggerOptimization={handleTriggerOptimization}
            isOptimizing={isOptimizing}
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
            trains={trains}
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
