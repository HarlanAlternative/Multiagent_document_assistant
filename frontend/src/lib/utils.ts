import type { Citation } from "../types/api";

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatCitation(citation: Citation): string {
  if (citation.page_number) {
    return `${citation.title} - page ${citation.page_number}`;
  }
  if (citation.slide_number) {
    return `${citation.title} - slide ${citation.slide_number}`;
  }
  if (citation.url) {
    return `${citation.title} - ${citation.url}`;
  }
  return citation.title;
}

export function getStatusTone(status: string): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "indexed" || status === "ok" || status === "private_only") {
    return "success";
  }
  if (status === "private_plus_web" || status === "web_only") {
    return "info";
  }
  if (status === "processing") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "neutral";
}
