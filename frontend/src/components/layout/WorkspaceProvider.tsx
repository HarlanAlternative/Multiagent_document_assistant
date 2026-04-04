import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useLlmSettings } from "../../hooks/useLlmSettings";
import { useProjects } from "../../hooks/useProjects";
import type { Project } from "../../types/api";

const STORAGE_KEY = "knowledge-copilot.current-project-id";

type WorkspaceContextValue = {
  currentProject: Project | null;
  selectedProjectId: string | null;
  setSelectedProjectId: (projectId: string) => void;
  projects: Project[];
  projectsQuery: ReturnType<typeof useProjects>["projectsQuery"];
  createProjectMutation: ReturnType<typeof useProjects>["createProjectMutation"];
  updateProjectMutation: ReturnType<typeof useProjects>["updateProjectMutation"];
  deleteProjectMutation: ReturnType<typeof useProjects>["deleteProjectMutation"];
  reindexProjectMutation: ReturnType<typeof useProjects>["reindexProjectMutation"];
  llmSettingsQuery: ReturnType<typeof useLlmSettings>["llmSettingsQuery"];
  searchSettingsQuery: ReturnType<typeof useLlmSettings>["searchSettingsQuery"];
  updateLlmSettingsMutation: ReturnType<typeof useLlmSettings>["updateLlmSettingsMutation"];
  updateSearchSettingsMutation: ReturnType<typeof useLlmSettings>["updateSearchSettingsMutation"];
  loadModelsMutation: ReturnType<typeof useLlmSettings>["loadModelsMutation"];
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

type WorkspaceProviderProps = {
  children: ReactNode;
};

export function WorkspaceProvider({ children }: WorkspaceProviderProps) {
  const [selectedProjectId, setSelectedProjectIdState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const { projectsQuery, createProjectMutation, updateProjectMutation, deleteProjectMutation, reindexProjectMutation } = useProjects();
  const { llmSettingsQuery, searchSettingsQuery, updateLlmSettingsMutation, updateSearchSettingsMutation, loadModelsMutation } = useLlmSettings();

  const projects = projectsQuery.data?.items ?? [];

  useEffect(() => {
    if (projects.length === 0) {
      return;
    }
    const selectedStillExists = selectedProjectId && projects.some((project) => project.id === selectedProjectId);
    if (!selectedStillExists) {
      setSelectedProjectIdState(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  useEffect(() => {
    if (selectedProjectId) {
      localStorage.setItem(STORAGE_KEY, selectedProjectId);
    }
  }, [selectedProjectId]);

  const currentProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? projects[0] ?? null,
    [projects, selectedProjectId],
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      currentProject,
      selectedProjectId: currentProject?.id ?? null,
      setSelectedProjectId: setSelectedProjectIdState,
      projects,
      projectsQuery,
      createProjectMutation,
      updateProjectMutation,
      deleteProjectMutation,
      reindexProjectMutation,
      llmSettingsQuery,
      searchSettingsQuery,
      updateLlmSettingsMutation,
      updateSearchSettingsMutation,
      loadModelsMutation,
    }),
    [
      createProjectMutation,
      currentProject,
      llmSettingsQuery,
      loadModelsMutation,
      projects,
      projectsQuery,
      searchSettingsQuery,
      deleteProjectMutation,
      reindexProjectMutation,
      updateLlmSettingsMutation,
      updateSearchSettingsMutation,
      updateProjectMutation,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within WorkspaceProvider.");
  }
  return context;
}
