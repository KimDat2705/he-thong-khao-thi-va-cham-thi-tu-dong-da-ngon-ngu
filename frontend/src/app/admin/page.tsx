"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  type BankStats,
  type ExamSummary,
  getBankStats,
  listExams,
  generateExam,
} from "@/lib/api";

export default function AdminPage() {
  const [stats, setStats] = useState<BankStats | null>(null);
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const [s, e] = await Promise.all([getBankStats(), listExams()]);
      setStats(s);
      setExams(e);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Initial load (kept out of refresh() so no setState runs synchronously in the effect body).
    (async () => {
      try {
        const [s, e] = await Promise.all([getBankStats(), listExams()]);
        setStats(s);
        setExams(e);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function onGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const title = `TOEIC Demo ${new Date().toLocaleString("vi-VN")}`;
      await generateExam(title);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-bold">Quản trị đề thi TOEIC</h1>
      <p className="mt-1 text-sm text-gray-500">
        Ngân hàng câu hỏi đã duyệt → sinh đề → xem đề.
      </p>

      {error && (
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Tồn kho ngân hàng (approved vs blueprint)</h2>
          <button
            onClick={onGenerate}
            disabled={generating}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? "Đang sinh đề…" : "Sinh đề TOEIC mới"}
          </button>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-gray-500">Đang tải…</p>
        ) : stats ? (
          <table className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2">Part</th>
                <th>Loại</th>
                <th>Approved</th>
                <th>Cần</th>
                <th>Đủ?</th>
              </tr>
            </thead>
            <tbody>
              {stats.blueprint_sufficiency.map((p) => (
                <tr key={p.part} className="border-b">
                  <td className="py-2 font-medium">Part {p.part}</td>
                  <td className="text-gray-600">{p.type}</td>
                  <td>{p.approved_count}</td>
                  <td>{p.needed_count}</td>
                  <td>
                    {p.is_sufficient ? (
                      <span className="text-green-600">✓ đủ</span>
                    ) : (
                      <span className="text-red-600">✗ thiếu</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Đề đã sinh ({exams.length})</h2>
        {exams.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">
            Chưa có đề nào. Bấm “Sinh đề TOEIC mới” để tạo.
          </p>
        ) : (
          <ul className="mt-3 divide-y rounded-md border">
            {exams.map((e) => (
              <li key={e.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="font-medium">{e.title}</div>
                  <div className="text-xs text-gray-500">
                    #{e.id} · {e.exam_type} · {e.question_count} câu · {e.duration_minutes} phút
                  </div>
                </div>
                <Link
                  href={`/exam/${e.id}`}
                  className="rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50"
                >
                  Xem đề →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
