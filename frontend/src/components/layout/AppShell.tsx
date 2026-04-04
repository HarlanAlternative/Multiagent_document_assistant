import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { API_BASE_URL } from "../../api/client";
import { useHealth } from "../../hooks/useHealth";
import { getStatusTone } from "../../lib/utils";
import { useWorkspace } from "./WorkspaceProvider";
import { Badge } from "../common/Badge";
import { Panel } from "../common/Panel";

const navItems = [
  { label: "Chat", to: "/chat" },
  { label: "Documents", to: "/documents" },
  { label: "Settings", to: "/settings" },
];

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const healthQuery = useHealth();
  const { currentProject, projects, selectedProjectId, setSelectedProjectId, llmSettingsQuery, searchSettingsQuery } = useWorkspace();

  return (
    <div className="min-h-screen bg-surface-gradient text-ink-900">
      <div className="mx-auto flex min-h-screen w-full max-w-[1880px] flex-col px-4 py-6 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">
        <header className="mb-6 rounded-3xl border border-white/70 bg-white/90 p-4 shadow-panel">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-signal-700">Portfolio-ready AI system</p>
              <h1 className="mt-2 text-2xl font-semibold text-ink-900">Multi-Agent Personal Knowledge Copilot</h1>
              <p className="mt-1 text-sm text-ink-600">
                Private-document retrieval, source-grounded QA, and document lifecycle management.
              </p>
            </div>

            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <div className="rounded-2xl bg-ink-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-500">Current project</p>
                <div className="mt-2 flex items-center gap-2">
                  <select
                    value={selectedProjectId ?? ""}
                    onChange={(event) => setSelectedProjectId(event.target.value)}
                    className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800"
                  >
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                  {currentProject ? <Badge label={currentProject.name} tone="info" /> : null}
                </div>
              </div>

              <div className="rounded-2xl bg-ink-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-500">Backend</p>
                <div className="mt-1 flex items-center gap-2">
                  <Badge
                    label={healthQuery.data?.status === "ok" ? "Online" : healthQuery.isError ? "Offline" : "Checking"}
                    tone={getStatusTone(healthQuery.data?.status ?? (healthQuery.isError ? "failed" : "processing"))}
                  />
                  <span className="text-sm text-ink-600">{healthQuery.data?.vector_store ?? "Unavailable"}</span>
                </div>
                {healthQuery.data ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge label={`router:${healthQuery.data.router_provider ?? "unknown"}`} />
                    <Badge label={`answer:${healthQuery.data.answer_provider ?? "unknown"}`} />
                    <Badge label={`embed:${healthQuery.data.embedding_provider ?? "unknown"}`} />
                    <Badge label={`search:${healthQuery.data.search_enabled ? healthQuery.data.search_provider ?? "on" : "off"}`} />
                    {healthQuery.data.chat_model ? <Badge label={healthQuery.data.chat_model} tone="info" /> : null}
                    {healthQuery.data.llm_configured === false ? <Badge label="API setup required" tone="warning" /> : null}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl bg-ink-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-500">API Base</p>
                <p className="mt-1 text-sm text-ink-700">{API_BASE_URL}</p>
                {llmSettingsQuery.data?.api_key_masked ? (
                  <p className="mt-2 text-xs text-ink-500">Stored key: {llmSettingsQuery.data.api_key_masked}</p>
                ) : null}
                {searchSettingsQuery.data?.search_enabled ? (
                  <p className="mt-1 text-xs text-ink-500">Search: {searchSettingsQuery.data.search_provider}</p>
                ) : null}
              </div>
            </div>
          </div>

          <nav className="mt-5 flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    "rounded-full px-4 py-2 text-sm font-semibold transition",
                    isActive ? "bg-ink-900 text-white" : "bg-ink-100 text-ink-700 hover:bg-ink-200",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="flex-1 w-full">{children}</main>

        <footer className="mt-6">
          <Panel className="bg-white/75 p-4">
            <div className="flex flex-col gap-2 text-sm text-ink-600 md:flex-row md:items-center md:justify-between">
              <span>Frontend MVP for document lifecycle management and grounded QA demos.</span>
              <span>
                Health endpoint:{" "}
                <code className="rounded bg-ink-100 px-1.5 py-0.5 text-xs text-ink-700">/api/health</code>
              </span>
            </div>
          </Panel>
        </footer>
      </div>
    </div>
  );
}
