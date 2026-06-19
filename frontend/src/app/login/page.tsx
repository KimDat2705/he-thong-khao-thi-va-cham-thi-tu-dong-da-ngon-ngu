"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { loginRequest, setToken, getToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // If already logged in, redirect to admin
  useEffect(() => {
    if (getToken()) {
      router.push("/admin");
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) {
      setError("Vui lòng điền đầy đủ tên đăng nhập và mật khẩu.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await loginRequest(username, password);
      setToken(res.access_token);
      router.push("/admin");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("401")) {
        setError("Tên đăng nhập hoặc mật khẩu không chính xác.");
      } else {
        setError(msg || "Đã xảy ra lỗi khi đăng nhập.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-radial from-gray-900 via-gray-950 to-black px-6 py-12">
      {/* Sleek card container */}
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl shadow-2xl">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight text-white bg-clip-text bg-linear-to-r from-blue-400 to-indigo-400">
            Hệ thống khảo thí
          </h2>
          <p className="mt-2 text-sm text-gray-400">
            Đăng nhập tài khoản Giáo viên hoặc Quản trị viên
          </p>
        </div>

        {error && (
          <div className="mt-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <form className="mt-6 space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="username" className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Tên đăng nhập
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              className="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-gray-500 shadow-xs outline-hidden focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              placeholder="Nhập tên đăng nhập..."
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Mật khẩu
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              className="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-gray-500 shadow-xs outline-hidden focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              placeholder="Nhập mật khẩu..."
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-linear-to-r from-blue-600 to-indigo-600 py-2.5 text-sm font-semibold text-white shadow-md hover:from-blue-500 hover:to-indigo-500 focus:outline-hidden disabled:opacity-50"
          >
            {loading ? "Đang xử lý..." : "Đăng nhập"}
          </button>
        </form>
      </div>
    </div>
  );
}
