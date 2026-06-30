// Thin client for the TOEIC demo backend (FastAPI).
// Override the base URL with NEXT_PUBLIC_API_BASE; defaults to local dev server.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface ExamSummary {
  id: number;
  title: string;
  language: string;
  exam_type: string;
  duration_minutes: number;
  is_active: boolean;
  created_at: string | null;
  question_count: number;
}

export interface QuestionOut {
  id: number;
  group_id: number | null;
  part: number | null;
  type: string;
  content: string;
  options: Record<string, string> | null;
  reference_answer: string | null;
  audio_url: string | null;
  image_url: string | null;
  difficulty: string | null;
  topic: string | null;
}

export interface GroupOut {
  id: number;
  part: number | null;
  topic: string | null;
  passage_text: string | null;
  audio_url: string | null;
  image_url: string | null;
  difficulty: string | null;
  questions: QuestionOut[];
}

export interface PartOut {
  part: number;
  part_type: string;
  question_count: number;
  audio_url: string | null;
  standalone_questions: QuestionOut[];
  groups: GroupOut[];
}

export interface ExamDetail {
  id: number;
  title: string;
  language: string;
  exam_type: string;
  duration_minutes: number;
  created_at: string | null;
  total_questions: number;
  parts: PartOut[];
}

export interface PartStats {
  part: number;
  type: string;
  approved_count: number;
  needed_count: number;
  is_sufficient: boolean;
}

export interface BankStats {
  question_counts: Record<string, Record<string, number>>;
  group_counts: Record<string, Record<string, number>>;
  blueprint_sufficiency: PartStats[];
}

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("auth_token");
  }
  return null;
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("auth_token", token);
  }
}

export function clearToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("auth_token");
  }
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearToken();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function loginRequest(username: string, password: string): Promise<{ access_token: string }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  );
}

export async function getBankStats(examType?: string): Promise<BankStats> {
  const url = examType
    ? `${API_BASE}/api/v1/bank/stats?exam_type=${examType}`
    : `${API_BASE}/api/v1/bank/stats`;
  return jsonOrThrow(
    await fetch(url, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

export async function listExams(): Promise<ExamSummary[]> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams`, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

export async function releaseExam(id: number): Promise<ExamDetail> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${id}/release`, {
      method: "POST",
      headers: {
        ...authHeaders(),
      },
    }),
  );
}

export async function retireExam(id: number): Promise<ExamDetail> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${id}/retire`, {
      method: "POST",
      headers: {
        ...authHeaders(),
      },
    }),
  );
}

export async function updateExam(
  id: number,
  payload: { title?: string; duration_minutes?: number },
): Promise<ExamDetail> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(payload),
    }),
  );
}

export async function generateExam(title: string, examType?: string, seed?: number): Promise<ExamSummary> {
  const body: Record<string, any> = { title };
  if (examType !== undefined) {
    body.exam_type = examType;
  }
  if (seed !== undefined) {
    body.seed = seed;
  }
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(body),
    }),
  );
}

export async function getExam(
  id: number | string,
  includeAnswers = false,
): Promise<ExamDetail> {
  const qs = includeAnswers ? "?include_answers=true" : "";
  const headers = includeAnswers ? { ...authHeaders() } : {};
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${id}${qs}`, {
      cache: "no-store",
      headers,
    }),
  );
}

// Resolve a (possibly bare-filename) audio_url into a playable URL via the
// backend's optional /audio static mount.
export function audioSrc(audioUrl: string | null): string | null {
  if (!audioUrl) return null;
  if (audioUrl.startsWith("http")) return audioUrl;
  if (audioUrl.startsWith("/")) return `${API_BASE}${audioUrl}`;
  return `${API_BASE}/audio/${encodeURIComponent(audioUrl)}`;
}

// Resolve an image_url. Backend stores extracted images as "/static/img/...".
export function imageSrc(imageUrl: string | null): string | null {
  if (!imageUrl) return null;
  if (imageUrl.startsWith("http")) return imageUrl;
  if (imageUrl.startsWith("/")) return `${API_BASE}${imageUrl}`;
  return null; // bare index (legacy) — no real file to show
}

export interface QuestionRead {
  id: number;
  exam_id: number | null;
  group_id: number | null;
  part: number | null;
  type: string;
  content: string;
  audio_url: string | null;
  image_url: string | null;
  options: Record<string, string> | null;
  reference_answer: string | null;
  difficulty: string | null;
  clo: string | null;
  topic: string | null;
  status: string;
  explanation: string | null;
  source_question_id: number | null;
  content_hash: string | null;
  import_batch_id: number | null;
  created_at: string | null;
}

export interface QuestionListResponse {
  total: number;
  items: QuestionRead[];
}

export async function listBankQuestions(params: {
  part?: number;
  status?: string;
  topic?: string;
  difficulty?: string;
  limit?: number;
  offset?: number;
}): Promise<QuestionListResponse> {
  const url = new URL(`${API_BASE}/api/v1/bank/questions`);
  if (params.part !== undefined) url.searchParams.append("part", String(params.part));
  if (params.status !== undefined) url.searchParams.append("status", params.status);
  if (params.topic !== undefined) url.searchParams.append("topic", params.topic);
  if (params.difficulty !== undefined) url.searchParams.append("difficulty", params.difficulty);
  if (params.limit !== undefined) url.searchParams.append("limit", String(params.limit));
  if (params.offset !== undefined) url.searchParams.append("offset", String(params.offset));

  return jsonOrThrow(
    await fetch(url.toString(), {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

export async function approveBankQuestions(ids: number[]): Promise<{ updated: number }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/bank/questions/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ ids }),
    }),
  );
}

export async function enrichBankQuestions(payload: {
  count: number;
  part: string;
  topic?: string;
}): Promise<{ success: boolean; generated_count: number }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/bank/enrich`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(payload),
    }),
  );
}

export interface SubmissionResult {
  submission_id: number;
  status: string;
  // Null while grading is asynchronous (essay/Writing via AI): the submit
  // response returns status "grading" first; scores arrive via getSubmission().
  listening_score: number | null;
  reading_score: number | null;
  total_score: number | null;
  listening_correct: number | null;
  reading_correct: number | null;
}

export interface EssayGrammarError {
  error: string;
  correction: string;
  explanation: string;
}

export interface EssayFeedback {
  score: number;
  feedback: string;
  grammar_errors?: EssayGrammarError[];
}

export interface SpeakingFeedback {
  score: number;
  transcription?: string;
  feedback: string;
  pronunciation_issues?: string[];
}

export interface SubmissionDetail {
  id: number;
  exam_id: number;
  user_id: number;
  started_at: string | null;
  submitted_at: string | null;
  status: string;
  answers: { question_id: number; candidate_text: string | null; audio_url: string | null }[];
  score_multiple_choice: number | null;
  listening_score: number | null;
  reading_score: number | null;
  score_writing: number | null;
  score_speaking: number | null;
  total_score: number | null;
  feedback_writing: Record<string, EssayFeedback> | null;
  feedback_speaking: Record<string, SpeakingFeedback> | null;
}

// Poll a submission's grading status/result (owner or admin/teacher only).
export async function getSubmission(id: number | string): Promise<SubmissionDetail> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/${id}`, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

// Teacher/admin override of AI essay grades (human-in-the-loop).
export async function overrideGrade(
  id: number | string,
  payload: { score_writing?: number | null; score_speaking?: number | null; teacher_note?: string | null },
): Promise<SubmissionDetail> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/${id}/grade`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    }),
  );
}

export async function submitExam(
  examId: number | string,
  answers: { question_id: number; answer: string; audio_url?: string | null }[],
): Promise<SubmissionResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${examId}/submit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ answers }),
    }),
  );
}

export interface StartAttemptResult {
  submission_id: number;
  exam_id: number;
  started_at: string;
  server_time: string;
  duration_minutes: number | null;
  // Server-authoritative remaining time (survives reload, can't be reset client-side).
  remaining_seconds: number;
  // Previously autosaved answers, for resuming an in-progress attempt.
  answers: { question_id: number; candidate_text: string | null; audio_url: string | null }[];
}

// Start (or resume) a server-authoritative exam session.
export async function startAttempt(examId: number | string): Promise<StartAttemptResult> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${examId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
    }),
  );
}

// Autosave in-progress answers so a disconnect/crash does not lose work.
export async function autosaveAttempt(
  submissionId: number,
  answers: { question_id: number; answer: string; audio_url?: string | null }[],
): Promise<{ submission_id: number; saved: number }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/${submissionId}/autosave`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ answers }),
    }),
  );
}

export interface ActiveAttempt {
  submission_id: number;
  exam_id: number;
  exam_title: string;
  started_at: string | null;
  remaining_seconds: number;
}

// In-progress attempts of the current candidate, for resuming from the exam list.
export async function getActiveAttempts(): Promise<ActiveAttempt[]> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/active`, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

export interface ExamActiveAttempt {
  submission_id: number;
  user_id: number;
  username: string;
  full_name: string | null;
  started_at: string | null;
  remaining_seconds: number;
}

// Teacher live invigilation: candidates currently taking a given exam.
export async function getExamActiveAttempts(examId: number | string): Promise<ExamActiveAttempt[]> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${examId}/active-attempts`, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}

// Download the exam's results as a CSV blob (admin/teacher).
export async function getExamResultsCsv(examId: number | string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/v1/exams/${examId}/results.csv`, {
    cache: "no-store",
    headers: { ...authHeaders() },
  });
  if (res.status === 401) clearToken();
  if (!res.ok) throw new Error(`${res.status}`);
  return res.blob();
}

// Upload a Speaking recording (Blob/File); returns the served audio_url.
export async function uploadAudio(file: Blob, filename = "recording.webm"): Promise<{ audio_url: string }> {
  const fd = new FormData();
  fd.append("file", file, filename);
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/upload-audio`, {
      method: "POST",
      // Do NOT set Content-Type — the browser adds the multipart boundary.
      headers: { ...authHeaders() },
      body: fd,
    }),
  );
}

export interface UserMe {
  id?: number;
  username: string;
  role: string;
  full_name?: string | null;
}

export async function getMe(): Promise<UserMe> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/auth/me`, {
      cache: "no-store",
      headers: {
        ...authHeaders(),
      },
    }),
  );
}

export async function registerCandidate(
  username: string,
  password: string,
  fullName?: string,
): Promise<{ id: number; username: string; role: string }> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        full_name: fullName || null,
      }),
    }),
  );
}


export interface SubmissionListItem {
  submission_id: number;
  user_id: number;
  username: string;
  full_name: string | null;
  exam_type: string | null;
  total_score: number | null;
  listening_score: number | null;
  reading_score: number | null;
  writing_score: number | null;
  status: string;
  submitted_at: string | null;
}

export interface MySubmissionListItem {
  submission_id: number;
  exam_id: number;
  exam_title: string;
  exam_type: string | null;
  total_score: number | null;
  listening_score: number | null;
  reading_score: number | null;
  writing_score: number | null;
  status: string;
  submitted_at: string | null;
}

export async function getExamSubmissions(examId: number | string): Promise<SubmissionListItem[]> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${examId}/submissions`, {
      cache: "no-store",
      headers: {
        ...authHeaders(),
      },
    }),
  );
}

export async function getMySubmissions(): Promise<MySubmissionListItem[]> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/submissions/me`, {
      cache: "no-store",
      headers: {
        ...authHeaders(),
      },
    }),
  );
}

export interface ScoreSummary {
  mean: number | null;
  min: number | null;
  max: number | null;
}

export interface ExamAnalyticsItem {
  question_id: number;
  part: number;
  type: string;
  content: string;
  answered_count: number;
  correct_count: number;
  correct_rate: number | null;
  option_distribution: Record<string, number> | null;
  avg_score: number | null;
}

export interface ExamAnalytics {
  submission_count: number;
  score_summary: ScoreSummary;
  items: ExamAnalyticsItem[];
}

export async function getExamAnalytics(examId: number | string): Promise<ExamAnalytics> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/${examId}/analytics`, {
      cache: "no-store",
      headers: { ...authHeaders() },
    }),
  );
}



