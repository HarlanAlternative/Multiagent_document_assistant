import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { Button } from "../components/common/Button";
import { EmptyState } from "../components/common/EmptyState";
import { Panel } from "../components/common/Panel";
import { Spinner } from "../components/common/Spinner";
import { DocumentDetailDrawer } from "../components/documents/DocumentDetailDrawer";
import { DocumentsTable } from "../components/documents/DocumentsTable";
import { DocumentUploadForm } from "../components/documents/DocumentUploadForm";
import { useWorkspace } from "../components/layout/WorkspaceProvider";
import { useDocuments } from "../hooks/useDocuments";
import type { DocumentDetail } from "../types/api";

export function DocumentsPage() {
  const { currentProject, createProjectMutation, updateProjectMutation, deleteProjectMutation, reindexProjectMutation, setSelectedProjectId } = useWorkspace();
  const { documentsQuery, detailMap, uploadMutation, deleteMutation, reindexMutation, renameMutation } = useDocuments(currentProject?.id ?? null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDescription, setNewProjectDescription] = useState("");
  const [projectNameDraft, setProjectNameDraft] = useState(currentProject?.name ?? "");
  const [memoryDraft, setMemoryDraft] = useState(currentProject?.memory ?? "");
  const [descriptionDraft, setDescriptionDraft] = useState(currentProject?.description ?? "");

  const selectedDocument = useMemo<DocumentDetail | null>(() => {
    if (!selectedDocumentId) {
      return null;
    }
    return detailMap.get(selectedDocumentId) ?? null;
  }, [detailMap, selectedDocumentId]);

  useEffect(() => {
    setProjectNameDraft(currentProject?.name ?? "");
    setMemoryDraft(currentProject?.memory ?? "");
    setDescriptionDraft(currentProject?.description ?? "");
  }, [currentProject?.id, currentProject?.name, currentProject?.memory, currentProject?.description]);

  const uploadErrorMessage = uploadMutation.error instanceof ApiError ? uploadMutation.error.message : null;
  const listErrorMessage = documentsQuery.error instanceof ApiError ? documentsQuery.error.message : "Failed to load documents.";
  const renameErrorMessage = renameMutation.error instanceof ApiError ? renameMutation.error.message : null;
  const projectErrorMessage =
    createProjectMutation.error instanceof ApiError
      ? createProjectMutation.error.message
      : updateProjectMutation.error instanceof ApiError
        ? updateProjectMutation.error.message
        : deleteProjectMutation.error instanceof ApiError
          ? deleteProjectMutation.error.message
          : reindexProjectMutation.error instanceof ApiError
            ? reindexProjectMutation.error.message
        : null;

  const handleCreateProject = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newProjectName.trim()) {
      return;
    }
    const project = await createProjectMutation.mutateAsync({
      name: newProjectName.trim(),
      description: newProjectDescription.trim() || null,
      memory: "",
    });
    setSelectedProjectId(project.id);
    setNewProjectName("");
    setNewProjectDescription("");
    setMemoryDraft(project.memory ?? "");
    setDescriptionDraft(project.description ?? "");
  };

  const handleSaveProjectContext = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!currentProject) {
      return;
    }
    await updateProjectMutation.mutateAsync({
      projectId: currentProject.id,
      payload: {
        name: projectNameDraft,
        description: descriptionDraft,
        memory: memoryDraft,
      },
    });
  };

  const handleDeleteProject = async () => {
    if (!currentProject) {
      return;
    }
    const confirmed = window.confirm(
      `Delete project "${currentProject.name}"? This removes its documents, conversations, and indexed artifacts.`,
    );
    if (!confirmed) {
      return;
    }
    await deleteProjectMutation.mutateAsync(currentProject.id);
  };

  const handleReindexProject = async () => {
    if (!currentProject) {
      return;
    }
    const confirmed = window.confirm(
      `Reindex all documents in "${currentProject.name}"? Use this after changing embedding provider, embedding model, or vector-store settings.`,
    );
    if (!confirmed) {
      return;
    }
    await reindexProjectMutation.mutateAsync(currentProject.id);
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Panel
          title="Current project workspace"
          description="Documents, chat scope, and memory are isolated per project so you can keep separate knowledge bases for separate efforts."
        >
          {currentProject ? (
            <form className="space-y-4" onSubmit={handleSaveProjectContext}>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">Project name</span>
                  <input
                    value={projectNameDraft}
                    onChange={(event) => setProjectNameDraft(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-ink-700">Description</span>
                  <input
                    value={descriptionDraft}
                    onChange={(event) => setDescriptionDraft(event.target.value)}
                    className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                    placeholder="What this project is for"
                  />
                </label>
              </div>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-ink-700">Project memory</span>
                <textarea
                  value={memoryDraft}
                  onChange={(event) => setMemoryDraft(event.target.value)}
                  rows={8}
                  className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800 outline-none focus:border-signal-500"
                  placeholder="Persistent project notes, assumptions, or constraints that should stay with this workspace."
                />
              </label>

              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Accuracy-first workflow: after switching embedding provider, embedding model, or vector store, reindex this project so retrieval uses the new index.
              </div>

              <div className="flex justify-end">
                <div className="flex flex-wrap gap-3">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={reindexProjectMutation.isPending}
                    onClick={() => void handleReindexProject()}
                  >
                    {reindexProjectMutation.isPending ? "Reindexing all..." : "Reindex all documents"}
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    disabled={deleteProjectMutation.isPending}
                    onClick={() => void handleDeleteProject()}
                  >
                    {deleteProjectMutation.isPending ? "Deleting project..." : "Delete project"}
                  </Button>
                  <Button type="submit" disabled={updateProjectMutation.isPending}>
                    {updateProjectMutation.isPending ? "Saving..." : "Save project context"}
                  </Button>
                </div>
              </div>
            </form>
          ) : (
            <EmptyState title="No project selected" description="Create a project to start uploading files into an isolated workspace." />
          )}
        </Panel>

        <Panel title="Create a new project" description="Use separate projects for different clients, research tracks, or internal workstreams.">
          <form className="space-y-4" onSubmit={handleCreateProject}>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Project name</span>
              <input
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                placeholder="Customer onboarding"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink-700">Description</span>
              <textarea
                value={newProjectDescription}
                onChange={(event) => setNewProjectDescription(event.target.value)}
                rows={4}
                className="w-full rounded-2xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-800"
                placeholder="Optional context for the workspace"
              />
            </label>

            {projectErrorMessage ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{projectErrorMessage}</p> : null}

            <Button type="submit" fullWidth disabled={createProjectMutation.isPending || !newProjectName.trim()}>
              {createProjectMutation.isPending ? "Creating project..." : "Create project"}
            </Button>
          </form>
        </Panel>
      </div>

      <DocumentUploadForm
        onUpload={(file) => uploadMutation.mutateAsync(file)}
        isUploading={uploadMutation.isPending}
        errorMessage={uploadErrorMessage}
        projectName={currentProject?.name}
        disabled={!currentProject}
        existingFilenames={documentsQuery.data?.items.map((document) => document.filename) ?? []}
      />

      <Panel
        title={`Indexed documents${currentProject ? ` for ${currentProject.name}` : ""}`}
        description="Track ingestion status, inspect chunk counts, and manage source files used by the QA workflow."
      >
        {renameErrorMessage ? <div className="mb-4 rounded-2xl bg-rose-50 px-4 py-4 text-sm text-rose-700">{renameErrorMessage}</div> : null}
        {documentsQuery.isLoading ? (
          <div className="flex items-center gap-3 rounded-2xl bg-ink-50 px-4 py-6 text-sm text-ink-600">
            <Spinner />
            Loading document catalog...
          </div>
        ) : documentsQuery.isError ? (
          <div className="rounded-2xl bg-rose-50 px-4 py-4 text-sm text-rose-700">{listErrorMessage}</div>
        ) : documentsQuery.data && documentsQuery.data.items.length > 0 ? (
          <DocumentsTable
            documents={documentsQuery.data.items}
            detailMap={detailMap}
            deletingDocumentId={deleteMutation.variables ?? null}
            reindexingDocumentId={reindexMutation.variables ?? null}
            renamingDocumentId={renameMutation.variables?.documentId ?? null}
            onOpenDetail={(documentId) => setSelectedDocumentId(documentId)}
            onDelete={(documentId) => deleteMutation.mutate(documentId)}
            onReindex={(documentId) => reindexMutation.mutate(documentId)}
            onRename={(documentId, filename) => renameMutation.mutateAsync({ documentId, filename })}
          />
        ) : (
          <EmptyState
            title="No documents indexed yet"
            description="Upload a PDF, PPTX, DOCX, TXT, or Markdown file to make the ingestion pipeline and document lifecycle visible in the UI."
          />
        )}
      </Panel>

      <DocumentDetailDrawer document={selectedDocument} onClose={() => setSelectedDocumentId(null)} />
    </div>
  );
}
