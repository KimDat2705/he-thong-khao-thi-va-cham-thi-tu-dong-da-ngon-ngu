"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type BankStats,
  type ExamSummary,
  getBankStats,
  listExams,
  generateExam,
  getToken,
  clearToken,
  releaseExam,
  retireExam,
  updateExam,
} from "@/lib/api";

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<BankStats | null>(null);
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  // States for exam lifecycle management
  const [processingExamId, setProcessingExamId] = useState<number | null>(null);
  const [editingExamId, setEditingExamId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDuration, setEditDuration] = useState("");
  const [examType, setExamType] = useState<string>("VSTEP_B1");


  async function refresh() {
    setError(null);
    try {
      const [s, e] = await Promise.all([getBankStats(), listExams()]);
      setStats(s);
      setExams(e);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    // Initial load only if token is present
    (async () => {
      try {
        const [s, e] = await Promise.all([getBankStats(), listExams()]);
        setStats(s);
        setExams(e);
        setAuthChecked(true);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (errMsg.includes("401")) {
          clearToken();
          router.push("/login");
        } else {
          setError(errMsg);
          setAuthChecked(true);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  async function onGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const title = `VSTEP B1 Demo ${new Date().toLocaleString("vi-VN")}`;
      await generateExam(title, examType);
      await refresh();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setGenerating(false);
    }
  }

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  async function onToggleActive(id: number, currentActive: boolean) {
    setProcessingExamId(id);
    setError(null);
    try {
      if (currentActive) {
        await retireExam(id);
      } else {
        await releaseExam(id);
      }
      await refresh();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setProcessingExamId(null);
    }
  }

  function onStartEdit(e: ExamSummary) {
    setEditingExamId(e.id);
    setEditTitle(e.title);
    setEditDuration(String(e.duration_minutes));
    setError(null);
  }

  function onCancelEdit() {
    setEditingExamId(null);
    setEditTitle("");
    setEditDuration("");
  }

  async function onSaveEdit(id: number) {
    const trimmedTitle = editTitle.trim();
    if (!trimmedTitle) {
      setError("Tiêu đề đề thi không được để trống.");
      return;
    }
    const duration = parseInt(editDuration, 10);
    if (isNaN(duration) || duration <= 0) {
      setError("Thời gian làm bài phải là số nguyên dương.");
      return;
    }

    setProcessingExamId(id);
    setError(null);
    try {
      await updateExam(id, { title: trimmedTitle, duration_minutes: duration });
      setEditingExamId(null);
      await refresh();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setProcessingExamId(null);
    }
  }


  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 text-sm text-gray-500">
        Đang xác thực thông tin đăng nhập…
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Quản trị đề thi</h1>
        <button
          onClick={onLogout}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          Đăng xuất
        </button>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        Ngân hàng câu hỏi đã duyệt → sinh đề → xem đề.
      </p>

      <div className="mt-4 flex gap-4 text-sm font-medium border-b border-gray-200 pb-1">
        <Link href="/admin" className="text-blue-600 border-b-2 border-blue-600 pb-1 font-semibold">
          Quản trị đề thi
        </Link>
        <Link href="/admin/bank" className="text-gray-500 hover:text-gray-700 pb-1">
          Duyệt ngân hàng câu hỏi
        </Link>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Tồn kho ngân hàng (approved vs blueprint)</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {generating ? "Đang sinh đề…" : "Sinh đề VSTEP B1 mới"}
            </button>
          </div>
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
            Chưa có đề nào. Chọn loại đề và bấm sinh đề mới để tạo.
          </p>
        ) : (
          <ul className="mt-3 divide-y rounded-md border">
            {exams.map((e) => (
              <li key={e.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50">
                {editingExamId === e.id ? (
                  <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-1 flex-col gap-2 sm:flex-row">
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(val) => setEditTitle(val.target.value)}
                        placeholder="Tiêu đề đề thi"
                        className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                        disabled={processingExamId === e.id}
                      />
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          value={editDuration}
                          onChange={(val) => setEditDuration(val.target.value)}
                          placeholder="Số phút"
                          className="w-20 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                          disabled={processingExamId === e.id}
                        />
                        <span className="text-xs text-gray-500">phút</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 self-end sm:self-auto">
                      <button
                        onClick={() => onSaveEdit(e.id)}
                        disabled={processingExamId === e.id}
                        className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        Lưu
                      </button>
                      <button
                        onClick={onCancelEdit}
                        disabled={processingExamId === e.id}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="pr-4">
                      <div className="flex items-center flex-wrap gap-2">
                        <span className="font-medium">{e.title}</span>
                        {e.is_active ? (
                          <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                            Đã phát hành
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10">
                            Đã ẩn
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        #{e.id} · {e.exam_type} · {e.question_count} câu · {e.duration_minutes} phút
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link
                        href={`/exam/${e.id}`}
                        className="rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-50"
                      >
                        Xem đề →
                      </Link>
                      <Link
                        href={`/admin/results/${e.id}`}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                      >
                        Kết quả
                      </Link>
                      <button
                        onClick={() => onStartEdit(e)}
                        disabled={processingExamId !== null}
                        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => onToggleActive(e.id, e.is_active)}
                        disabled={processingExamId !== null}
                        className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${
                          e.is_active
                            ? "border border-red-300 bg-white text-red-700 hover:bg-red-50"
                            : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                      >
                        {processingExamId === e.id
                          ? "Đang xử lý…"
                          : e.is_active
                          ? "Ẩn đề"
                          : "Phát hành"}
                      </button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
