import React, { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import OnboardingPage from "./pages/OnboardingPage";
import ChatPage from "./pages/ChatPage";
import ProjectsPage from "./pages/ProjectsPage";
import MetricsPage from "./pages/MetricsPage";
import ProfilePage from "./pages/ProfilePage";
import Sidebar from "./components/Sidebar";
import WelcomeModal from "./components/WelcomeModal";

function App() {
  const { user, token, justCompletedOnboarding, clearJustCompletedOnboarding } = useAuth();
  const [page, setPage] = useState("chat");
  // Incrementado sempre que "Projetos" é clicado enquanto já ativo,
  // forçando o ProjectsPage a remontar e voltar para a lista principal.
  const [projectsResetKey, setProjectsResetKey] = useState(0);

  function handleSetPage(p: string) {
    if (p === "projects" && page === "projects") {
      setProjectsResetKey(k => k + 1);
    }
    setPage(p);
  }

  // Intercepta ?reset_token= na URL — mostra tela de redefinição de senha
  const params = new URLSearchParams(window.location.search);
  const resetToken = params.get("reset_token");
  if (resetToken) {
    return (
      <ResetPasswordPage
        token={resetToken}
        onDone={() => {
          window.history.replaceState({}, "", "/");
          window.location.reload();
        }}
      />
    );
  }

  if (!token || !user) return <LoginPage />;
  if (!user.onboarding_done) return <OnboardingPage />;

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar page={page} setPage={handleSetPage} />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {page === "chat"     && <ChatPage />}
        {page === "projects" && <ProjectsPage key={projectsResetKey} />}
        {page === "metrics"  && <MetricsPage />}
        {page === "profile"  && <ProfilePage onSaved={() => setPage("chat")} />}
      </main>
      {justCompletedOnboarding && (
        <WelcomeModal userName={user.name} onClose={clearJustCompletedOnboarding} />
      )}
    </div>
  );
}

export default function Root() {
  return <AuthProvider><App /></AuthProvider>;
}
