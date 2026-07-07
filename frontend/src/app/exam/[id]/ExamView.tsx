"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  type ExamDetail,
  type QuestionOut,
  type GroupOut,
  getExam,
  audioSrc,
  imageSrc,
} from "@/lib/api";

function Question({ q, showAnswers }: { q: QuestionOut; showAnswers: boolean }) {
  const img = imageSrc(q.image_url);
  const hasOptions = q.options && Object.keys(q.options).length > 0;
  return (
    <div className="rounded-md border border-gray-200 p-4">
      <div className="whitespace-pre-wrap text-sm font-medium">
        {q.content?.trim() ? q.content : <span className="text-gray-400">[Câu hình ảnh — nhìn ảnh và nghe audio]</span>}
      </div>
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img} alt={`Câu ${q.id}`} className="mt-2 max-h-96 rounded border" />
      )}
      {hasOptions ? (
        <ul className="mt-3 space-y-1">
          {Object.entries(q.options!).map(([letter, text]) => {
            const correct = showAnswers && q.reference_answer === letter;
            return (
              <li
                key={letter}
                className={`rounded px-2 py-1 text-sm ${
                  correct ? "bg-green-50 font-medium text-green-800" : "text-gray-700"
                }`}
              >
                <span className="mr-2 font-semibold">{letter}.</span>
                {text}
                {correct && <span className="ml-2 text-xs text-green-600">✓ đáp án</span>}
              </li>
            );
          })}
        </ul>
      ) : (
        showAnswers && q.reference_answer && (
          <div className="mt-2 whitespace-pre-wrap text-sm text-green-700">Đáp án đúng: <b>{q.reference_answer}</b></div>
        )
      )}
    </div>
  );
}

function Group({ g, showAnswers }: { g: GroupOut; showAnswers: boolean }) {
  const img = imageSrc(g.image_url);
  return (
    <div className="rounded-lg border border-gray-300 bg-gray-50/50 p-4">
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
      <div className="mt-3 space-y-3">
        {g.questions.map((q) => (
          <Question key={q.id} q={q} showAnswers={showAnswers} />
        ))}
      </div>
    </div>
  );
}

export default function ExamView({ id }: { id: string }) {
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAnswers, setShowAnswers] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    getExam(id, showAnswers)
      .then((data) => {
        setExam(data);
        // Only clear the auth notice on a successful answer-key load (teacher/admin);
        // the revert-triggered candidate re-fetch must NOT wipe a just-set notice.
        if (showAnswers) setAuthError(null);
      })
      .catch((err) => {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (showAnswers && (errMsg.includes("401") || errMsg.includes("403"))) {
          setAuthError("Bạn không có quyền xem đáp án (chỉ dành cho Giáo viên hoặc Admin).");
          setShowAnswers(false);
        } else {
          setError(errMsg);
        }
      });
  }, [id, showAnswers]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Link href="/admin" className="text-sm text-blue-600">← Về quản trị</Link>
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </main>
    );
  }

  if (!exam) {
    return <main className="mx-auto max-w-3xl px-6 py-10 text-sm text-gray-500">Đang tải đề…</main>;
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/admin" className="text-sm text-blue-600">← Về quản trị</Link>
          <Link href={`/exam/${id}/take`} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
            Làm bài →
          </Link>
        </div>
        <button
          onClick={() => setShowAnswers((v) => !v)}
          className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
            showAnswers
              ? "border-green-600 bg-green-50 text-green-700"
              : "border-gray-300 text-gray-600 hover:bg-gray-50"
          }`}
        >
          {showAnswers ? "Đang hiện đáp án (giáo viên)" : "Hiện đáp án (giáo viên)"}
        </button>
      </div>

      {authError && (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          ⚠️ {authError}
        </div>
      )}

      <h1 className="mt-2 text-2xl font-bold">{exam.title}</h1>
      <p className="mt-1 text-sm text-gray-500">
        {exam.exam_type} · {exam.total_questions} câu · {exam.duration_minutes} phút
        {!showAnswers && <span className="ml-2 text-gray-400">· chế độ thí sinh (ẩn đáp án)</span>}
      </p>

      {exam.parts.map((p) => {
        const audio = audioSrc(p.audio_url);
        return (
          <section key={p.part} className="mt-8">
            <h2 className="border-b pb-2 text-lg font-semibold">
              Part {p.part}
              <span className="ml-2 text-sm font-normal text-gray-400">
                {p.part_type} · {p.question_count} câu
              </span>
            </h2>
            {audio && (
              <div className="mt-3">
                <div className="text-xs text-gray-500">🎧 Audio phần Nghe</div>
                <audio controls className="mt-1 w-full">
                  <source src={audio} type="audio/mpeg" />
                </audio>
              </div>
            )}
            <div className="mt-4 space-y-4">
              {p.standalone_questions.map((q) => (
                <Question key={q.id} q={q} showAnswers={showAnswers} />
              ))}
              {p.groups.map((g) => (
                <Group key={g.id} g={g} showAnswers={showAnswers} />
              ))}
            </div>
          </section>
        );
      })}
    </main>
  );
}
