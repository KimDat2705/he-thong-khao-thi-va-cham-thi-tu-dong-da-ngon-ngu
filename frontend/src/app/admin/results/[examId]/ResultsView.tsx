"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getExam,
  getExamSubmissions,
  getToken,
  clearToken,
  type SubmissionListItem,
} from "@/lib/api";

interface ResultsViewProps {
  examId: string;
}

export default function ResultsView({ examId }: ResultsViewProps) {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [examTitle, setExamTitle] = useState<string>(`Kết quả đề #${examId}`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

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
        } catch (titleErr) {
          console.warn("Failed to fetch exam title, falling back:", titleErr);
          // Keep default fallback title: "Kết quả đề #{examId}"
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
      </div>

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
                  <th className="px-6 py-3">Điểm nghe</th>
                  <th className="px-6 py-3">Điểm đọc</th>
                  <th className="px-6 py-3">Tổng điểm</th>
                  <th className="px-6 py-3">Trạng thái</th>
                  <th className="px-6 py-3">Thời gian nộp</th>
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
                      <td className="px-6 py-4">
                        {sub.listening_score !== null && sub.listening_score !== undefined ? sub.listening_score : "—"}
                      </td>
                      <td className="px-6 py-4">
                        {sub.reading_score !== null && sub.reading_score !== undefined ? sub.reading_score : "—"}
                      </td>
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
