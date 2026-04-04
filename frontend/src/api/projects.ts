import type { Project, ProjectCreateRequest, ProjectListResponse, ProjectReindexResponse, ProjectUpdateRequest } from "../types/api";
import { deleteRequest, getJson, patchJson, postJson } from "./client";

export function listProjects(): Promise<ProjectListResponse> {
  return getJson<ProjectListResponse>("/projects");
}

export function getProject(projectId: string): Promise<Project> {
  return getJson<Project>(`/projects/${projectId}`);
}

export function createProject(payload: ProjectCreateRequest): Promise<Project> {
  return postJson<Project, ProjectCreateRequest>("/projects", payload);
}

export function updateProject(projectId: string, payload: ProjectUpdateRequest): Promise<Project> {
  return patchJson<Project, ProjectUpdateRequest>(`/projects/${projectId}`, payload);
}

export function deleteProject(projectId: string): Promise<void> {
  return deleteRequest(`/projects/${projectId}`);
}

export function reindexProject(projectId: string): Promise<ProjectReindexResponse> {
  return postJson<ProjectReindexResponse, Record<string, never>>(`/projects/${projectId}/reindex`, {});
}
