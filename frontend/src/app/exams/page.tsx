"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ExamSummary, listExams, getToken, clearToken } from "@/lib/api";

export default function ExamsPage() {
  const router = useRouter();
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const fetchExams = async () => {
    setLoading(true);
    try {
      const data = await listExams();
      setExams(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setIsLoggedIn(!!getToken());
    fetchExams();
  }, []);

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
            <Link href="/" className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Trang chủ
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
        <div className="mb-8">
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Danh sách đề thi khả dụng</h1>
          <p className="text-sm text-gray-500 mt-1">Chọn đề thi bên dưới để bắt đầu làm bài hoặc xem cấu trúc đề.</p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 mb-6">
            Lỗi tải dữ liệu: {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-sm text-gray-500">Đang tải danh sách đề thi...</div>
        ) : exams.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 p-20 text-center text-sm text-gray-500 bg-white">
            Hiện không có đề thi nào được phát hành.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {exams.map((exam) => (
              <div
                key={exam.id}
                className="rounded-xl border border-gray-200 bg-white p-5 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-600">
                      {exam.exam_type}
                    </span>
                    <span className="text-xs text-gray-400">ID: {exam.id}</span>
                  </div>
                  <h3 className="mt-3 font-bold text-gray-900 text-lg leading-snug line-clamp-2">{exam.title}</h3>
                  <div className="mt-3 text-sm text-gray-500 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <span>⏱️ Thời lượng:</span>
                      <span className="font-semibold text-gray-700">{exam.duration_minutes} phút</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span>📝 Số câu hỏi:</span>
                      <span className="font-semibold text-gray-700">{exam.question_count} câu</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex gap-2 border-t border-gray-100 pt-4">
                  <Link
                    href={`/exam/${exam.id}/take`}
                    className="flex-1 text-center rounded-md bg-blue-600 hover:bg-blue-700 py-2 text-xs font-semibold text-white transition-colors"
                  >
                    Làm bài →
                  </Link>
                  <Link
                    href={`/exam/${exam.id}`}
                    className="flex-1 text-center rounded-md border border-gray-200 hover:bg-gray-50 py-2 text-xs font-semibold text-gray-700 transition-colors"
                  >
                    Xem cấu trúc
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
