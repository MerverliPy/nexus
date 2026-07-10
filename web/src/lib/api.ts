const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

interface UserResponse {
  id: number;
  email: string;
  is_active: boolean;
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  due_date: string | null;
  recurrence_rule: string | null;
  created_at: string;
  updated_at: string;
}

function getTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("nexus_access_token"),
    refresh: localStorage.getItem("nexus_refresh_token"),
  };
}

function storeTokens(access: string, refresh: string) {
  localStorage.setItem("nexus_access_token", access);
  localStorage.setItem("nexus_refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("nexus_access_token");
  localStorage.removeItem("nexus_refresh_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { access } = getTokens();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (access) {
    headers["Authorization"] = `Bearer ${access}`;
  }

  let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Token expired — try refresh
  if (res.status === 401 && access) {
    const { refresh } = getTokens();
    if (refresh) {
      const refreshRes = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (refreshRes.ok) {
        const tokens: TokenResponse = await refreshRes.json();
        storeTokens(tokens.access_token, tokens.refresh_token);
        headers["Authorization"] = `Bearer ${tokens.access_token}`;
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } else {
        clearTokens();
      }
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      body.detail || `Request failed with status ${res.status}`,
      res.status
    );
  }

  return res.json();
}

export const api = {
  // Auth
  register: (email: string, password: string) =>
    request<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<UserResponse>("/api/v1/auth/me"),

  // Tasks
  listTasks: (status?: string) =>
    request<Task[]>(`/api/v1/tasks${status ? `?status=${status}` : ""}`),

  createTask: (data: {
    title: string;
    description?: string;
    priority?: number;
    due_date?: string | null;
    recurrence_rule?: string | null;
  }) =>
    request<Task>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTask: (id: number, data: Record<string, unknown>) =>
    request<Task>(`/api/v1/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  completeTask: (id: number) =>
    request<Task>(`/api/v1/tasks/${id}/complete`, { method: "PATCH" }),

  deleteTask: (id: number) =>
    fetch(`${API_BASE}/api/v1/tasks/${id}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${getTokens().access}`,
      },
    }).then((r) => {
      if (!r.ok && r.status !== 204) throw new ApiError("Delete failed", r.status);
    }),

  storeTokens,
  clearTokens,
  getTokens,
};
