/** Autenticação de equipe: token JWT separado em localStorage + login/logout. */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  apiFetch,
  clearStoredTeamToken,
  getStoredTeamToken,
  setStoredTeamToken,
  errorMessage,
} from "../api/client";
import type { ApiResult, TeamLoginResponse } from "../types";

interface TeamAuthContextValue {
  teamToken: string | null;
  isTeamAuthenticated: boolean;
  teamLogin: (registrationCode: string, password: string) => Promise<void>;
  teamLogout: () => void;
}

const TeamAuthContext = createContext<TeamAuthContextValue | null>(null);

export function TeamAuthProvider({ children }: { children: ReactNode }) {
  const [teamToken, setTeamToken] = useState<string | null>(() =>
    getStoredTeamToken(),
  );

  const teamLogin = useCallback(
    async (registrationCode: string, password: string) => {
      const result = await apiFetch<TeamLoginResponse>("/api/v1/teams/login", {
        method: "POST",
        body: { registration_code: registrationCode, password },
      });
      if (!result.ok || !result.data?.token) {
        throw new Error(
          errorMessage(result as ApiResult<unknown>),
        );
      }
      setStoredTeamToken(result.data.token);
      setTeamToken(result.data.token);
    },
    [],
  );

  const teamLogout = useCallback(() => {
    clearStoredTeamToken();
    setTeamToken(null);
  }, []);

  const value = useMemo<TeamAuthContextValue>(
    () => ({
      teamToken,
      isTeamAuthenticated: teamToken !== null,
      teamLogin,
      teamLogout,
    }),
    [teamToken, teamLogin, teamLogout],
  );

  return (
    <TeamAuthContext.Provider value={value}>
      {children}
    </TeamAuthContext.Provider>
  );
}

export function useTeamAuth(): TeamAuthContextValue {
  const context = useContext(TeamAuthContext);
  if (!context) {
    throw new Error("useTeamAuth deve ser usado dentro de TeamAuthProvider.");
  }
  return context;
}