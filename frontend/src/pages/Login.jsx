import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { fmtErr, roleHomePath } from "@/lib/api";
import Logo from "@/components/Logo";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (user) return <Navigate to={roleHomePath(user.role)} replace />;

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const u = await login(username.trim(), password);
      navigate(roleHomePath(u.role));
    } catch (e2) {
      setErr(fmtErr(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="min-h-screen w-full bg-cover bg-center relative flex items-center justify-center p-4 sm:p-8"
      style={{
        backgroundImage:
          "url('https://customer-assets-4nw71qhi.emergentagent.net/job_simple-enterprise-ai/artifacts/ye1u44gy_pic.jpg.jpeg')",
      }}
      data-testid="login-hero"
    >
      {/* Elegant gradient overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/60 via-white/40 to-emerald-900/30" />
      <div className="absolute inset-0 backdrop-blur-[2px]" />

      {/* Centered glass card */}
      <div className="relative z-10 w-full max-w-md">
        <div className="bg-white/85 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/60 px-8 py-10 sm:px-10 sm:py-12">
          {/* Brand */}
          <div className="flex flex-col items-center text-center mb-8">
            <Logo size={96} />
            <div className="mt-4 text-[11px] uppercase tracking-[0.22em] text-emerald-800/80 font-semibold">
              Internal Workspace
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-semibold text-gray-900 tracking-tight mt-4">
              Welcome back
            </h2>
            <p className="text-sm text-gray-600 mt-1.5">
              Sign in with your clinic credentials.
            </p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <label className="text-xs uppercase tracking-wider font-semibold text-gray-600 block mb-1.5">
                Username
              </label>
              <input
                type="text"
                className="w-full px-3.5 py-2.5 bg-white/90 border border-gray-200 rounded-md text-sm focus-ring"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                data-testid="login-username-input"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-wider font-semibold text-gray-600 block mb-1.5">
                Password
              </label>
              <input
                type="password"
                className="w-full px-3.5 py-2.5 bg-white/90 border border-gray-200 rounded-md text-sm focus-ring"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="login-password-input"
              />
            </div>

            {err && (
              <div
                className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2"
                data-testid="login-error"
              >
                {err}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white text-sm font-medium py-2.5 rounded-md transition-colors flex items-center justify-center gap-2 shadow-md"
              data-testid="login-submit-button"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              Sign in
            </button>
          </form>

          <div className="mt-8 text-xs text-gray-500 border-t border-gray-200/70 pt-5 text-center leading-relaxed">
            Trouble signing in? Contact the clinic administrator to reset your credentials.
          </div>
        </div>

        <p className="text-center text-[11px] text-white/90 mt-5 tracking-wide drop-shadow">
          © Sparsa Homeoclinic — Internal Workspace
        </p>
      </div>
    </div>
  );
}
