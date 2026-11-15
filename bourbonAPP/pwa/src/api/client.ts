/** Client HTTP da API: endpoint configurável (localStorage) + timeout 1500ms.
 *
 * Erros de rede/timeout retornam {ok: false, status: 0, data: null} para o
 * PWA seguir funcionando offline (service worker só precacheia o app shell).
 */

import type { ApiErrorBody, ApiResult } from "../types";

const ENDPOINT_KEY = "checkin.api.endpoint";
const TOKEN_KEY = "checkin.api.token";
const TEAM_TOKEN_KEY = "checkin.api.team.token";
const DEFAULT_ENDPOINT = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 1500;

export function getEndpoint(): string {
  return localStorage.getItem(ENDPOINT_KEY) ?? DEFAULT_ENDPOINT;
}

export function setEndpoint(url: string): void {
  const normalized = url.trim().replace(/\/+$/, "");
  if (normalized) {
    localStorage.setItem(ENDPOINT_KEY, normalized);
  }
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getStoredTeamToken(): string | null {
  return localStorage.getItem(TEAM_TOKEN_KEY);
}

export function setStoredTeamToken(token: string): void {
  localStorage.setItem(TEAM_TOKEN_KEY, token);
}

export function clearStoredTeamToken(): void {
  localStorage.removeItem(TEAM_TOKEN_KEY);
}

export interface ApiFetchOptions {
  method?: "GET" | "POST";
  body?: unknown;
  auth?: boolean;
  teamAuth?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<ApiResult<T>> {
  const { method = "GET", body, auth = false, teamAuth = false } = options;

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (auth) {
    const token = getStoredToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  if (teamAuth) {
    const token = getStoredTeamToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  try {
    const response = await fetch(`${getEndpoint()}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const data = (await response.json().catch(() => null)) as T | null;
    return { ok: response.ok, status: response.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  } finally {
    window.clearTimeout(timer);
  }
}

/** Extrai a mensagem de erro amigável de um resultado de API. */
export function errorMessage(result: ApiResult<unknown>): string {
  const body = result.data as ApiErrorBody | null;
  return (
    body?.detail ??
    "Falha de comunicação com o servidor. Verifique o endpoint em Ajustes e tente novamente."
  );
}

/** Baixa o PDF das credenciais da equipe e dispara o download no navegador. */
export async function downloadTeamPdf(
  teamId: number,
): Promise<{ ok: boolean; status: number; error?: string }> {
  const token = getStoredTeamToken();
  try {
    const response = await fetch(`${getEndpoint()}/api/v1/credentials/team/${teamId}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      return { ok: false, status: response.status };
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `credenciais-${teamId}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    return { ok: true, status: response.status };
  } catch {
    return { ok: false, status: 0 };
  }
}
