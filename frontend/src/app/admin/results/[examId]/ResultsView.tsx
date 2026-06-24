"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getExam,
  getExamSubmissions,
  getExamActiveAttempts,
  getExamResultsCsv,
  getExamAnalytics,
  getToken,
  clearToken,
  type SubmissionListItem,
  type ExamActiveAttempt,
  type ExamAnalytics,
} from "@/lib/api";

interface ResultsViewProps {
  examId: string;
}

function formatRemaining(totalSec: number): string {
  const safe = Math.max(0, totalSec);
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ResultsView({ examId }: ResultsViewProps) {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [examTitle, setExamTitle] = useState<string>(`Kết quả đề #${examId}`);
  const [examType, setExamType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  // Live invigilation: candidates currently taking this exam (in-progress).
  const [activeAttempts, setActiveAttempts] = useState<ExamActiveAttempt[]>([]);
  const [refreshingActive, setRefreshingActive] = useState(false);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  // Essay exams (VSTEP Writing, etc.) show an AI Writing score instead of L/R.
  const isEssay = examType !== null && examType.toUpperCase() !== "TOEIC";

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    (async () => {
      try {
        // 1. Fetch submissions (requires token/admin permission)
        const subs = await getExamSubmissions(examId);
        setSubmissions(subs);

        // 2. Fetch exam title (no token, handles retired status)
        try {
          const exam = await getExam(examId, false);
          setExamTitle(`Kết quả đề thi: ${exam.title}`);
          setExamType(exam.exam_type);
        } catch (titleErr) {
          console.warn("Failed to fetch exam title, falling back:", titleErr);
          // Keep default fallback title: "Kết quả đề #{examId}"
        }

        // 3. Live in-progress attempts (teacher invigilation).
        try {
          setActiveAttempts(await getExamActiveAttempts(examId));
        } catch (activeErr) {
          console.warn("Failed to fetch active attempts:", activeErr);
        }

        // 4. Fetch exam analytics (requires teacher/admin)
        try {
          const analyt = await getExamAnalytics(examId);
          setAnalytics(analyt);
        } catch (analytErr) {
          console.warn("Failed to fetch exam analytics:", analytErr);
          const errMsg = analytErr instanceof Error ? analytErr.message : String(analytErr);
          if (errMsg.includes("401") || errMsg.includes("403")) {
            throw analytErr;
          } else {
            setAnalyticsError("Không tải được dữ liệu phân tích.");
          }
        }

        setAuthChecked(true);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (errMsg.includes("401")) {
          clearToken();
          router.push("/login");
        } else if (errMsg.includes("403")) {
          setIsForbidden(true);
          setAuthChecked(true);
        } else {
          setError(errMsg);
          setAuthChecked(true);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [examId, router]);

  const [exporting, setExporting] = useState(false);

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const blob = await getExamResultsCsv(examId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ket_qua_de_${examId}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const m = err instanceof Error ? err.message : String(err);
      if (m.includes("401")) {
        clearToken();
        router.push("/login");
      }
    } finally {
      setExporting(false);
    }
  };

  const refreshActive = async () => {
    setRefreshingActive(true);
    try {
      setActiveAttempts(await getExamActiveAttempts(examId));
    } catch {
      /* non-fatal — keep the previous snapshot */
    } finally {
      setRefreshingActive(false);
    }
  };

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 text-sm text-gray-500">
        Đang xác thực thông tin đăng nhập…
      </div>
    );
  }

  if (isForbidden) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="mb-4">
          <Link href="/admin" className="text-sm font-semibold text-blue-600 hover:underline">
            ← Về quản trị
          </Link>
        </div>
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          Bạn không có quyền truy cập trang này.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-4">
        <Link href="/admin" className="text-sm font-semibold text-blue-600 hover:underline">
          ← Về quản trị
        </Link>
      </div>

      <div className="flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold">{examTitle}</h1>
          <p className="mt-1 text-sm text-gray-500">
            Danh sách bài nộp và điểm số chi tiết của các thí sinh.
          </p>
        </div>
        {submissions.length > 0 && (
          <button
            onClick={handleExportCsv}
            disabled={exporting}
            className="shrink-0 rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {exporting ? "Đang xuất…" : "⬇ Xuất CSV"}
          </button>
        )}
      </div>

      {/* Live invigilation: candidates currently taking this exam */}
      <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4 shadow-xs">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-bold text-gray-900">
            <span className="relative flex h-2.5 w-2.5">
              {activeAttempts.length > 0 && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                  activeAttempts.length > 0 ? "bg-emerald-500" : "bg-gray-300"
                }`}
              />
            </span>
            Đang làm bài ({activeAttempts.length})
          </h2>
          <button
            onClick={refreshActive}
            disabled={refreshingActive}
            className="rounded-md border border-gray-200 px-3 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshingActive ? "Đang tải…" : "↻ Làm mới"}
          </button>
        </div>
        {activeAttempts.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">Hiện không có thí sinh nào đang làm bài.</p>
        ) : (
          <ul className="mt-3 divide-y divide-gray-100">
            {activeAttempts.map((a) => {
              const name = a.full_name ? `${a.full_name} (${a.username})` : a.username;
              const started = a.started_at
                ? new Date(a.started_at).toLocaleTimeString("vi-VN")
                : "—";
              return (
                <li key={a.submission_id} className="flex items-center justify-between py-2 text-sm">
                  <span className="font-medium text-gray-900">{name}</span>
                  <span className="flex items-center gap-4 text-xs text-gray-500">
                    <span>Bắt đầu: {started}</span>
                    <span
                      className={`font-semibold tabular-nums ${
                        a.remaining_seconds <= 300 ? "text-red-600" : "text-emerald-700"
                      }`}
                    >
                      ⏱ {formatRemaining(a.remaining_seconds)} còn lại
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* 📊 Phân tích panel */}
      {analyticsError ? (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-xs">
          {analyticsError}
        </div>
      ) : analytics ? (
        <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4 shadow-xs">
          <h2 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
            <span>📊 Phân tích kết quả</span>
          </h2>
          
          {analytics.submission_count === 0 ? (
            <p className="text-sm text-gray-500">Chưa có dữ liệu phân tích.</p>
          ) : (
            <div>
              {/* Tóm tắt điểm số */}
              <div className="grid grid-cols-4 gap-4 bg-gray-50 p-3 rounded-md mb-4 text-sm">
                <div>
                  <span className="text-gray-500 block text-xs font-semibold">Tổng số bài nộp</span>
                  <span className="font-bold text-gray-900 text-lg">{analytics.submission_count}</span>
                </div>
                <div>
                  <span className="text-gray-500 block text-xs font-semibold">Điểm trung bình</span>
                  <span className="font-bold text-gray-900 text-lg">
                    {analytics.score_summary.mean !== null ? analytics.score_summary.mean.toFixed(1) : "Chưa có bài nộp"}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block text-xs font-semibold">Điểm thấp nhất</span>
                  <span className="font-bold text-gray-900 text-lg">
                    {analytics.score_summary.min !== null ? analytics.score_summary.min.toFixed(1) : "Chưa có bài nộp"}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block text-xs font-semibold">Điểm cao nhất</span>
                  <span className="font-bold text-gray-900 text-lg">
                    {analytics.score_summary.max !== null ? analytics.score_summary.max.toFixed(1) : "Chưa có bài nộp"}
                  </span>
                </div>
              </div>

              {/* Bảng item-analysis */}
              <div className="overflow-x-auto border border-gray-100 rounded-md">
                <table className="w-full border-collapse text-left text-xs text-gray-700">
                  <thead>
                    <tr className="border-b bg-gray-100 font-semibold text-gray-600">
                      <th className="px-4 py-2">Câu (Part + Nội dung)</th>
                      <th className="px-4 py-2">Loại</th>
                      <th className="px-4 py-2">Đã trả lời</th>
                      <th className="px-4 py-2">Tỷ lệ đúng</th>
                      <th className="px-4 py-2">Phân bố lựa chọn</th>
                      <th className="px-4 py-2">Điểm trung bình AI</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {analytics.items.map((item) => {
                      let rateBadge = <span>—</span>;
                      if (item.correct_rate !== null) {
                        const rate = item.correct_rate;
                        let colorClass = "text-yellow-700 bg-yellow-50 ring-yellow-600/20";
                        let difficultyText = "Trung bình";
                        if (rate >= 0.9) {
                          colorClass = "text-green-700 bg-green-50 ring-green-600/20";
                          difficultyText = "Dễ";
                        } else if (rate <= 0.3) {
                          colorClass = "text-red-700 bg-red-50 ring-red-600/20";
                          difficultyText = "Khó";
                        }
                        const percent = Math.round(rate * 100);
                        rateBadge = (
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ring-1 ring-inset ${colorClass}`}>
                            {percent}% ({difficultyText})
                          </span>
                        );
                      }

                      // Format option distribution
                      let optDistStr = "—";
                      if (item.option_distribution && Object.keys(item.option_distribution).length > 0) {
                        optDistStr = Object.entries(item.option_distribution)
                          .map(([opt, cnt]) => `${opt}:${cnt}`)
                          .join(" ");
                      }

                      return (
                        <tr key={item.question_id} className="hover:bg-gray-50">
                          <td className="px-4 py-2 font-medium text-gray-900">
                            Part {item.part} - <span className="text-gray-500 font-normal">{item.content}</span>
                          </td>
                          <td className="px-4 py-2 capitalize">{item.type}</td>
                          <td className="px-4 py-2 tabular-nums">{item.answered_count}</td>
                          <td className="px-4 py-2 font-semibold">
                            {rateBadge}
                          </td>
                          <td className="px-4 py-2 text-gray-500 tabular-nums">{optDistStr}</td>
                          <td className="px-4 py-2 font-semibold text-emerald-700">
                            {item.avg_score !== null ? `${item.avg_score.toFixed(1)}/10` : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {error && (
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-8">
        {loading ? (
          <div className="text-sm text-gray-500">Đang tải danh sách bài nộp…</div>
        ) : submissions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 p-16 text-center text-sm text-gray-500 bg-white">
            Chưa có thí sinh nộp bài.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-xs">
            <table className="w-full border-collapse text-left text-sm text-gray-700">
              <thead>
                <tr className="border-b bg-gray-50 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  <th className="px-6 py-3">Thí sinh</th>
                  {isEssay ? (
                    <th className="px-6 py-3">Điểm Viết (AI)</th>
                  ) : (
                    <>
                      <th className="px-6 py-3">Điểm nghe</th>
                      <th className="px-6 py-3">Điểm đọc</th>
                    </>
                  )}
                  <th className="px-6 py-3">Tổng điểm</th>
                  <th className="px-6 py-3">Trạng thái</th>
                  <th className="px-6 py-3">Thời gian nộp</th>
                  <th className="px-6 py-3">Chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {submissions.map((sub) => {
                  const candidateName = sub.full_name ? `${sub.full_name} (${sub.username})` : sub.username;
                  const formattedDate = sub.submitted_at
                    ? new Date(sub.submitted_at).toLocaleString("vi-VN")
                    : "—";
                  
                  return (
                    <tr key={sub.submission_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 font-medium text-gray-900">{candidateName}</td>
                      {isEssay ? (
                        <td className="px-6 py-4 font-semibold text-emerald-700">
                          {sub.writing_score !== null && sub.writing_score !== undefined ? `${sub.writing_score} điểm` : "—"}
                        </td>
                      ) : (
                        <>
                          <td className="px-6 py-4">
                            {sub.listening_score !== null && sub.listening_score !== undefined ? sub.listening_score : "—"}
                          </td>
                          <td className="px-6 py-4">
                            {sub.reading_score !== null && sub.reading_score !== undefined ? sub.reading_score : "—"}
                          </td>
                        </>
                      )}
                      <td className="px-6 py-4 font-bold text-blue-600">
                        {sub.total_score !== null && sub.total_score !== undefined ? sub.total_score : "—"}
                      </td>
                      <td className="px-6 py-4">
                        {sub.status === "completed" ? (
                          <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                            Hoàn thành
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-700 ring-1 ring-inset ring-yellow-600/20">
                            {sub.status}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-500">{formattedDate}</td>
                      <td className="px-6 py-4">
                        <Link
                          href={`/submissions/${sub.submission_id}`}
                          className="text-sm font-semibold text-blue-600 hover:underline"
                        >
                          Xem
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
