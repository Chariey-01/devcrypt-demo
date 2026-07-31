// Mirrors the JSON shape returned by GET /missions/status (app/blueprints/missions.py's
// status() and its _serialize_* helpers) plus the smaller response shapes from the other
// player-facing endpoints. Kept as plain interfaces, not runtime validation -- the backend is
// the source of truth and this is a same-repo, same-deploy contract, not a public API.

export interface TimelineEntry {
  mission_id: number;
  title: string;
  status: "passed" | "overridden" | "soft_locked" | "current" | "not_started";
}

export interface TeamSummary {
  name: string;
  score: number;
  integrity: number;
  hints_used: number;
  hints_remaining: number;
  mcq_points: number;
  coding_points: number;
  cipher_points: number;
  hint_points: number;
  time_bonus_points: number;
}

export interface CryptogramWord {
  mission_id: number;
  title: string;
  tagline: string | null;
  display: string;
  revealed: boolean[];
  complete: boolean;
}

export interface FragmentEntry {
  mission_id: number;
  value: string;
}

export interface EvidenceFile {
  id: number;
  label: string;
  file_type: string;
  content: string;
  has_binary: boolean;
  mime_type: string | null;
  filename: string | null;
}

export interface KnowledgeOption {
  id: number;
  option_text: string;
}

export interface KnowledgeQuestion {
  id: number;
  question_text: string;
  options: KnowledgeOption[];
  answered: boolean;
  was_correct: boolean | null;
}

export type GradingMode = "manual_review" | "auto" | "pytest";

export interface Challenge {
  type: string;
  prompt: string;
  hint_text: string | null;
  hints_revealed: string[];
  hints_taken: number;
  hints_available: number;
  grading_mode: GradingMode;
  // Present only when grading_mode is "auto" | "pytest".
  title?: string | null;
  language?: string | null;
  function_signature?: string | null;
  starter_code?: string | null;
  last_submitted_code?: string | null;
  max_attempts?: number | null;
  attempts_used?: number;
}

export interface Mission {
  id: number;
  title: string;
  tagline: string | null;
  narrative: string;
  time_limit: number | null;
  started_at: string | null;
  status: string;
  attempts: number;
  booth_score: number;
  penalty_remaining: number | null;
  submitted_at: string | null;
  elapsed_seconds: number | null;
  time_remaining_frozen: number | null;
  submission_status: "on_time" | "overtime" | null;
  grading_status: "pending_review" | "graded" | null;
  evidence_files: EvidenceFile[];
  challenge: Challenge | null;
  pending_review: boolean;
  knowledge_questions: KnowledgeQuestion[];
  knowledge_check_complete: boolean;
}

export interface MissionStatus {
  timeline: TimelineEntry[];
  next_mission: { mission_id: number; title: string } | null;
  booths_completed: number;
  booths_total: number;
  event_status: string;
  soft_lock_min_attempts: number;
  broadcast: { message: string; at: string } | null;
  team: TeamSummary;
  cryptogram: CryptogramWord[];
  fragments: FragmentEntry[];
  finished: boolean;
  mission: Mission | null;
}

export interface GradingResultRow {
  name: string;
  visibility: "visible" | "hidden";
  passed: boolean;
  weight: number;
  failure_message: string | null;
  input_data: string | null;
  expected_output: string | null;
  actual_output: string | null;
}

export interface RunTestsResponse {
  results: GradingResultRow[];
  passed_tests: number;
  total_tests: number;
}

export interface SubmitResponse {
  correct: boolean;
  message?: string;
  error?: string;
  percent_score?: number;
  passed_tests?: number;
  total_tests?: number;
  penalty_remaining?: number;
}

export interface HintResponse {
  hint: string | null;
  hints_revealed: string[];
  hints_taken: number;
  hints_available: number;
  error?: string;
}

export interface KnowledgeAnswerResponse {
  correct?: boolean;
  message?: string;
  error?: string;
  already_answered?: boolean;
}

export interface FinalFlagVault {
  mission_id: number;
  title: string;
}

export interface FinalFlagRequirementsResponse {
  vaults?: FinalFlagVault[];
  error?: string;
}

export interface FinalFlagStatusResponse {
  status: "none" | "pending" | "confirmed";
  flag?: string;
  error?: string;
}

export interface FinalFlagSubmitResponse {
  status?: "pending" | "confirmed";
  flag?: string;
  error?: string;
  incorrect_mission_ids?: number[];
}
