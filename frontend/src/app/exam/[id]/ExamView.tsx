"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  type ExamDetail,
  type QuestionOut,
  type GroupOut,
  getExam,
  audioSrc,
} from "@/lib/api";

function Question({ q, index }: { q: QuestionOut; index?: number }) {
  const audio = audioSrc(q.audio_url);
  return (
    <div className="rounded-md border border-gray-200 p-4">
      <div className="text-sm font-medium">
        {index != null && <span className="mr-2 text-gray-400">{index}.</span>}
        {q.content?.trim() ? q.content : <span className="text-gray-400">[Câu hình ảnh — nhìn ảnh và nghe]</span>}
      </div>
      {q.image_url && (
        <div className="mt-1 text-xs text-gray-400">🖼 Ảnh: {q.image_url}</div>
      )}
      {audio && (
        <audio controls className="mt-2 w-full">
          <source src={audio} type="audio/mpeg" />
        </audio>
      )}
      {q.options && (
        <ul className="mt-3 space-y-1">
          {Object.entries(q.options).map(([letter, text]) => {
            const correct = q.reference_answer === letter;
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
      )}
    </div>
  );
}

function Group({ g }: { g: GroupOut }) {
  const audio = audioSrc(g.audio_url);
  return (
    <div className="rounded-lg border border-gray-300 bg-gray-50/50 p-4">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        {g.topic && <span className="rounded bg-gray-200 px-2 py-0.5">{g.topic}</span>}
        {g.difficulty && <span>· {g.difficulty}</span>}
      </div>
      {g.passage_text && (
        <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">{g.passage_text}</p>
      )}
      {g.image_url && <div className="mt-1 text-xs text-gray-400">🖼 Ảnh: {g.image_url}</div>}
      {audio && (
        <audio controls className="mt-2 w-full">
          <source src={audio} type="audio/mpeg" />
        </audio>
      )}
      <div className="mt-3 space-y-3">
        {g.questions.map((q) => (
          <Question key={q.id} q={q} />
        ))}
      </div>
    </div>
  );
}

export default function ExamView({ id }: { id: string }) {
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExam(id)
      .then(setExam)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [id]);

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
      <Link href="/admin" className="text-sm text-blue-600">← Về quản trị</Link>
      <h1 className="mt-2 text-2xl font-bold">{exam.title}</h1>
      <p className="mt-1 text-sm text-gray-500">
        {exam.exam_type} · {exam.total_questions} câu · {exam.duration_minutes} phút
      </p>

      {exam.parts.map((p) => (
        <section key={p.part} className="mt-8">
          <h2 className="border-b pb-2 text-lg font-semibold">
            Part {p.part}
            <span className="ml-2 text-sm font-normal text-gray-400">
              {p.part_type} · {p.question_count} câu
            </span>
          </h2>
          <div className="mt-4 space-y-4">
            {p.standalone_questions.map((q) => (
              <Question key={q.id} q={q} />
            ))}
            {p.groups.map((g) => (
              <Group key={g.id} g={g} />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
