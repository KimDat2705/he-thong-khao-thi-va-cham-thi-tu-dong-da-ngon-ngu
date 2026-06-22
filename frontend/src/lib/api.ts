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

export async function getBankStats(): Promise<BankStats> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/bank/stats`, {
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

export async function generateExam(title: string, seed?: number): Promise<ExamSummary> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ title, seed }),
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

export interface SubmissionResult {
  submission_id: number;
  status: string;
  listening_score: number;
  reading_score: number;
  total_score: number;
  listening_correct: number;
  reading_correct: number;
}

export async function submitExam(
  examId: number | string,
  answers: { question_id: number; answer: string }[],
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

