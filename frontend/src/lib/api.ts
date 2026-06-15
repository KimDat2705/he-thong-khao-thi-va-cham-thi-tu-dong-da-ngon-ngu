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

async function jsonOrThrow<T>(res: Response): Promise<T> {
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

export async function getBankStats(): Promise<BankStats> {
  return jsonOrThrow(await fetch(`${API_BASE}/api/v1/bank/stats`, { cache: "no-store" }));
}

export async function listExams(): Promise<ExamSummary[]> {
  return jsonOrThrow(await fetch(`${API_BASE}/api/v1/exams`, { cache: "no-store" }));
}

export async function generateExam(title: string, seed?: number): Promise<ExamSummary> {
  return jsonOrThrow(
    await fetch(`${API_BASE}/api/v1/exams/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, seed }),
    }),
  );
}

export async function getExam(
  id: number | string,
  includeAnswers = false,
): Promise<ExamDetail> {
  const qs = includeAnswers ? "?include_answers=true" : "";
  return jsonOrThrow(await fetch(`${API_BASE}/api/v1/exams/${id}${qs}`, { cache: "no-store" }));
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
