/** Settings: troca manual do endpoint (Nuvem/LAN) + badge de conectividade.
 *
 * A troca é deliberadamente MANUAL e coordenada (sem auto-failover) para
 * evitar split-brain entre os aparelhos dos fiscais (ARCHITECTURE §11).
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetch, getEndpoint, setEndpoint as persistEndpoint } from "../api/client";
import type { HealthResponse } from "../types";

type HealthState = "checking" | "online" | "offline";

export default function SettingsPage() {
  const [endpoint, setEndpointInput] = useState(getEndpoint());
  const [healthState, setHealthState] = useState<HealthState>("checking");
  const [lastCheck, setLastCheck] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    const result = await apiFetch<HealthResponse>("/api/v1/health");
    setHealthState(result.ok ? "online" : "offline");
    setLastCheck(new Date().toLocaleTimeString("pt-BR"));
  }, []);

  // Badge passivo de saúde: verifica a cada 60s usando o endpoint vigente.
  useEffect(() => {
    void checkHealth();
    const timer = window.setInterval(() => void checkHealth(), 60_000);
    return () => window.clearInterval(timer);
  }, [checkHealth]);

  const save = () => {
    setError(null);
    let normalized = endpoint.trim();
    if (!normalized) {
      setError("Informe a URL do servidor.");
      return;
    }
    try {
      normalized = new URL(normalized).toString().replace(/\/+$/, "");
    } catch {
      setError("URL inválida. Use o formato completo, por exemplo https://checkin.exemplo.com.");
      return;
    }
    persistEndpoint(normalized);
    setEndpointInput(normalized);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
    setHealthState("checking");
    void checkHealth();
  };

  return (
    <div className="page">
      <h2>Ajustes</h2>

      <div className="card">
        <div className="field">
          <label htmlFor="api-endpoint">Servidor (Nuvem/LAN)</label>
          <input
            id="api-endpoint"
            type="url"
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={endpoint}
            onChange={(event) => setEndpointInput(event.target.value)}
            placeholder="https://checkin.exemplo.com"
          />
          <p className="hint">
            Endereço da API. A troca deve ser coordenada pelo coordenador — não
            há failover automático.
          </p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={save}
        >
          Salvar
        </button>

        {saved && (
          <p className="success" role="status">
            Endpoint salvo com sucesso.
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="card">
        <h3>Conectividade</h3>
        <div className="health-row" aria-live="polite">
          <span
            className={
              healthState === "online"
                ? "health-dot online"
                : healthState === "offline"
                  ? "health-dot offline"
                  : "health-dot checking"
            }
            aria-hidden="true"
          />
          <span className="health-label">
            {healthState === "online"
              ? "Servidor acessível"
              : healthState === "offline"
                ? "Servidor inacessível"
                : "Verificando…"}
          </span>
        </div>
        <dl className="details">
          <div>
            <dt>Endpoint atual</dt>
            <dd>{getEndpoint()}</dd>
          </div>
          {lastCheck && (
            <div>
              <dt>Última verificação</dt>
              <dd>{lastCheck}</dd>
            </div>
          )}
        </dl>
        <p className="hint">
          A conectividade é verificada a cada 60 segundos via GET /api/v1/health.
        </p>
      </div>
    </div>
  );
}
