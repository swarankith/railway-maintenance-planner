import {
  MaintenanceRequest,
  ConflictDetail,
  SchedulePlan,
  IngestResponse,
  ApprovalAudit,
} from '../types';

const API_BASE = (import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/$/, '') : '') + '/api/v1';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function ingestDocument(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Document ingestion failed');
  }
  return res.json();
}

export async function fetchRequests(filters?: {
  corridor?: string;
  department?: string;
  status?: string;
  priority?: number;
}): Promise<MaintenanceRequest[]> {
  const params = new URLSearchParams();
  if (filters?.corridor) params.append('corridor', filters.corridor);
  if (filters?.department) params.append('department', filters.department);
  if (filters?.status) params.append('status', filters.status);
  if (filters?.priority) params.append('priority', filters.priority.toString());

  const url = `${API_BASE}/requests${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch requests');
  return res.json();
}

export async function createRequest(payload: Partial<MaintenanceRequest>): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create request');
  }
  return res.json();
}

export async function updateRequest(id: string, payload: Partial<MaintenanceRequest>): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to update request');
  }
  return res.json();
}

export async function confirmRequest(id: string): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests/${id}/confirm`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to confirm request');
  }
  return res.json();
}

export async function deleteRequest(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/requests/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete request');
  return res.json();
}

export async function clearAllRequests(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/requests`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to clear requests');
  return res.json();
}

export async function checkConflicts(requestIds?: string[]): Promise<ConflictDetail[]> {
  const res = await fetch(`${API_BASE}/conflicts/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestIds || null),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to check conflicts');
  }
  return res.json();
}

export async function optimizeSchedule(requestIds?: string[]): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestIds || null),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Optimization failed');
  }
  return res.json();
}

export async function fetchSchedule(id: string): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/${id}`);
  if (!res.ok) throw new Error('Failed to fetch schedule');
  return res.json();
}

export async function fetchSchedules(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/schedules`);
  if (!res.ok) throw new Error('Failed to fetch schedules');
  return res.json();
}

export async function approveSchedule(
  id: string,
  payload: { role: string; user_name: string; notes?: string }
): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to approve schedule');
  }
  return res.json();
}

export async function rejectSchedule(
  id: string,
  payload: { role: string; user_name: string; reason: string }
): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/${id}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to reject schedule');
  }
  return res.json();
}

export async function fetchAudits(id: string): Promise<ApprovalAudit[]> {
  const res = await fetch(`${API_BASE}/schedules/${id}/audit`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}
