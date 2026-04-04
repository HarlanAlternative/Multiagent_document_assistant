import type { HealthStatus } from "../types/api";
import { getJson } from "./client";

export function getHealth(): Promise<HealthStatus> {
  return getJson<HealthStatus>("/health");
}
