import { useState } from "react";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Bot, LogIn, UserPlus } from "lucide-react";

export function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [userId, setUserId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const { login, register, authLoading, authError } = useStore();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) return;
    if (mode === "login") {
      login(userId.trim());
    } else {
      register(userId.trim(), displayName.trim() || undefined, email.trim() || undefined);
    }
  };

  return (
    <div className="flex h-full bg-background">
      {/* Left side - Branding (hidden on mobile) */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-gradient-to-br from-[#0D1117] via-[#0f1a14] to-[#0D1117] items-center justify-center">
        {/* Decorative orbs */}
        <div className="absolute top-1/4 left-1/4 w-64 h-64 rounded-full bg-green/10 blur-3xl animate-float-orb" />
        <div className="absolute bottom-1/3 right-1/4 w-48 h-48 rounded-full bg-green/8 blur-3xl animate-float-orb-delayed" />
        <div className="absolute top-2/3 left-1/3 w-32 h-32 rounded-full bg-green/5 blur-3xl animate-float-orb-slow" />

        <div className="relative z-10 flex flex-col items-center text-center px-12">
          <div className="w-24 h-24 rounded-3xl bg-green/10 border border-green/20 flex items-center justify-center mb-8 shadow-[0_0_40px_rgba(17,199,111,0.2)]">
            <Bot className="w-12 h-12 text-green" />
          </div>
          <h1 className="text-4xl font-bold text-text-primary mb-3 tracking-tight">nanobot</h1>
          <p className="text-lg text-text-secondary font-light">AI Agent Platform</p>
          <div className="mt-8 w-16 h-px bg-gradient-to-r from-transparent via-green/40 to-transparent" />
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          {/* Mobile logo (visible only on small screens) */}
          <div className="flex flex-col items-center mb-8 lg:hidden">
            <div className="w-14 h-14 rounded-2xl bg-green/10 border border-green/20 flex items-center justify-center mb-3 shadow-[0_0_30px_rgba(17,199,111,0.15)]">
              <Bot className="w-7 h-7 text-green" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">nanobot</h1>
          </div>

          {/* Glass card */}
          <div className="backdrop-blur-xl bg-white/[0.03] rounded-2xl border border-white/[0.06] p-8 shadow-[0_0_40px_rgba(0,0,0,0.3)]">
            {/* Tab toggle */}
            <div className="flex rounded-xl bg-white/[0.04] border border-white/[0.06] p-1 mb-8">
              <button
                onClick={() => setMode("login")}
                className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 cursor-pointer ${
                  mode === "login"
                    ? "bg-green text-black shadow-[0_0_15px_rgba(17,199,111,0.3)]"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Login
              </button>
              <button
                onClick={() => setMode("register")}
                className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 cursor-pointer ${
                  mode === "register"
                    ? "bg-green text-black shadow-[0_0_15px_rgba(17,199,111,0.3)]"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm text-text-secondary mb-2 font-medium">
                  User ID
                </label>
                <Input
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter your user ID"
                  autoFocus
                />
              </div>

              {mode === "register" && (
                <>
                  <div>
                    <label className="block text-sm text-text-secondary mb-2 font-medium">
                      Display Name
                    </label>
                    <Input
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Your name (optional)"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-text-secondary mb-2 font-medium">
                      Email
                    </label>
                    <Input
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="your@email.com (optional)"
                      type="email"
                    />
                  </div>
                </>
              )}

              {authError && (
                <div className="rounded-lg bg-red-muted/50 border border-red/20 px-4 py-3 text-sm text-red">
                  {authError}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={authLoading || !userId.trim()}
              >
                {authLoading ? (
                  <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                ) : mode === "login" ? (
                  <>
                    <LogIn className="w-4 h-4 mr-2" />
                    Sign In
                  </>
                ) : (
                  <>
                    <UserPlus className="w-4 h-4 mr-2" />
                    Create Account
                  </>
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
