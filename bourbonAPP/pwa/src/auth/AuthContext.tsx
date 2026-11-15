/** Autenticação de staff: token JWT em localStorage + login/logout. */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "../api/client";
import type { ApiErrorBody, StaffLoginResponse } from "../types";

interface AuthContextValue {
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("checkin.api.token"),
  );

  const login = useCallback(async (username: string, password: string) => {
    const result = await apiFetch<StaffLoginResponse>(
      "/api/v1/auth/staff/login",
      {
        method: "POST",
        body: { username, password },
      },
    );
    if (!result.ok || !result.data?.token) {
      const body = result.data as ApiErrorBody | null;
      throw new Error(
        body?.detail ??
          "Credenciais inválidas ou servidor inacessível. Verifique o endpoint em Ajustes.",
      );
    }
    localStorage.setItem("checkin.api.token", result.data.token);
    setToken(result.data.token);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("checkin.api.token");
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: token !== null,
      login,
      logout,
    }),
    [token, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  }
  return context;
}
