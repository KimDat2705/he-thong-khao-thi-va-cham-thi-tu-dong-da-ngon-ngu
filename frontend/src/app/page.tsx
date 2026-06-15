import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col items-start justify-center px-6 py-16">
      <h1 className="text-3xl font-bold">Hệ thống Khảo thí TOEIC</h1>
      <p className="mt-2 text-gray-500">
        Demo: nạp đề thật → ngân hàng câu hỏi → sinh đề TOEIC 200 câu → xem đề.
      </p>
      <Link
        href="/admin"
        className="mt-6 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        Vào trang quản trị →
      </Link>
    </main>
  );
}
