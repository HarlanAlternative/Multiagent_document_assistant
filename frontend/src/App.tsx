import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { WorkspaceProvider, useWorkspace } from "./components/layout/WorkspaceProvider";
import { EmptyState } from "./components/common/EmptyState";
import { ChatPage } from "./pages/ChatPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <WorkspaceProvider>
      <AppRoutes />
    </WorkspaceProvider>
  );
}

function AppRoutes() {
  const location = useLocation();
  const { llmSettingsQuery } = useWorkspace();

  if (llmSettingsQuery.isLoading) {
    return (
      <AppShell>
        <EmptyState title="Loading workspace" description="Fetching project and model configuration before rendering the app." />
      </AppShell>
    );
  }

  const requiresSetup = llmSettingsQuery.data?.is_configured === false && location.pathname !== "/settings";
  if (requiresSetup) {
    return (
      <AppShell>
        <Navigate to="/settings" replace />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to={requiresSetup ? "/settings" : "/chat"} replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to={requiresSetup ? "/settings" : "/chat"} replace />} />
      </Routes>
    </AppShell>
  );
}
