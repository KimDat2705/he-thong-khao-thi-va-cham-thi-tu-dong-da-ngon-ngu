"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ExamDetail,
  type QuestionOut,
  type GroupOut,
  getExam,
  submitExam,
  getSubmission,
  type SubmissionResult,
  type SubmissionDetail,
  audioSrc,
  imageSrc,
  getToken,
  clearToken,
} from "@/lib/api";

function QuestionItem({
  q,
  selectedValue,
  onChange,
}: {
  q: QuestionOut;
  selectedValue?: string;
  onChange: (value: string) => void;
}) {
  const img = imageSrc(q.image_url);
  const hasOptions = q.options && Object.keys(q.options).length > 0;
  const isWriting = q.type === "writing";
  return (
    <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-medium text-gray-900 whitespace-pre-wrap">
        {q.content?.trim() ? q.content : <span className="text-gray-400">[Câu hình ảnh — nhìn ảnh và nghe audio]</span>}
      </div>
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img} alt={`Câu ${q.id}`} className="mt-2 max-h-96 rounded border" />
      )}
      {isWriting ? (
        <div className="mt-3">
          <textarea
            rows={8}
            placeholder="Viết bài làm của bạn ở đây…"
            value={selectedValue || ""}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-hidden"
          />
          <div className="mt-1 text-right text-xs text-gray-400">
            {(selectedValue || "").trim() ? (selectedValue || "").trim().split(/\s+/).length : 0} từ
          </div>
        </div>
      ) : hasOptions ? (
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {Object.entries(q.options!).map(([letter, text]) => (
            <label
              key={letter}
              className={`flex items-center gap-2 rounded-md border p-2.5 cursor-pointer transition-colors ${
                selectedValue === letter
                  ? "border-blue-500 bg-blue-50/50"
                  : "border-gray-200 hover:bg-gray-50"
              }`}
            >
              <input
                type="radio"
                name={`question-${q.id}`}
                checked={selectedValue === letter}
                onChange={() => onChange(letter)}
                className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                <span className="mr-1 font-bold">{letter}.</span> {text}
              </span>
            </label>
          ))}
        </div>
      ) : (
        <div className="mt-2">
          <input
            type="text"
            placeholder="Nhập câu trả lời..."
            value={selectedValue || ""}
            onChange={(e) => onChange(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-hidden"
          />
        </div>
      )}
    </div>
  );
}

function GroupItem({
  g,
  selectedAnswers,
  onChange,
}: {
  g: GroupOut;
  selectedAnswers: Record<number, string>;
  onChange: (qid: number, value: string) => void;
}) {
  const img = imageSrc(g.image_url);
  return (
    <div className="rounded-lg border border-gray-300 bg-gray-50/50 p-4 space-y-3">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        {g.topic && <span className="rounded bg-gray-200 px-2 py-0.5">{g.topic}</span>}
        {g.difficulty && <span>· {g.difficulty}</span>}
      </div>
      {g.passage_text && (
        <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">{g.passage_text}</p>
      )}
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img} alt={`Đoạn ${g.id}`} className="mt-2 max-h-96 rounded border" />
      )}
      <div className="space-y-3">
        {g.questions.map((q) => (
          <QuestionItem
            key={q.id}
            q={q}
            selectedValue={selectedAnswers[q.id]}
            onChange={(value) => onChange(q.id, value)}
          />
        ))}
      </div>
    </div>
  );
}

export default function TakeView({ id }: { id: string }) {
  const router = useRouter();
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);

  // Take States
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmissionResult | null>(null);
  // Async (essay/AI) grading: poll the submission until it completes.
  const [gradingDetail, setGradingDetail] = useState<SubmissionDetail | null>(null);
  const [polling, setPolling] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    setAuthChecked(true);
  }, [router]);

  useEffect(() => {
    if (!authChecked) return;

    setLoading(true);
    getExam(id, false)
      .then((data) => {
        setExam(data);
        setError(null);
      })
      .catch((err) => {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (errMsg.includes("401")) {
          clearToken();
          router.push("/login");
        } else {
          setError(errMsg);
        }
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id, authChecked, router]);

  // Extract all question IDs to calculate progress and build payload
  const getAllQuestions = (): QuestionOut[] => {
    if (!exam) return [];
    const questions: QuestionOut[] = [];
    exam.parts.forEach((p) => {
      p.standalone_questions.forEach((q) => {
        questions.push(q);
      });
      p.groups.forEach((g) => {
        g.questions.forEach((q) => {
          questions.push(q);
        });
      });
    });
    return questions;
  };

  const questions = getAllQuestions();
  const totalQuestions = questions.length;
  const answeredCount = Object.keys(selectedAnswers).filter(
    (key) => selectedAnswers[Number(key)]?.trim() !== ""
  ).length;
  // Essay exams (Writing/Speaking) are graded asynchronously by AI — the result
  // panel polls for the score instead of showing TOEIC L/R numbers immediately.
  const isEssayExam = questions.some((q) => q.type === "writing" || q.type === "speaking");

  const handleSelectAnswer = (qid: number, value: string) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [qid]: value,
    }));
  };

  const pollGrading = async (submissionId: number) => {
    setPolling(true);
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    // ~40 * 2.5s = 100s ceiling, well above the AI grading turnaround.
    for (let i = 0; i < 40; i++) {
      try {
        const detail = await getSubmission(submissionId);
        if (!mountedRef.current) return;
        if (detail.status === "completed") {
          setGradingDetail(detail);
          setPolling(false);
          return;
        }
      } catch (err) {
        const m = err instanceof Error ? err.message : String(err);
        if (m.includes("401")) {
          clearToken();
          router.push("/login");
          return;
        }
        // transient error -> keep polling
      }
      await sleep(2500);
    }
    if (mountedRef.current) setPolling(false);
  };

  const handleSubmit = async () => {
    if (!exam) return;
    const ok = window.confirm("Bạn có chắc chắn muốn nộp bài không?");
    if (!ok) return;

    setSubmitting(true);
    try {
      // Build answers payload for ALL questions in the exam
      const answersPayload = questions.map((q) => ({
        question_id: q.id,
        answer: selectedAnswers[q.id] ?? "",
      }));

      const res = await submitExam(exam.id, answersPayload);
      setResult(res);
      window.scrollTo({ top: 0, behavior: "smooth" });
      // Async essay grading: returned status is "grading" with no scores yet.
      if (res.status !== "completed") {
        pollGrading(res.submission_id);
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        alert(`Nộp bài thất bại: ${errMsg}`);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href="/admin" className="text-sm text-blue-600">← Về quản trị</Link>
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          Lỗi: {error}
        </div>
      </main>
    );
  }

  if (loading || !exam) {
    return <main className="mx-auto max-w-3xl px-6 py-10 text-sm text-gray-500">Đang tải đề thi…</main>;
  }

  if (result && isEssayExam) {
    const resetEssay = () => {
      setResult(null);
      setGradingDetail(null);
      setPolling(false);
      setSelectedAnswers({});
    };
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-xl space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">Kết Quả Bài Viết</h1>
            <p className="text-sm text-gray-500 mt-1">{exam.title}</p>
          </div>

          {!gradingDetail ? (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
              <p className="text-sm font-medium text-gray-700">Đang chấm bằng AI (Gemini)…</p>
              <p className="text-xs text-gray-400">
                {polling ? "Bài đã nộp, vui lòng đợi trong giây lát." : "Đang xử lý…"}
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-col items-center justify-center py-4">
                <div className="flex h-28 w-28 items-center justify-center rounded-full bg-emerald-50 border-4 border-emerald-500 shadow-inner">
                  <div className="text-center">
                    <span className="text-3xl font-extrabold text-emerald-600">
                      {gradingDetail.score_writing ?? gradingDetail.total_score ?? 0}
                    </span>
                    <span className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 mt-0.5">Điểm AI</span>
                  </div>
                </div>
                <span className="mt-2 text-xs font-semibold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
                  Trạng thái: {gradingDetail.status}
                </span>
              </div>

              <div className="space-y-4 border-t border-gray-100 pt-5">
                <h2 className="text-sm font-bold text-gray-900">Nhận xét chi tiết từ AI</h2>
                {gradingDetail.feedback_writing &&
                Object.keys(gradingDetail.feedback_writing).length > 0 ? (
                  Object.entries(gradingDetail.feedback_writing).map(([qkey, fb], idx) => (
                    <div key={qkey} className="rounded-lg border border-gray-200 bg-gray-50/50 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-gray-800">Bài {idx + 1}</span>
                        <span className="text-sm font-bold text-emerald-600">{fb.score}/10</span>
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-gray-700">{fb.feedback}</p>
                      {fb.grammar_errors && fb.grammar_errors.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <span className="text-xs font-semibold text-gray-500">Lỗi & gợi ý sửa:</span>
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
                  ))
                ) : (
                  <p className="text-sm text-gray-500">Không có nhận xét chi tiết.</p>
                )}
              </div>
            </>
          )}

          <div className="flex flex-col gap-2 pt-2">
            <button
              onClick={resetEssay}
              className="w-full rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            >
              Làm lại bài
            </button>
            <Link
              href="/my-results"
              className="w-full rounded-md border border-gray-300 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors inline-block text-center"
            >
              Kết quả của tôi
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (result) {
    return (
      <main className="mx-auto max-w-xl px-6 py-12">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-xl text-center space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Kết Quả Thi</h1>
            <p className="text-sm text-gray-500 mt-1">{exam.title}</p>
          </div>

          <div className="flex flex-col items-center justify-center py-6">
            <div className="flex h-32 w-32 items-center justify-center rounded-full bg-blue-50 border-4 border-blue-500 shadow-inner">
              <div>
                <span className="text-4xl font-extrabold text-blue-600">{result.total_score}</span>
                <span className="block text-[10px] uppercase tracking-wider font-semibold text-gray-400 mt-0.5">Điểm</span>
              </div>
            </div>
            <span className="mt-2 text-xs font-semibold uppercase tracking-wider text-green-600 bg-green-50 px-2 py-0.5 rounded">
              Trạng thái: {result.status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 border-t border-b border-gray-100 py-6 text-left">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Nghe (Listening)</span>
              <span className="text-xl font-bold text-gray-800 block">{result.listening_score} điểm</span>
              <span className="text-xs text-gray-500 block">Số câu đúng: {result.listening_correct} câu</span>
            </div>
            <div className="space-y-1 border-l border-gray-100 pl-4">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Đọc (Reading)</span>
              <span className="text-xl font-bold text-gray-800 block">{result.reading_score} điểm</span>
              <span className="text-xs text-gray-500 block">Số câu đúng: {result.reading_correct} câu</span>
            </div>
          </div>

          <div className="flex flex-col gap-2 pt-2">
            <button
              onClick={() => {
                setResult(null);
                setSelectedAnswers({});
              }}
              className="w-full rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            >
              Làm lại bài thi
            </button>
            <Link
              href="/admin"
              className="w-full rounded-md border border-gray-300 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors inline-block"
            >
              Quay lại quản trị
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 pb-20 pt-24 relative">
      {/* Sticky Header with Progress */}
      <header className="fixed top-0 left-0 right-0 z-10 border-b border-gray-200 bg-white/95 px-6 py-3 backdrop-blur-md">
        <div className="mx-auto max-w-3xl flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-bold text-gray-900">{exam.title}</h1>
            <div className="mt-1 flex items-center gap-3">
              <div className="h-1.5 w-32 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0}%` }}
                />
              </div>
              <span className="text-xs font-medium text-gray-500">
                Đã làm: {answeredCount}/{totalQuestions} câu
              </span>
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="shrink-0 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-hidden disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Đang nộp..." : "Nộp bài"}
          </button>
        </div>
      </header>

      {/* Main Questions Container */}
      <div className="space-y-8">
        {exam.parts.map((p) => {
          const audio = audioSrc(p.audio_url);
          return (
            <section key={p.part} className="space-y-4">
              <h2 className="border-b border-gray-200 pb-2 text-lg font-bold text-gray-950">
                Part {p.part}
                <span className="ml-2 text-sm font-normal text-gray-400">
                  {p.part_type} · {p.question_count} câu
                </span>
              </h2>
              {audio && (
                <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-4">
                  <span className="text-xs font-semibold text-gray-500 block mb-1">🎧 Audio phần Nghe</span>
                  <audio controls className="w-full">
                    <source src={audio} type="audio/mpeg" />
                  </audio>
                </div>
              )}
              <div className="space-y-4 mt-4">
                {p.standalone_questions.map((q) => (
                  <QuestionItem
                    key={q.id}
                    q={q}
                    selectedValue={selectedAnswers[q.id]}
                    onChange={(value) => handleSelectAnswer(q.id, value)}
                  />
                ))}
                {p.groups.map((g) => (
                  <GroupItem
                    key={g.id}
                    g={g}
                    selectedAnswers={selectedAnswers}
                    onChange={handleSelectAnswer}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </main>
  );
}
