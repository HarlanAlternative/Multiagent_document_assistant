import { useState } from "react";

import { Button } from "../common/Button";
import { Panel } from "../common/Panel";
import { Spinner } from "../common/Spinner";

type DocumentUploadFormProps = {
  onUpload: (file: File) => Promise<unknown>;
  isUploading: boolean;
  errorMessage: string | null;
  projectName?: string | null;
  disabled?: boolean;
  existingFilenames?: string[];
};

export function DocumentUploadForm({
  onUpload,
  isUploading,
  errorMessage,
  projectName,
  disabled = false,
  existingFilenames = [],
}: DocumentUploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [localErrorMessage, setLocalErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      return;
    }
    const duplicateExists = existingFilenames.some(
      (existingFilename) => existingFilename.toLowerCase() === file.name.toLowerCase(),
    );
    if (duplicateExists) {
      setLocalErrorMessage(`A document named "${file.name}" already exists in this project.`);
      return;
    }
    setLocalErrorMessage(null);
    await onUpload(file);
    setFile(null);
    event.currentTarget.reset();
  };

  return (
    <Panel
      title="Upload documents"
      description={`Index PDF, PPTX, DOCX, TXT, and Markdown files into the private knowledge base${projectName ? ` for ${projectName}` : ""}. Upload starts the full parsing, chunking, embedding, and vector insertion pipeline.`}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink-700">Document file</span>
          <input
            type="file"
            accept=".pdf,.pptx,.docx,.txt,.md"
            onChange={(event) => {
              setLocalErrorMessage(null);
              setFile(event.target.files?.[0] ?? null);
            }}
            disabled={disabled}
            className="block w-full rounded-2xl border border-ink-200 bg-ink-50 px-4 py-3 text-sm text-ink-700 file:mr-4 file:rounded-xl file:border-0 file:bg-ink-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-ink-800"
          />
        </label>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-ink-600">
            {file ? (
              <span>
                Ready to upload <strong className="text-ink-800">{file.name}</strong>
              </span>
            ) : (
              <span>Select a PDF, PPTX, DOCX, TXT, or Markdown file.</span>
            )}
          </div>

          <Button type="submit" disabled={disabled || !file || isUploading}>
            {isUploading ? (
              <span className="flex items-center gap-2">
                <Spinner />
                Uploading...
              </span>
            ) : disabled ? (
              "Select a project first"
            ) : (
              "Upload document"
            )}
          </Button>
        </div>

        {localErrorMessage || errorMessage ? (
          <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{localErrorMessage ?? errorMessage}</p>
        ) : null}
      </form>
    </Panel>
  );
}
