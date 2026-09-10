export type Department = 'Engineering' | 'Electrical' | 'S&T' | 'Operations';

export type PriorityLevel = 1 | 2 | 3;

export type BlockType = 'Emergency' | 'Normal' | 'Corridor' | 'Rolling';

export type RequestStatus =
  | 'Ingested'
  | 'Needs-Review'
  | 'Confirmed'
  | 'Optimized'
  | 'Approved'
  | 'Deferred'
  | 'Manual Review'
  | 'Isolated-Emergency';

export type ConflictType =
  | 'HardPhysicalOverlap'
  | 'PowerDisconnectionContradiction'
  | 'ResourceContention'
  | 'TrainMovementCollision'
  | 'SpeedRestrictionConflict'
  | 'StationSignalingInterlock';

export type PlanStatus = 'Draft' | 'Approved' | 'Rejected';

export interface User {
  id: number;
  username: string;
  role: 'Chief Controller' | 'Planner' | 'Approver' | 'Operations';
}

export interface MaintenanceRequest {
  request_id: string;
  application_id?: string;
  cycle_id?: string;
  department: Department;
  corridor: string;
  km_start: number;
  km_end: number;
  earliest_start: string;
  latest_end: string;
  duration_minutes: number;
  work_type: string;
  asset: string;
  disconnection_required: boolean | null;
  priority: PriorityLevel;
  priority_reason?: string;
  block_type?: string;
  isolation_requirement?: string;
  block_shared_allowed?: boolean;
  required_resources: string[];
  dependencies: string[];
  status: RequestStatus;
  source_document: string;
  missing_fields: string[];
  validation_notes?: string;
  confidence_score?: number;
  retry_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface TrainMovement {
  train_id: string;
  train_number?: string;
  train_name?: string;
  speed_kmh?: number;
  corridor: string;
  departure_time: string;
  arrival_time: string;
  km_start: number;
  km_end: number;
  train_type: string;
  source_document?: string;
  cycle_id?: string;
}

export interface ConflictDetail {
  conflict_id: string;
  cycle_id?: string;
  conflict_type: ConflictType;
  severity: 'Hard' | 'Warning' | 'ReviewRequired';
  request_ids: string[];
  corridor?: string;
  time_overlap_start?: string;
  time_overlap_end?: string;
  km_overlap_start?: number;
  km_overlap_end?: number;
  resource_involved?: string;
  train_id_involved?: string;
  explanation: string;
  suggested_resolution: string;
}

export interface MaintenanceBlock {
  block_id: string;
  corridor: string;
  scheduled_start: string;
  scheduled_end: string;
  duration_minutes: number;
  km_start: number;
  km_end: number;
  request_ids: string[];
  departments: string[];
  resources_allocated: string[];
  isolation_applied?: string;
  utilization_score: number;
  time_saved_minutes: number;
  bundling_explanation: string;
  requests: MaintenanceRequest[];
}

export interface RequestDecision {
  request_id: string;
  application_id?: string;
  final_status: string;
  disconnection_required: boolean | null;
  priority: number;
  bundle_id?: string;
  bundle_members: string[];
  retry_count: number;
  reason: string;
  train_window_checked: boolean;
}

export interface SchedulePlan {
  schedule_id: string;
  cycle_id?: string;
  plan_name: string;
  is_recommended: boolean;
  blocks: MaintenanceBlock[];
  unassigned_requests: string[];
  infeasibility_reasons: string[];
  total_corridor_downtime_minutes: number;
  total_jobs_completed: number;
  total_jobs_requested: number;
  bundling_efficiency_percentage: number;
  summary_explanation: string;
  decisions?: RequestDecision[];
  deferred_requests?: RequestDecision[];
  manual_review_requests?: RequestDecision[];
  isolated_emergency_requests?: RequestDecision[];
  created_at: string;
  status: PlanStatus;
  approved_by?: string;
  approval_role?: string;
  approval_timestamp?: string;
  approval_notes?: string;
  alternative_plan?: SchedulePlan;
}

export interface IngestResponse {
  application_id: string;
  filename: string;
  total_extracted: number;
  confirmed_count: number;
  needs_review_count: number;
  candidate_requests: MaintenanceRequest[];
  detected_trains: TrainMovement[];
  warnings: string[];
}

export interface ApprovalAudit {
  id: number;
  schedule_id: string;
  application_id?: string;
  cycle_id?: string;
  action: 'APPROVED' | 'REJECTED' | 'DELETED';
  role: string;
  user_name: string;
  notes?: string;
  timestamp: string;
  report_url?: string;
}

export interface ApprovalHistoryItem {
  id: number;
  schedule_id: string;
  application_id: string;
  cycle_id?: string;
  action: 'APPROVED' | 'REJECTED' | 'DELETED';
  role: string;
  user_name: string;
  notes?: string;
  timestamp: string;
  report_url?: string;
  request_ids: string[];
  corridors: string[];
  total_blocks: number;
  total_jobs: number;
}

export interface BulkDeleteResponse {
  deleted_count: number;
  skipped_count: number;
  deleted_ids: string[];
  skipped_ids: string[];
  reason?: string;
}

export type ActiveTab = 'ingest' | 'requests' | 'conflicts' | 'gantt' | 'approval' | 'history';
