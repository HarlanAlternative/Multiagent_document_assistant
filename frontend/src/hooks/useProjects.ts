import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createProject, deleteProject, listProjects, reindexProject, updateProject } from "../api/projects";
import type { ProjectCreateRequest, ProjectUpdateRequest } from "../types/api";

export function useProjects() {
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  const invalidateProjects = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
    await queryClient.invalidateQueries({ queryKey: ["documents"] });
    await queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  const createProjectMutation = useMutation({
    mutationFn: (payload: ProjectCreateRequest) => createProject(payload),
    onSuccess: invalidateProjects,
  });

  const updateProjectMutation = useMutation({
    mutationFn: ({ projectId, payload }: { projectId: string; payload: ProjectUpdateRequest }) => updateProject(projectId, payload),
    onSuccess: invalidateProjects,
  });

  const deleteProjectMutation = useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: invalidateProjects,
  });

  const reindexProjectMutation = useMutation({
    mutationFn: (projectId: string) => reindexProject(projectId),
    onSuccess: invalidateProjects,
  });

  return {
    projectsQuery,
    createProjectMutation,
    updateProjectMutation,
    deleteProjectMutation,
    reindexProjectMutation,
  };
}
