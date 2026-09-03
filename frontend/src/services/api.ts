import {
  MaintenanceRequest,
  ConflictDetail,
  SchedulePlan,
  IngestResponse,
  ApprovalAudit,
  ApprovalHistoryItem,
  User,
} from '../types';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      if (window.location.port === '8000' || window.location.port === '') {
        return '/api/v1';
      }
      return `${window.location.protocol}//${hostname}:8000/api/v1`;
    }
  }
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && !envUrl.includes('localhost') && !envUrl.includes('127.0.0.1')) {
    return envUrl.replace(/\/$/, '') + '/api/v1';
  }
  return '/api/v1';
}

const API_BASE = getApiBaseUrl();

// Token Storage Helpers
export function getAuthToken(): string | null {
  return localStorage.getItem('railway_auth_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('railway_auth_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('railway_auth_token');
  localStorage.removeItem('railway_auth_user');
}

export function getStoredUser(): User | null {
  const data = localStorage.getItem('railway_auth_user');
  try {
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User) {
  localStorage.setItem('railway_auth_user', JSON.stringify(user));
}

function getAuthHeaders(isJson: boolean = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (isJson) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Authentication Endpoints
export async function loginUser(username: string, password: string):Promise<{ access_token: string; user: User }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed. Please check credentials.');
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  setStoredUser(data.user);
  return data;
}

export async function fetchMe(): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Session expired. Please log in again.');
  return res.json();
}

// System Health
export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

// Ingestion
export async function ingestDocument(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: {
      ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
    },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Document ingestion failed');
  }
  return res.json();
}

// Requests CRUD
export async function fetchRequests(filters?: {
  corridor?: string;
  department?: string;
  status?: string;
  priority?: number;
  application_id?: string;
}): Promise<MaintenanceRequest[]> {
  const params = new URLSearchParams();
  if (filters?.corridor) params.append('corridor', filters.corridor);
  if (filters?.department) params.append('department', filters.department);
  if (filters?.status) params.append('status', filters.status);
  if (filters?.priority) params.append('priority', filters.priority.toString());
  if (filters?.application_id) params.append('application_id', filters.application_id);

  const url = `${API_BASE}/requests${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch requests');
  return res.json();
}

export async function createRequest(payload: Partial<MaintenanceRequest>): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create request');
  }
  return res.json();
}

export async function updateRequest(id: string, payload: Partial<MaintenanceRequest>): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update request');
  }
  return res.json();
}

export async function confirmRequest(id: string): Promise<MaintenanceRequest> {
  const res = await fetch(`${API_BASE}/requests/${id}/confirm`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to confirm request');
  }
  return res.json();
}

export async function deleteRequest(id: string): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/requests/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete request');
  return res.json();
}

export async function clearAllRequests(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/requests`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to clear requests');
  return res.json();
}

// Conflict Detection
export async function checkConflicts(requestIds?: string[]): Promise<ConflictDetail[]> {
  const res = await fetch(`${API_BASE}/conflicts/check`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(requestIds || null),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to check conflicts');
  }
  return res.json();
}

// Scheduling & Deterministic Optimization
export async function optimizeSchedule(requestIds?: string[]): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/optimize`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(requestIds || null),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Optimization failed');
  }
  return res.json();
}

export async function fetchSchedule(id: string): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/${id}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch schedule');
  return res.json();
}

export async function fetchSchedules(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/schedules`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch schedules');
  return res.json();
}

export async function approveSchedule(
  id: string,
  payload: { role: string; user_name: string; notes?: string }
): Promise<SchedulePlan> {
  const res = await fetch(`${API_BASE}/schedules/${id}/approve`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
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
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to reject schedule');
  }
  return res.json();
}

export async function fetchAudits(id: string): Promise<ApprovalAudit[]> {
  const res = await fetch(`${API_BASE}/schedules/${id}/audit`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

// Approval History Portal
export async function fetchApprovalHistory(filters?: {
  startDate?: string;
  endDate?: string;
  applicationId?: string;
  corridor?: string;
}): Promise<ApprovalHistoryItem[]> {
  const params = new URLSearchParams();
  if (filters?.startDate) params.append('start_date', filters.startDate);
  if (filters?.endDate) params.append('end_date', filters.endDate);
  if (filters?.applicationId) params.append('application_id', filters.applicationId);
  if (filters?.corridor) params.append('corridor', filters.corridor);

  const res = await fetch(`${API_BASE}/approvals/history?${params.toString()}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch approval history');
  return res.json();
}

// Export Endpoints (Excel / PDF Blob download helpers)
export async function downloadExport(
  type: 'requests' | 'approvals',
  format: 'excel' | 'pdf'
) {
  const url = `${API_BASE}/export/${type}?format=${format}`;
  const res = await fetch(url, {
    headers: getAuthHeaders(false),
  });
  if (!res.ok) throw new Error(`Export failed for ${type}`);
  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  const ext = format === 'excel' ? 'xlsx' : 'pdf';
  a.download = `${type}_status_${new Date().toISOString().slice(0, 10)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}
