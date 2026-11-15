/** Leitura de QR: câmera → verify → presence (POST /api/v1/checkin/*). */

import { useCallback, useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { useNavigate } from "react-router-dom";
import { apiFetch, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime } from "../format";
import type {
  PresenceResponse,
  Session,
  VerifyResponse,
} from "../types";

type ScanPhase = "idle" | "scanning" | "verifying" | "confirmed" | "error";

export default function ScanPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<ScanPhase>("idle");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(1);
  const [qrText, setQrText] = useState("");
  const [verify, setVerify] = useState<VerifyResponse | null>(null);
  const [presence, setPresence] = useState<PresenceResponse | null>(null);
  const [message, setMessage] = useState("");
  const [cameraError, setCameraError] = useState(false);

  const scannerRef = useRef<Html5Qrcode | null>(null);
  const sessionIdRef = useRef(sessionId);
  const phaseRef = useRef<ScanPhase>("idle");

  const setPhaseBoth = (next: ScanPhase) => {
    phaseRef.current = next;
    setPhase(next);
  };

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);

  const loadSessions = useCallback(async () => {
    const result = await apiFetch<Session[]>("/api/v1/sessions?status=open", {
      auth: true,
    });
    if (result.status === 401) {
      handleUnauthorized();
      return;
    }
    if (result.ok && result.data && result.data.length > 0) {
      setSessions(result.data);
      setSessionId(result.data[0].id);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const stopScanner = useCallback(async () => {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    if (!scanner) {
      return;
    }
    try {
      await scanner.stop();
    } catch {
      // câmera já parada ou nunca iniciada
    }
    try {
      scanner.clear();
    } catch {
      // sem elemento DOM a limpar
    }
  }, []);

  // Garante que a câmera é liberada ao sair da página.
  useEffect(() => {
    return () => {
      void stopScanner();
    };
  }, [stopScanner]);

  const handleDecode = async (decodedText: string) => {
    if (
      phaseRef.current === "verifying" ||
      phaseRef.current === "confirmed"
    ) {
      return;
    }
    await stopScanner();
    setQrText(decodedText);
    setPhaseBoth("verifying");

    const result = await apiFetch<VerifyResponse>("/api/v1/checkin/verify", {
      method: "POST",
      body: { qr_text: decodedText, session_id: sessionIdRef.current },
      auth: true,
    });
    if (result.status === 401) {
      handleUnauthorized();
      return;
    }
    if (!result.ok || !result.data?.valid) {
      setMessage(errorMessage(result));
      setPhaseBoth("error");
      return;
    }
    setVerify(result.data);
    setPhaseBoth("confirmed");
  };

  const startScanner = useCallback(async () => {
    setCameraError(false);
    setMessage("");
    setVerify(null);
    setPresence(null);
    setPhaseBoth("scanning");
    try {
      const scanner = new Html5Qrcode("qr-reader");
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText) => {
          void handleDecode(decodedText);
        },
        () => {
          // erros por frame são esperados até um QR ser encontrado
        },
      );
    } catch {
      setCameraError(true);
      setPhaseBoth("error");
    }
  }, []);

  const confirmPresence = async () => {
    if (!qrText) {
      return;
    }
    setMessage("");
    setPhaseBoth("verifying");
    const result = await apiFetch<PresenceResponse>(
      "/api/v1/checkin/presence",
      {
        method: "POST",
        body: { qr_text: qrText, session_id: sessionIdRef.current },
        auth: true,
      },
    );
    if (result.status === 401) {
      handleUnauthorized();
      return;
    }
    if (!result.ok || !result.data) {
      setMessage(errorMessage(result));
      setPhaseBoth("error");
      return;
    }
    setPresence(result.data);
    setPhaseBoth("confirmed");
  };

  const cancelScan = async () => {
    await stopScanner();
    setPhaseBoth("idle");
  };

  return (
    <div className="page">
      <h2>Leitura de QR</h2>

      {phase === "idle" && (
        <div className="card">
          <div className="field">
            <label htmlFor="scan-session">Sessão do evento</label>
            <select
              id="scan-session"
              value={sessionId}
              onChange={(event) => setSessionId(Number(event.target.value))}
            >
              {sessions.length > 0 ? (
                sessions.map((session) => (
                  <option key={session.id} value={session.id}>
                    {session.name}
                  </option>
                ))
              ) : (
                <option value={1}>Sessão 1</option>
              )}
            </select>
            {sessions.length === 0 && (
              <p className="hint">
                Nenhuma sessão aberta encontrada; usando a sessão padrão.
              </p>
            )}
          </div>

          <button
            type="button"
            className="primary-button"
            onClick={() => void startScanner()}
          >
            Iniciar leitura
          </button>
        </div>
      )}

      {phase === "scanning" && (
        <div className="card">
          <div id="qr-reader" className="qr-reader" aria-label="Leitor de QR Code" />
          <p className="hint">Aponte a câmera para o QR da credencial ou do chassi.</p>
          <button
            type="button"
            className="ghost-button"
            onClick={() => void cancelScan()}
          >
            Cancelar
          </button>
        </div>
      )}

      {phase === "verifying" && (
        <div className="card status-card" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Verificando QR…</p>
        </div>
      )}

      {phase === "confirmed" && verify && (
        <div className="card">
          {verify.subject_type === "member" ? (
            <>
              <p className="badge badge-ok">Participante confirmado</p>
              <h3>{verify.member?.name}</h3>
              <dl className="details">
                <div>
                  <dt>Equipe</dt>
                  <dd>{verify.member?.team}</dd>
                </div>
                <div>
                  <dt>Função</dt>
                  <dd>{verify.member?.role === "leader" ? "Líder" : "Integrante"}</dd>
                </div>
              </dl>
            </>
          ) : (
            <>
              <p className="badge badge-ok">Veículo confirmado</p>
              <h3>{verify.vehicle?.name}</h3>
              <dl className="details">
                <div>
                  <dt>Equipe</dt>
                  <dd>{verify.vehicle?.team}</dd>
                </div>
                <div>
                  <dt>Conformidade</dt>
                  <dd>
                    {verify.vehicle?.conformity_status === "pass"
                      ? "Aprovado"
                      : verify.vehicle?.conformity_status === "fail"
                        ? "Reprovado"
                        : "Não avaliado"}
                  </dd>
                </div>
              </dl>
            </>
          )}

          {presence ? (
            <>
              <p
                className={presence.duplicate ? "notice" : "success"}
                role="status"
              >
                {presence.duplicate
                  ? "Presença já registrada anteriormente nesta sessão."
                  : "Presença registrada com sucesso."}
              </p>
              <dl className="details">
                <div>
                  <dt>Horário</dt>
                  <dd>{formatDateTime(presence.last_seen_at)}</dd>
                </div>
              </dl>
            </>
          ) : (
            <button
              type="button"
              className="primary-button"
              onClick={() => void confirmPresence()}
            >
              Registrar presença
            </button>
          )}

          <div className="row-actions">
            <button
              type="button"
              className="ghost-button"
              onClick={() => void startScanner()}
            >
              Escanear novamente
            </button>
          </div>
        </div>
      )}

      {phase === "error" && (
        <div className="card">
          <p className="error" role="alert">
            {cameraError
              ? "Não foi possível acessar a câmera. Verifique as permissões do navegador e use HTTPS."
              : message}
          </p>
          <div className="row-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void startScanner()}
            >
              Tentar novamente
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => void cancelScan()}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
