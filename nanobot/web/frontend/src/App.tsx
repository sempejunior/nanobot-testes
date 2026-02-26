import { useEffect } from "react";
import { useStore } from "@/lib/store";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastContainer } from "@/components/ui/toast";
import { AuthPage } from "@/components/AuthPage";
import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";
import { CronPanel } from "@/components/CronPanel";
import { MemoryPanel } from "@/components/MemoryPanel";
import { SkillsPanel } from "@/components/SkillsPanel";
import { SettingsPanel } from "@/components/SettingsPanel";

function App() {
  const { user, authLoading, initAuth, cronOpen, setPanelState } = useStore();

  useEffect(() => {
    initAuth();
  }, [initAuth]);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-full bg-background">
        <div className="w-8 h-8 border-3 border-green/30 border-t-green rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <AuthPage />
        <ToastContainer />
      </>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex h-full bg-background">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 relative">
          <ChatArea />
        </div>
        <CronPanel open={cronOpen} onClose={() => setPanelState("cron", false)} />
        <MemoryPanel />
        <SkillsPanel />
        <SettingsPanel />
      </div>
      <ToastContainer />
    </ErrorBoundary>
  );
}

export default App;
