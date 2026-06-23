"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getSubmission,
  getExam,
  getToken,
  clearToken,
  API_BASE,
  type SubmissionDetail,
  type QuestionOut,
} from "@/lib/api";

export default function SubmissionDetailView({ id }: { id: string }) {
  const router = useRouter();
  const [sub, setSub] = useState<SubmissionDetail | null>(null);
  // Map question_id -> { content, type } from the exam (for showing the prompt).
  const [questionMap, setQuestionMap] = useState<Record<number, QuestionOut>>({});
  const [examTitle, setExamTitle] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    (async () => {
      try {
        const data = await getSubmission(id);
        setSub(data);
        // Best-effort fetch of the exam to show prompts (active exams only).
        try {
          const exam = await getExam(data.exam_id, false);
          setExamTitle(exam.title);
          const map: Record<number, QuestionOut> = {};
          for (const p of exam.parts) {
            for (const q of p.standalone_questions) map[q.id] = q;
            for (const g of p.groups) for (const q of g.questions) map[q.id] = q;
          }
          setQuestionMap(map);
        } catch {
          /* retired/unavailable exam — fall back to question ids */
        }
      } catch (err) {
        const m = err instanceof Error ? err.message : String(err);
        if (m.includes("401")) {
          clearToken();
          router.push("/login");
        } else if (m.includes("403")) {
          setForbidden(true);
        } else {
          setError(m);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [id, router]);

  if (loading) {
    return <main className="mx-auto max-w-3xl px-6 py-10 text-sm text-gray-500">Đang tải bài nộp…</main>;
  }
  if (forbidden) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          Bạn không có quyền xem bài nộp này.
        </div>
      </main>
    );
  }
  if (error || !sub) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          Lỗi: {error ?? "Không tìm thấy bài nộp."}
        </div>
      </main>
    );
  }

  const fw = sub.feedback_writing || {};
  const fs = sub.feedback_speaking || {};
  const hasEssayFeedback = (qid: number) => !!fw[`question_${qid}`] || !!fs[`question_${qid}`];
  // Choice (auto-graded) answers = those WITHOUT an AI free-text feedback entry.
  const choiceCount = sub.answers.filter((a) => !hasEssayFeedback(a.question_id)).length;
  const essayAnswers = sub.answers.filter((a) => fw[`question_${a.question_id}`]);
  const speakingAnswers = sub.answers.filter((a) => fs[`question_${a.question_id}`]);
  const audioFullUrl = (u: string | null) =>
    !u ? null : u.startsWith("http") ? u : `${API_BASE}${u}`;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10 space-y-6">
      <Link href="/my-results" className="text-sm font-semibold text-blue-600 hover:underline">
        ← Quay lại
      </Link>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {examTitle || `Bài nộp #${sub.id}`}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Bài nộp #{sub.id} · Trạng thái:{" "}
            <span className={sub.status === "completed" ? "text-green-700 font-medium" : "text-yellow-700 font-medium"}>
              {sub.status === "completed" ? "Đã chấm xong" : sub.status}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-4">
          {choiceCount > 0 && (
            <div>
              <div className="text-xs text-gray-400 font-medium">Trắc nghiệm</div>
              <div className="text-base font-bold text-blue-700">
                {sub.score_multiple_choice ?? 0}/{choiceCount} câu đúng
              </div>
            </div>
          )}
          {(sub.score_writing ?? 0) > 0 || essayAnswers.length > 0 ? (
            <div>
              <div className="text-xs text-gray-400 font-medium">Điểm Viết (AI)</div>
              <div className="text-base font-bold text-emerald-700">{sub.score_writing ?? 0}</div>
            </div>
          ) : null}
          {(sub.score_speaking ?? 0) > 0 || speakingAnswers.length > 0 ? (
            <div>
              <div className="text-xs text-gray-400 font-medium">Điểm Nói (AI)</div>
              <div className="text-base font-bold text-emerald-700">{sub.score_speaking ?? 0}</div>
            </div>
          ) : null}
          <div>
            <div className="text-xs text-gray-400 font-semibold">Tổng điểm</div>
            <div className="text-base font-bold text-gray-900">{sub.total_score ?? "—"}</div>
          </div>
        </div>
      </div>

      {essayAnswers.length === 0 && speakingAnswers.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500 bg-white">
          Bài nộp này không có câu tự luận (hoặc chưa chấm xong).
        </div>
      )}

      {essayAnswers.length > 0 && (
        <div className="space-y-5">
          <h2 className="text-sm font-bold text-gray-900">Bài làm tự luận &amp; nhận xét AI (Viết)</h2>
          {essayAnswers.map((a, idx) => {
            const fb = fw[`question_${a.question_id}`];
            const q = questionMap[a.question_id];
            return (
              <div key={a.question_id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-800">Bài {idx + 1}</span>
                  {fb && <span className="text-sm font-bold text-emerald-600">{fb.score}/10</span>}
                </div>
                {q?.content && (
                  <p className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-xs text-gray-600">
                    <span className="font-semibold">Đề: </span>{q.content}
                  </p>
                )}
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-1">Bài làm của thí sinh</div>
                  <p className="whitespace-pre-wrap rounded-md border border-gray-200 p-3 text-sm text-gray-800">
                    {a.candidate_text?.trim() ? a.candidate_text : <span className="text-gray-400">(để trống)</span>}
                  </p>
                </div>
                {fb && (
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-500">Nhận xét AI</div>
                    <p className="whitespace-pre-wrap text-sm text-gray-700">{fb.feedback}</p>
                    {fb.grammar_errors && fb.grammar_errors.length > 0 && (
                      <div className="space-y-1.5">
                        {fb.grammar_errors.map((ge, gi) => (
                          <div key={gi} className="rounded border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-gray-700">
                            <span className="line-through text-red-500">{ge.error}</span>
                            {" → "}
                            <span className="font-semibold text-emerald-700">{ge.correction}</span>
                            {ge.explanation && <span className="block text-gray-500 mt-0.5">{ge.explanation}</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {speakingAnswers.length > 0 && (
        <div className="space-y-5">
          <h2 className="text-sm font-bold text-gray-900">Bài làm &amp; nhận xét AI (Nói)</h2>
          {speakingAnswers.map((a, idx) => {
            const fb = fs[`question_${a.question_id}`];
            const q = questionMap[a.question_id];
            const src = audioFullUrl(a.audio_url);
            return (
              <div key={a.question_id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-800">Phần nói {idx + 1}</span>
                  {fb && <span className="text-sm font-bold text-emerald-600">{fb.score}/10</span>}
                </div>
                {q?.content && (
                  <p className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-xs text-gray-600">
                    <span className="font-semibold">Đề: </span>{q.content}
                  </p>
                )}
                {src && <audio controls src={src} className="w-full" />}
                {fb?.transcription && (
                  <p className="whitespace-pre-wrap rounded-md border border-gray-200 p-3 text-sm italic text-gray-700">
                    “{fb.transcription}”
                  </p>
                )}
                {fb && (
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-500">Nhận xét AI</div>
                    <p className="whitespace-pre-wrap text-sm text-gray-700">{fb.feedback}</p>
                    {fb.pronunciation_issues && fb.pronunciation_issues.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <span className="text-xs font-semibold text-gray-500">Lỗi phát âm:</span>
                        <ul className="list-disc pl-5 text-xs text-gray-700">
                          {fb.pronunciation_issues.map((p, pi) => (
                            <li key={pi}>{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
