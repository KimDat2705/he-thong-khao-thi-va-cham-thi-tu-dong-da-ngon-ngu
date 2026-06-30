"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type QuestionRead,
  type BankStats,
  listBankQuestions,
  approveBankQuestions,
  getBankStats,
  enrichBankQuestions,
  getToken,
  clearToken,
} from "@/lib/api";

export default function BankAdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<BankStats | null>(null);
  const [questions, setQuestions] = useState<QuestionRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  // Filter states
  const [examType, setExamType] = useState<string>("TOEIC");
  const [status, setStatus] = useState<string>("draft");
  const [part, setPart] = useState<number | "">("");
  const [difficulty, setDifficulty] = useState<string>("");
  const [topic, setTopic] = useState<string>("");
  const [topicInput, setTopicInput] = useState<string>("");

  // Pagination states
  const [page, setPage] = useState<number>(1);
  const limit = 25;

  // Selection states
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // AI Enrichment states
  const [enrichPart, setEnrichPart] = useState<string>("1");
  const [enrichTopic, setEnrichTopic] = useState<string>("");
  const [enrichCount, setEnrichCount] = useState<number>(1);
  const [enriching, setEnriching] = useState<boolean>(false);

  // Guard authentication
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    setAuthChecked(true);
  }, [router]);

  // Fetch stats and questions
  async function fetchData() {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * limit;
      const qParams = {
        part: part === "" ? undefined : Number(part),
        status: status === "" ? undefined : status,
        difficulty: difficulty === "" ? undefined : difficulty,
        topic: topic === "" ? undefined : topic,
        exam_type: examType,
        limit,
        offset,
      };
      const [qData, sData] = await Promise.all([
        listBankQuestions(qParams),
        getBankStats(examType),
      ]);
      setQuestions(qData.items);
      setTotal(qData.total);
      setStats(sData);
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

  // Trigger fetch when parameters or page change, only if authenticated
  useEffect(() => {
    if (authChecked) {
      fetchData();
    }
  }, [part, status, difficulty, topic, page, examType, authChecked]);

  // Debounce topic input
  useEffect(() => {
    const handler = setTimeout(() => {
      setTopic(topicInput);
      setPage(1); // Reset to page 1 on search
    }, 300);
    return () => clearTimeout(handler);
  }, [topicInput]);

  // Checkbox handlers
  function toggleSelect(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const allOnPageSelected =
    questions.length > 0 && questions.every((q) => selectedIds.includes(q.id));

  function toggleSelectAll() {
    if (allOnPageSelected) {
      const pageIds = questions.map((q) => q.id);
      setSelectedIds((prev) => prev.filter((id) => !pageIds.includes(id)));
    } else {
      const pageIds = questions.map((q) => q.id);
      setSelectedIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    }
  }

  // Approval handler
  async function handleApprove() {
    if (selectedIds.length === 0) return;
    setApproving(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await approveBankQuestions(selectedIds);
      setSuccess(`Đã duyệt thành công ${res.updated} câu hỏi.`);
      setSelectedIds([]);
      await fetchData();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setApproving(false);
    }
  }

  // AI Enrichment handler
  async function handleEnrich() {
    setEnriching(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await enrichBankQuestions({
        count: enrichCount,
        part: enrichPart,
        topic: enrichTopic === "" ? undefined : enrichTopic,
      });
      setSuccess(`AI đã sinh thành công ${res.generated_count} câu hỏi/nhóm câu hỏi VSTEP B1 dạng Nháp.`);
      setExamType("VSTEP_B1");
      setStatus("draft");
      setPage(1);
      await fetchData();
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("401")) {
        clearToken();
        router.push("/login");
      } else {
        setError(errMsg);
      }
    } finally {
      setEnriching(false);
    }
  }

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 text-sm text-gray-500">
        Đang xác thực thông tin đăng nhập…
      </div>
    );
  }

  // Calculate quick stats totals
  let totalDraft = 0;
  let totalApproved = 0;
  if (stats) {
    for (const partStr in stats.question_counts) {
      const counts = stats.question_counts[partStr];
      totalDraft += counts.draft || 0;
      totalApproved += counts.approved || 0;
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Duyệt Ngân hàng Câu hỏi</h1>
        <button
          onClick={onLogout}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          Đăng xuất
        </button>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        Giáo viên duyệt câu hỏi từ trạng thái Draft sang Approved để cho phép sinh đề.
      </p>

      {/* Tabs navigation */}
      <div className="mt-4 flex gap-4 text-sm font-medium border-b border-gray-200 pb-1">
        <Link href="/admin" className="text-gray-500 hover:text-gray-700 pb-1">
          Quản trị đề thi
        </Link>
        <Link href="/admin/bank" className="text-blue-600 border-b-2 border-blue-600 pb-1 font-semibold">
          Duyệt ngân hàng câu hỏi
        </Link>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="mt-4 rounded-md border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Stats indicators */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <div className="text-xs font-medium text-yellow-800 uppercase tracking-wider">Tổng câu chưa duyệt (Draft)</div>
          <div className="mt-1 text-2xl font-semibold text-yellow-900">{loading && !stats ? "..." : totalDraft}</div>
        </div>
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <div className="text-xs font-medium text-green-800 uppercase tracking-wider">Tổng câu đã duyệt (Approved)</div>
          <div className="mt-1 text-2xl font-semibold text-green-900">{loading && !stats ? "..." : totalApproved}</div>
        </div>
      </div>

      {/* AI Question Enrichment Panel */}
      <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50/50 p-4">
        <h3 className="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-1.5">
          <span>✨</span> Tự động sinh câu hỏi bằng AI (Enrichment)
        </h3>
        <p className="text-xs text-blue-700 mb-4">
          Hệ thống sẽ gọi API Gemini để tự động sinh câu hỏi, đáp án, giải thích, ảnh minh hoạ (Imagen) và file âm thanh (TTS) theo đúng đặc tả Ma trận B1.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Chọn phần (Part)</label>
            <select
              value={enrichPart}
              onChange={(e) => setEnrichPart(e.target.value)}
              disabled={enriching}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            >
              <option value="1">Part 1: Đọc - Câu trắc nghiệm (R1)</option>
              <option value="2">Part 2: Đọc - Thông báo ngắn (R2)</option>
              <option value="3">Part 3: Đọc - Đoạn văn (R3)</option>
              <option value="4">Part 4: Đọc - Điền từ (R4)</option>
              <option value="5">Part 5: Viết - Viết lại câu (W1)</option>
              <option value="6">Part 6: Viết - Thư/luận (W2)</option>
              <option value="7">Part 7: Nghe - Chọn tranh (L1)</option>
              <option value="8">Part 8: Nghe - Điền thông tin (L2)</option>
              <option value="9">Part 9: Nói - Phỏng vấn (S1)</option>
              <option value="10">Part 10: Nói - Thảo luận giải pháp (S2)</option>
              <option value="11">Part 11: Nói - Phát triển chủ đề (S3)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Chủ đề (Topic)</label>
            <select
              value={enrichTopic}
              onChange={(e) => setEnrichTopic(e.target.value)}
              disabled={enriching}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            >
              <option value="">Ngẫu nhiên</option>
              <option value="Bản thân">Bản thân</option>
              <option value="Nhà cửa-gia đình-môi trường">Nhà cửa - Gia đình - Môi trường</option>
              <option value="Cuộc sống hằng ngày">Cuộc sống hằng ngày</option>
              <option value="Vui chơi-giải trí">Vui chơi - Giải trí</option>
              <option value="Đi lại-du lịch">Đi lại - Du lịch</option>
              <option value="Mối quan hệ">Mối quan hệ</option>
              <option value="Sức khỏe">Sức khỏe</option>
              <option value="Giáo dục">Giáo dục</option>
              <option value="Mua bán">Mua bán</option>
              <option value="Thực phẩm-đồ uống">Thực phẩm - Đồ uống</option>
              <option value="Các dịch vụ">Các dịch vụ</option>
              <option value="Địa điểm-địa danh">Địa điểm - Địa danh</option>
              <option value="Ngôn ngữ">Ngôn ngữ</option>
              <option value="Thời tiết">Thời tiết</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Số lượng sinh (Tối đa 5)</label>
            <input
              type="number"
              min={1}
              max={5}
              value={enrichCount}
              onChange={(e) => setEnrichCount(Math.min(5, Math.max(1, Number(e.target.value))))}
              disabled={enriching}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={handleEnrich}
              disabled={enriching}
              className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-blue-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {enriching ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span>Đang sinh...</span>
                </>
              ) : (
                <span>AI Sinh Câu Hỏi</span>
              )}
            </button>
          </div>
        </div>
        {enriching && (
          <p className="text-[11px] text-blue-600 mt-2 italic animate-pulse">
            * AI đang làm việc (sinh văn bản, tạo ảnh Imagen & đọc phát âm TTS nếu là phần nghe). Quá trình này có thể tốn từ 10-30 giây tùy tốc độ mạng của API Gemini...
          </p>
        )}
      </div>

      {/* Filters Form */}
      <div className="mt-6 rounded-lg border bg-gray-50 p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Bộ lọc tìm kiếm</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Loại đề thi</label>
            <select
              value={examType}
              onChange={(e) => {
                setExamType(e.target.value);
                setPart("");
                setPage(1);
                setSelectedIds([]);
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="TOEIC">TOEIC</option>
              <option value="VSTEP_B1">VSTEP B1</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Trạng thái</label>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
                setSelectedIds([]);
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="draft">Draft (Nháp)</option>
              <option value="approved">Approved (Đã duyệt)</option>
              <option value="">Tất cả trạng thái</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Part</label>
            <select
              value={part}
              onChange={(e) => {
                setPart(e.target.value === "" ? "" : Number(e.target.value));
                setPage(1);
                setSelectedIds([]);
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Tất cả parts</option>
              {examType === "TOEIC" ? (
                <>
                  <option value="1">Part 1</option>
                  <option value="2">Part 2</option>
                  <option value="3">Part 3</option>
                  <option value="4">Part 4</option>
                  <option value="5">Part 5</option>
                  <option value="6">Part 6</option>
                  <option value="7">Part 7</option>
                </>
              ) : (
                <>
                  <option value="1">Part 1: Đọc - Câu đơn (R1)</option>
                  <option value="2">Part 2: Đọc - Thông báo ngắn (R2)</option>
                  <option value="3">Part 3: Đọc - Đoạn văn (R3)</option>
                  <option value="4">Part 4: Đọc - Điền từ (R4)</option>
                  <option value="5">Part 5: Viết - Viết lại câu (W1)</option>
                  <option value="6">Part 6: Viết - Thư/luận (W2)</option>
                  <option value="7">Part 7: Nghe - Chọn tranh (L1)</option>
                  <option value="8">Part 8: Nghe - Điền thông tin (L2)</option>
                  <option value="9">Part 9: Nói - Phỏng vấn (S1)</option>
                  <option value="10">Part 10: Nói - Thảo luận giải pháp (S2)</option>
                  <option value="11">Part 11: Nói - Phát triển chủ đề (S3)</option>
                </>
              )}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Độ khó</label>
            <select
              value={difficulty}
              onChange={(e) => {
                setDifficulty(e.target.value);
                setPage(1);
                setSelectedIds([]);
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Tất cả độ khó</option>
              <option value="easy">Easy (Dễ)</option>
              <option value="medium">Medium (Trung bình)</option>
              <option value="hard">Hard (Khó)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Chủ đề (Topic)</label>
            <input
              type="text"
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              placeholder="Nhập chủ đề..."
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Bulk action bar */}
      {selectedIds.length > 0 && (
        <div className="mt-4 flex items-center justify-between rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-600 animate-pulse"></span>
            <span className="font-medium text-blue-700">Đã chọn {selectedIds.length} câu hỏi</span>
          </div>
          <button
            onClick={handleApprove}
            disabled={approving}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-50"
          >
            {approving ? "Đang duyệt..." : "Duyệt câu đã chọn"}
          </button>
        </div>
      )}

      {/* Table of questions */}
      <div className="mt-6 overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-gray-500 font-medium">
              <th className="py-3 pl-4 w-12 text-center">
                <input
                  type="checkbox"
                  checked={allOnPageSelected}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              </th>
              <th className="py-3 px-3 w-16">ID</th>
              <th className="py-3 px-3 w-20">Part</th>
              <th className="py-3 px-3 w-32">Topic</th>
              <th className="py-3 px-3 w-24">Độ khó</th>
              <th className="py-3 px-3">Nội dung</th>
              <th className="py-3 px-3 w-28 text-right pr-4">Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {loading && questions.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-500">Đang tải câu hỏi...</td>
              </tr>
            ) : questions.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-500">Không tìm thấy câu hỏi nào.</td>
              </tr>
            ) : (
              questions.map((q) => {
                const isSelected = selectedIds.includes(q.id);
                return (
                  <tr
                    key={q.id}
                    className={`border-b transition hover:bg-gray-50 ${
                      isSelected ? "bg-blue-50/30" : ""
                    }`}
                  >
                    <td className="py-3 pl-4 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(q.id)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </td>
                    <td className="py-3 px-3 font-semibold text-gray-700">#{q.id}</td>
                    <td className="py-3 px-3">
                      <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                        Part {q.part}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-gray-600 max-w-[120px] truncate" title={q.topic ?? ""}>
                      {q.topic || <span className="text-gray-400 font-light italic">None</span>}
                    </td>
                    <td className="py-3 px-3">
                      {q.difficulty === "easy" && (
                        <span className="rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-700 border border-green-200">Easy</span>
                      )}
                      {q.difficulty === "medium" && (
                        <span className="rounded bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 border border-blue-200">Medium</span>
                      )}
                      {q.difficulty === "hard" && (
                        <span className="rounded bg-orange-50 px-2 py-1 text-xs font-medium text-orange-700 border border-orange-200">Hard</span>
                      )}
                      {!q.difficulty && (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-3 max-w-md">
                      <div className="font-medium text-gray-800 line-clamp-2" title={q.content}>
                        {q.content}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right pr-4">
                      {q.status === "approved" ? (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                          Approved
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20">
                          Draft
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {total > 0 && (
        <div className="mt-6 flex items-center justify-between border-t border-gray-200 pt-4">
          <div className="text-sm text-gray-500">
            Hiển thị <span className="font-medium">{(page - 1) * limit + 1}</span> -{" "}
            <span className="font-medium">{Math.min(page * limit, total)}</span> trong tổng số{" "}
            <span className="font-medium">{total}</span> câu hỏi
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || loading}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Trang trước
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * limit >= total || loading}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Trang sau
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
