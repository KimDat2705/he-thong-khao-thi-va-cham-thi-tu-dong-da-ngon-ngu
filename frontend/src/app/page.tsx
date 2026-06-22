import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col items-start justify-center px-6 py-16">
      <h1 className="text-3xl font-bold">Hệ thống Khảo thí và Chấm thi Đa ngôn ngữ</h1>
      <p className="mt-1 text-sm font-medium text-blue-600">Phân hệ Tạo đề TOEIC (bản demo)</p>
      <p className="mt-2 text-gray-500">
        Nạp đề thật → ngân hàng câu hỏi → sinh đề TOEIC 200 câu → xem đề (ảnh, audio, ẩn đáp án).
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          href="/exams"
          className="rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Xem đề thi →
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-gray-300 hover:bg-gray-50 px-5 py-2.5 text-sm font-medium text-gray-700 transition-colors"
        >
          Đăng nhập
        </Link>
        <Link
          href="/admin"
          className="rounded-md bg-gray-100 hover:bg-gray-200 px-5 py-2.5 text-sm font-medium text-gray-700 transition-colors"
        >
          Vào quản trị →
        </Link>
      </div>

    </main>
  );
}
