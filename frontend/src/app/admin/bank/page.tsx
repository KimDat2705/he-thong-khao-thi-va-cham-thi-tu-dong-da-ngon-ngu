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
  enrichBankQuestionsAsync,
  getEnrichTask,
  paraphraseBankQuestion,
  getToken,
  clearToken,
  audioSrc,
  imageSrc,
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
  const [examType, setExamType] = useState<string>("VSTEP_B1");
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
  const [selectedQuestion, setSelectedQuestion] = useState<QuestionRead | null>(null);

  // AI Enrichment states
  const [enrichPart, setEnrichPart] = useState<string>("1");
  const [enrichTopic, setEnrichTopic] = useState<string>("");
  const [enrichCount, setEnrichCount] = useState<number>(1);
  const [enrichDifficulty, setEnrichDifficulty] = useState<string>("");
  const [enriching, setEnriching] = useState<boolean>(false);
  const [enrichProgress, setEnrichProgress] = useState<string>("");

  // BANK-007 paraphrase states
  const [paraphrasing, setParaphrasing] = useState<boolean>(false);
  const [paraphraseCount, setParaphraseCount] = useState<number>(3);

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

  // AI Enrichment handler (SPEC-BANK-006): gửi job bất đồng bộ rồi poll tiến độ —
  // cho phép sinh lô lớn (tới 50 câu) mà không bị timeout HTTP.
  async function handleEnrich() {
    setEnriching(true);
    setError(null);
    setSuccess(null);
    setEnrichProgress("Đang gửi yêu cầu tới AI...");
    try {
      const { job_id } = await enrichBankQuestionsAsync({
        count: enrichCount,
        part: enrichPart,
        topic: enrichTopic === "" ? undefined : enrichTopic,
        difficulty: enrichDifficulty === "" ? undefined : enrichDifficulty,
      });

      // Poll cho tới khi job xong (hoặc lỗi / quá thời gian chờ). Job vẫn chạy nền
      // phía server nếu client bỏ đi — câu nháp sẽ xuất hiện khi hoàn tất.
      const maxAttempts = 120; // 120 * 2.5s = 5 phút
      let generated = 0;
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const task = await getEnrichTask(job_id);
        if (task.status === "completed") {
          generated = task.generated_count;
          break;
        }
        if (task.status === "error") {
          throw new Error(task.error || "AI sinh câu hỏi thất bại.");
        }
        setEnrichProgress(
          `AI đang xử lý nền... (${task.status}, đã sinh ${task.generated_count}/${task.requested})`,
        );
        if (attempt === maxAttempts - 1) {
          throw new Error(
            "Quá thời gian chờ. Job vẫn đang chạy nền — kiểm tra lại danh sách Nháp sau ít phút.",
          );
        }
      }

      setSuccess(`AI đã sinh thành công ${generated} câu hỏi/nhóm câu hỏi VSTEP B1 dạng Nháp.`);
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
      setEnrichProgress("");
    }
  }

  // BANK-007: nhân bản (paraphrase) một câu trắc nghiệm sẵn có thành N biến thể nháp.
  async function handleParaphrase(seedId: number) {
    setParaphrasing(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await paraphraseBankQuestion({ seed_question_id: seedId, count: paraphraseCount });
      setSuccess(
        `AI đã nhân bản ${res.generated_count} biến thể nháp từ câu #${seedId} ` +
        `(viết lại đề + phương án, giữ điểm ngữ pháp & đáp án, tránh trùng bản quyền).`,
      );
      setSelectedQuestion(null);
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
      setParaphrasing(false);
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
        Bấm vào một câu trắc nghiệm để xem chi tiết và <span className="font-medium text-purple-700">🧬 Nhân bản (AI Paraphrase)</span> thành biến thể mới.
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-5">
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
            <label className="block text-xs font-medium text-gray-500 uppercase">Số lượng sinh (Tối đa 50)</label>
            <input
              type="number"
              min={1}
              max={50}
              value={enrichCount}
              onChange={(e) => setEnrichCount(Math.min(50, Math.max(1, Number(e.target.value))))}
              disabled={enriching}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase">Độ khó (Difficulty)</label>
            <select
              value={enrichDifficulty}
              onChange={(e) => setEnrichDifficulty(e.target.value)}
              disabled={enriching}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            >
              <option value="">Ngẫu nhiên (AI chọn)</option>
              <option value="easy">Dễ (Easy)</option>
              <option value="medium">Trung bình (Medium)</option>
              <option value="hard">Khó (Hard)</option>
            </select>
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
            {enrichProgress || "* AI đang xử lý nền..."} Sinh lô lớn (tới 50 câu, kèm ảnh Imagen & phát âm TTS cho phần nghe) có thể mất vài phút; câu nháp sẽ xuất hiện khi hoàn tất.
          </p>
        )}
      </div>

      {/* Filters Form */}
      <div className="mt-6 rounded-lg border bg-gray-50 p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Bộ lọc tìm kiếm</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">

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
                    <td className="py-3 px-3 font-semibold text-gray-700">
                      <button
                        onClick={() => setSelectedQuestion(q)}
                        className="text-blue-600 hover:underline hover:text-blue-800 focus:outline-none"
                        title="Xem chi tiết"
                      >
                        #{q.id}
                      </button>
                    </td>
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
                      <button
                        onClick={() => setSelectedQuestion(q)}
                        className="text-left font-medium text-gray-800 line-clamp-2 hover:text-blue-600 transition focus:outline-none"
                        title="Bấm để xem chi tiết câu hỏi"
                      >
                        {q.content}
                      </button>
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

      {/* Question Detail Modal */}
      {selectedQuestion && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-3xl rounded-xl bg-white shadow-2xl border border-gray-100 flex flex-col max-h-[85vh] overflow-hidden transform transition duration-300 scale-100 text-left">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-6 py-4 bg-gray-50/80">
              <div>
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  Chi tiết câu hỏi <span className="text-blue-600 font-mono">#{selectedQuestion.id}</span>
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Part {selectedQuestion.part} • Topic: {selectedQuestion.topic || "N/A"} • Độ khó: {selectedQuestion.difficulty || "N/A"}
                </p>
              </div>
              <button
                onClick={() => setSelectedQuestion(null)}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition focus:outline-none"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {/* Badges Info */}
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded bg-blue-100 px-2.5 py-1 font-semibold text-blue-800">
                  Part {selectedQuestion.part}
                </span>
                <span className={`rounded px-2.5 py-1 font-semibold border ${
                  selectedQuestion.difficulty === "easy" ? "bg-green-50 text-green-700 border-green-200" :
                  selectedQuestion.difficulty === "medium" ? "bg-blue-50 text-blue-700 border-blue-200" :
                  "bg-orange-50 text-orange-700 border-orange-200"
                }`}>
                  Độ khó: {selectedQuestion.difficulty?.toUpperCase()}
                </span>
                {selectedQuestion.clo && (
                  <span className="rounded bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700 border border-indigo-200">
                    CLO: {selectedQuestion.clo}
                  </span>
                )}
                <span className={`rounded-full px-2.5 py-1 font-semibold text-xs border ${
                  selectedQuestion.status === "approved" ? "bg-green-100 text-green-800 border-green-200" : "bg-amber-100 text-amber-800 border-amber-200"
                }`}>
                  {selectedQuestion.status === "approved" ? "Approved" : "Draft (Nháp)"}
                </span>
              </div>

              {/* Group Passage / Reading passage */}
              {selectedQuestion.group_passage && (
                <div className="rounded-lg border bg-gray-50/50 p-4 space-y-2">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Bài đọc / Ngữ cảnh chung</h4>
                  <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-sans bg-white p-3 rounded border">
                    {selectedQuestion.group_passage}
                  </div>
                </div>
              )}

              {/* Audio Player */}
              {(selectedQuestion.audio_url || selectedQuestion.group_audio_url) && (
                <div className="rounded-lg border bg-blue-50/30 p-4 space-y-2">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">File âm thanh (Listening)</h4>
                  <audio
                    src={audioSrc(selectedQuestion.audio_url || selectedQuestion.group_audio_url) || ""}
                    controls
                    className="w-full mt-1"
                  />
                </div>
              )}

              {/* Question Content */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Nội dung câu hỏi</h4>
                <p className="text-base font-semibold text-gray-900 bg-gray-50/20 p-3 rounded border">
                  {selectedQuestion.content}
                </p>
              </div>

              {/* Image Graphics (Part 7 Tranh) */}
              {(selectedQuestion.image_url || selectedQuestion.group_image_url) && (
                <div className="rounded-lg border p-4 space-y-2">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Hình ảnh minh họa</h4>
                  <div className="flex flex-wrap gap-3 justify-center">
                    {(selectedQuestion.image_url || selectedQuestion.group_image_url)?.split(",").map((url, i) => (
                      <div key={i} className="border rounded overflow-hidden shadow-sm bg-gray-50 flex flex-col items-center">
                        <img
                          src={imageSrc(url) || ""}
                          alt={`Minh họa ${i+1}`}
                          className="max-h-48 object-contain"
                        />
                        {((selectedQuestion.image_url || selectedQuestion.group_image_url)?.split(",").length ?? 0) > 1 && (
                          <span className="text-xs font-semibold py-1 bg-gray-100 w-full text-center text-gray-600 border-t">
                            Hình ảnh {String.fromCharCode(65 + i)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Options & Reference Answer */}
              {selectedQuestion.options && Object.keys(selectedQuestion.options).length > 0 ? (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Các phương án lựa chọn</h4>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {Object.entries(selectedQuestion.options).map(([key, val]) => {
                      const isCorrect = key === selectedQuestion.reference_answer;
                      return (
                        <div
                          key={key}
                          className={`flex items-start gap-3 rounded-lg border p-3 transition ${
                            isCorrect
                              ? "bg-green-50 border-green-300 text-green-950 font-medium"
                              : "bg-white border-gray-200 text-gray-700"
                          }`}
                        >
                          <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                            isCorrect ? "bg-green-600 text-white" : "bg-gray-100 text-gray-600"
                          }`}>
                            {key}
                          </span>
                          <span className="text-sm pt-0.5">{val}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : selectedQuestion.reference_answer ? (
                <div className="rounded-lg border bg-green-50/30 p-4 space-y-2 border-green-100">
                  <h4 className="text-xs font-bold text-green-700 uppercase tracking-wider">Đáp án mẫu / Đúng</h4>
                  <p className="text-sm font-semibold text-green-900 bg-white p-3 rounded border border-green-200 whitespace-pre-wrap leading-relaxed">
                    {selectedQuestion.reference_answer}
                  </p>
                </div>
              ) : null}

              {/* Explanation */}
              {selectedQuestion.explanation && (
                <div className="rounded-lg border bg-yellow-50/20 p-4 space-y-2 border-yellow-100">
                  <h4 className="text-xs font-bold text-yellow-700 uppercase tracking-wider">Giải thích đáp án</h4>
                  <p className="text-sm text-gray-700 bg-white p-3 rounded border border-yellow-200 whitespace-pre-wrap leading-relaxed">
                    {selectedQuestion.explanation}
                  </p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t px-6 py-4 bg-gray-50 flex flex-wrap items-center justify-between gap-3">
              {/* BANK-007: Nhân bản (Paraphrase) — chỉ cho câu trắc nghiệm có phương án */}
              {selectedQuestion.type === "choice" &&
              selectedQuestion.options &&
              Object.keys(selectedQuestion.options).length >= 2 ? (
                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-gray-500">Số biến thể</label>
                  <select
                    value={paraphraseCount}
                    onChange={(e) => setParaphraseCount(Number(e.target.value))}
                    disabled={paraphrasing}
                    className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:bg-gray-100"
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleParaphrase(selectedQuestion.id)}
                    disabled={paraphrasing}
                    title="AI viết lại câu này thành các biến thể nháp mới (giữ điểm ngữ pháp + đáp án, sinh ảnh mới cho câu tranh, tránh trùng bản quyền)"
                    className="rounded-lg bg-purple-600 hover:bg-purple-700 px-4 py-2 text-sm font-semibold text-white shadow transition focus:outline-none disabled:bg-purple-300 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {paraphrasing ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <span>Đang nhân bản...</span>
                      </>
                    ) : (
                      <span>🧬 Nhân bản AI (Paraphrase)</span>
                    )}
                  </button>
                </div>
              ) : (
                <span className="text-xs text-gray-400 italic">
                  Chỉ nhân bản (paraphrase) được câu trắc nghiệm có phương án.
                </span>
              )}
              <button
                onClick={() => setSelectedQuestion(null)}
                disabled={paraphrasing}
                className="rounded-lg bg-gray-900 hover:bg-gray-800 px-5 py-2 text-sm font-semibold text-white shadow transition focus:outline-none disabled:opacity-50"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
