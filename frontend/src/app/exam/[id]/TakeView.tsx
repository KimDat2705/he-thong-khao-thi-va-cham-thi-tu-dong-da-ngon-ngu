"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ExamDetail,
  type QuestionOut,
  type GroupOut,
  getExam,
  submitExam,
  type SubmissionResult,
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
  return (
    <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-medium text-gray-900">
        {q.content?.trim() ? q.content : <span className="text-gray-400">[Câu hình ảnh — nhìn ảnh và nghe audio]</span>}
      </div>
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img} alt={`Câu ${q.id}`} className="mt-2 max-h-96 rounded border" />
      )}
      {hasOptions ? (
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

  const handleSelectAnswer = (qid: number, value: string) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [qid]: value,
    }));
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
