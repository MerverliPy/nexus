"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, clearTokens, type Task } from "./api";

interface User {
  id: number;
  email: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  tasks: Task[];
  refreshTasks: (status?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState<Task[]>([]);

  useEffect(() => {
    const access = api.getTokens().access;
    if (access) {
      api
        .me()
        .then(setUser)
        .catch(() => {
          clearTokens();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    api.storeTokens(tokens.access_token, tokens.refresh_token);
    const me = await api.me();
    setUser(me);
  };

  const register = async (email: string, password: string) => {
    const tokens = await api.register(email, password);
    api.storeTokens(tokens.access_token, tokens.refresh_token);
    const me = await api.me();
    setUser(me);
  };

  const logout = () => {
    clearTokens();
    setUser(null);
    setTasks([]);
  };

  const refreshTasks = async (status?: string) => {
    const list = await api.listTasks(status);
    setTasks(list);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, tasks, refreshTasks }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
