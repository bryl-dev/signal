import type { DocumentItem, InterestItem, Topic, TopicCategory, User } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const AUTH_PATHS = new Set([
  "/v1/auth/login",
  "/v1/auth/register",
  "/v1/auth/logout",
  "/v1/auth/refresh",
]);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function errorMessage(data: { detail?: string | Array<{ msg?: string }> }): string {
  const detail = data.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? "Invalid input").join(", ");
  }
  return typeof detail === "string" ? detail : "Request failed";
}

async function request<T>(path: string, init?: RequestInit, didRefresh = false): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (res.status === 401 && !didRefresh && !AUTH_PATHS.has(path)) {
    const refreshed = await fetch(`${API_URL}/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshed.ok) {
      return request<T>(path, init, true);
    }
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const data = (await res.json().catch(() => ({}))) as {
    detail?: string | Array<{ msg?: string }>;
  };

  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(data));
  }

  return data as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  me: () => request<User>("/v1/me"),
  register: (email: string, password: string) =>
    request<User>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<User>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/v1/auth/logout", { method: "POST" }),
  topics: () => request<{ categories: TopicCategory[] }>("/v1/topics"),
  createTopic: (name: string, category: string) =>
    request<Topic>("/v1/topics", {
      method: "POST",
      body: JSON.stringify({ name, category }),
    }),
  interests: () => request<{ items: InterestItem[]; onboarded: boolean }>("/v1/me/interests"),
  saveInterests: (topicIds: string[]) =>
    request<{ items: InterestItem[]; onboarded: boolean }>("/v1/me/interests", {
      method: "PUT",
      body: JSON.stringify({ topic_ids: topicIds }),
    }),
  documents: () => request<{ items: DocumentItem[] }>("/v1/documents"),
  ingest: () =>
    request<{ sources: number; fetched: number; upserted: number; errors: Array<{ source: string; error: string }> }>(
      "/v1/ingest",
      { method: "POST" },
    ),
};
