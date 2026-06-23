"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getMySubmissions, getToken, clearToken, type MySubmissionListItem } from "@/lib/api";

export default function MyResultsPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<MySubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const data = await getMySubmissions();
      setSubmissions(data);
      setError(null);
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
  };

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    setIsLoggedIn(true);
    fetchHistory();
  }, [router]);

  const handleLogout = () => {
    clearToken();
    setIsLoggedIn(false);
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Navigation Header */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10 px-6 py-3.5 shadow-sm">
        <div className="mx-auto max-w-5xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-xl font-bold text-gray-900 hover:text-blue-600 transition-colors">
              Hệ thống Khảo thí
            </Link>
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
              Thí sinh
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Link href="/exams" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Danh sách đề thi
            </Link>
            {isLoggedIn ? (
              <button
                onClick={handleLogout}
                className="rounded-md bg-gray-100 hover:bg-gray-200 px-3.5 py-1.5 text-sm font-semibold text-gray-700 transition-colors"
              >
                Đăng xuất
              </button>
            ) : (
              <Link
                href="/login"
                className="rounded-md bg-blue-600 hover:bg-blue-700 px-3.5 py-1.5 text-sm font-semibold text-white transition-colors"
              >
                Đăng nhập
              </Link>
            )}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="mx-auto max-w-5xl px-6 py-10 flex-1 w-full">
        <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Kết quả của tôi</h1>
            <p className="text-sm text-gray-500 mt-1">Lịch sử và điểm số các bài thi bạn đã nộp.</p>
          </div>
          <Link
            href="/exams"
            className="self-start sm:self-auto text-sm font-medium text-blue-600 hover:underline"
          >
            ← Quay lại danh sách đề thi
          </Link>
        </div>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 mb-6">
            Lỗi tải dữ liệu: {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-sm text-gray-500">Đang tải lịch sử làm bài...</div>
        ) : submissions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 p-20 text-center bg-white shadow-xs">
            <p className="text-sm text-gray-500 mb-4">Bạn chưa thực hiện bài thi nào.</p>
            <Link
              href="/exams"
              className="inline-flex items-center justify-center rounded-md bg-blue-600 hover:bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors"
            >
              Làm bài ngay
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {submissions.map((sub) => {
              const formattedDate = sub.submitted_at
                ? new Date(sub.submitted_at).toLocaleString("vi-VN")
                : "—";
              const isEssay = !!sub.exam_type && sub.exam_type.toUpperCase() !== "TOEIC";

              return (
                <div
                  key={sub.submission_id}
                  className="rounded-xl border border-gray-200 bg-white p-5 shadow-xs flex flex-col justify-between sm:flex-row sm:items-center gap-4"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-600">
                        {sub.exam_type ?? "Đề thi"}
                      </span>
                      <span className="text-xs text-gray-400">Bài nộp #{sub.submission_id}</span>
                    </div>
                    <h3 className="font-bold text-gray-900 text-lg leading-snug">{sub.exam_title}</h3>
                    <div className="text-xs text-gray-500 flex items-center gap-1.5 flex-wrap">
                      <span>Nộp lúc:</span>
                      <span className="font-medium text-gray-700">{formattedDate}</span>
                      <span>•</span>
                      <span>Trạng thái:</span>
                      {sub.status === "completed" ? (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                          Đã chấm xong
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-700 ring-1 ring-inset ring-yellow-600/20">
                          {sub.status}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 border-t border-gray-100 pt-4 sm:border-0 sm:pt-0 shrink-0">
                    {isEssay ? (
                      <div className="text-center">
                        <div className="text-xs text-gray-400 font-medium">Viết (AI)</div>
                        <div className="text-sm font-semibold text-emerald-700">
                          {sub.writing_score !== null && sub.writing_score !== undefined ? sub.writing_score : "—"}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="text-center">
                          <div className="text-xs text-gray-400 font-medium">Nghe</div>
                          <div className="text-sm font-semibold text-gray-700">
                            {sub.listening_score !== null && sub.listening_score !== undefined ? sub.listening_score : "—"}
                          </div>
                        </div>
                        <div className="w-px h-8 bg-gray-200"></div>
                        <div className="text-center">
                          <div className="text-xs text-gray-400 font-medium">Đọc</div>
                          <div className="text-sm font-semibold text-gray-700">
                            {sub.reading_score !== null && sub.reading_score !== undefined ? sub.reading_score : "—"}
                          </div>
                        </div>
                      </>
                    )}
                    <div className="w-px h-8 bg-gray-200"></div>
                    <div className="text-center">
                      <div className="text-xs text-gray-400 font-semibold">Tổng điểm</div>
                      <div className="text-lg font-bold text-blue-600">
                        {sub.total_score !== null && sub.total_score !== undefined ? sub.total_score : "—"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
