/** Checklist manual de conformidade técnica (POST /api/v1/checkin/conformity).
 *
 * O fiscal escaneia o QR do chassi, confere visualmente os itens do edital e
 * registra pass/fail com notas. Não há medição automatizada (fora de escopo).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { useNavigate } from "react-router-dom";
import { apiFetch, errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime, formatTime } from "../format";
import type {
  ConformityItems,
  ConformityResponse,
  Session,
  VerifyResponse,
} from "../types";

type ChecklistPhase =
  | "idle"
  | "scanning"
  | "verifying"
  | "review"
  | "submitting"
  | "done"
  | "error";

const CHECKLIST_LABELS: Array<{ key: keyof ConformityItems; label: string }> = [
  {
    key: "dimensoes",
    label: "Dimensões (comprimento < 60 cm, largura < 30 cm, altura < 30 cm)",
  },
  { key: "ratoeira", label: "Ratoeira 90 × 165 mm (± 10%)" },
  { key: "materiais", label: "Materiais sustentáveis (≥ 50% da massa)" },
];

const EMPTY_ITEMS: ConformityItems = {
  dimensoes: false,
  ratoeira: false,
  materiais: false,
};

export default function ChecklistPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<ChecklistPhase>("idle");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(1);
  const [qrText, setQrText] = useState("");
  const [verify, setVerify] = useState<VerifyResponse | null>(null);
  const [result, setResult] = useState<"pass" | "fail" | null>(null);
  const [items, setItems] = useState<ConformityItems>(EMPTY_ITEMS);
  const [notes, setNotes] = useState("");
  const [conformity, setConformity] = useState<ConformityResponse | null>(null);
  const [message, setMessage] = useState("");
  const [cameraError, setCameraError] = useState(false);

  const scannerRef = useRef<Html5Qrcode | null>(null);
  const sessionIdRef = useRef(sessionId);
  const phaseRef = useRef<ChecklistPhase>("idle");

  const setPhaseBoth = (next: ChecklistPhase) => {
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

  useEffect(() => {
    return () => {
      void stopScanner();
    };
  }, [stopScanner]);

  const startScanner = useCallback(async () => {
    setCameraError(false);
    setMessage("");
    setVerify(null);
    setConformity(null);
    setResult(null);
    setItems(EMPTY_ITEMS);
    setNotes("");
    setPhaseBoth("scanning");
    try {
      const scanner = new Html5Qrcode("checklist-vehicle-reader");
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

  const handleDecode = async (decodedText: string) => {
    if (
      phaseRef.current === "verifying" ||
      phaseRef.current === "review" ||
      phaseRef.current === "submitting"
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
    if (result.data.subject_type !== "vehicle") {
      setMessage("Este QR não é de um veículo. Escaneie o QR do chassi.");
      setPhaseBoth("error");
      return;
    }
    setVerify(result.data);
    setPhaseBoth("review");
  };

  const toggleItem = (key: keyof ConformityItems) => {
    setItems((current) => ({ ...current, [key]: !current[key] }));
  };

  const submitConformity = async () => {
    if (!result) {
      setMessage("Selecione o resultado: aprovado ou reprovado.");
      setPhaseBoth("error");
      return;
    }
    setMessage("");
    setPhaseBoth("submitting");

    const checkedItems = Object.entries(items)
      .filter(([, checked]) => checked)
      .reduce<ConformityItems>((acc, [key]) => {
        acc[key as keyof ConformityItems] = true;
        return acc;
      }, {});

    const apiResult = await apiFetch<ConformityResponse>(
      "/api/v1/checkin/conformity",
      {
        method: "POST",
        body: {
          qr_text: qrText,
          session_id: sessionIdRef.current,
          result,
          items: checkedItems,
          notes,
        },
        auth: true,
      },
    );
    if (apiResult.status === 401) {
      handleUnauthorized();
      return;
    }
    if (!apiResult.ok || !apiResult.data) {
      setMessage(errorMessage(apiResult));
      setPhaseBoth("error");
      return;
    }
    setConformity(apiResult.data);
    setPhaseBoth("done");
  };

  const cancelScan = async () => {
    await stopScanner();
    setPhaseBoth("idle");
  };

  return (
    <div className="page">
      <h2>Conformidade técnica</h2>

      {phase === "idle" && (
        <div className="card">
          <div className="field">
            <label htmlFor="checklist-session">Sessão do evento</label>
            <select
              id="checklist-session"
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
            Escanear QR do veículo
          </button>
        </div>
      )}

      {phase === "scanning" && (
        <div className="card">
          <div
            id="checklist-vehicle-reader"
            className="qr-reader"
            aria-label="Leitor de QR do veículo"
          />
          <p className="hint">Aponte a câmera para o QR do chassi.</p>
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

      {phase === "review" && verify?.vehicle && (
        <div className="card">
          <p className="badge badge-ok">Veículo localizado</p>
          <h3>{verify.vehicle.name}</h3>
          <dl className="details">
            <div>
              <dt>Equipe</dt>
              <dd>{verify.vehicle.team}</dd>
            </div>
            <div>
              <dt>Status atual</dt>
              <dd>
                {verify.vehicle.conformity_status === "pass"
                  ? "Aprovado"
                  : verify.vehicle.conformity_status === "fail"
                    ? "Reprovado"
                    : "Não avaliado"}
              </dd>
            </div>
          </dl>

          <fieldset className="field-group">
            <legend>Resultado da inspeção</legend>
            <div className="inline-options">
              <label className="option-pill">
                <input
                  type="radio"
                  name="conformity-result"
                  value="pass"
                  checked={result === "pass"}
                  onChange={() => setResult("pass")}
                />
                <span>Aprovado</span>
              </label>
              <label className="option-pill">
                <input
                  type="radio"
                  name="conformity-result"
                  value="fail"
                  checked={result === "fail"}
                  onChange={() => setResult("fail")}
                />
                <span>Reprovado</span>
              </label>
            </div>
          </fieldset>

          <fieldset className="field-group">
            <legend>Itens conferidos</legend>
            {CHECKLIST_LABELS.map(({ key, label }) => (
              <label key={key} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={Boolean(items[key])}
                  onChange={() => toggleItem(key)}
                />
                <span>{label}</span>
              </label>
            ))}
          </fieldset>

          <div className="field">
            <label htmlFor="conformity-notes">Notas (opcional)</label>
            <textarea
              id="conformity-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              placeholder="Observações do fiscal…"
            />
          </div>

          {result === "pass" && !items.dimensoes && !items.ratoeira && !items.materiais && (
            <p className="hint">
              Para aprovar, marque ao menos um item conferido.
            </p>
          )}

          <div className="row-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void submitConformity()}
              disabled={result === null}
            >
              Enviar avaliação
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => void startScanner()}
            >
              Escanear outro
            </button>
          </div>
        </div>
      )}

      {phase === "submitting" && (
        <div className="card status-card" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Registrando conformidade…</p>
        </div>
      )}

      {phase === "done" && conformity && (
        <div className="card">
          <p
            className={
              conformity.conformity_status === "pass"
                ? "badge badge-ok"
                : "badge badge-error"
            }
          >
            {conformity.conformity_status === "pass"
              ? "Veículo aprovado"
              : "Veículo reprovado"}
          </p>
          <dl className="details">
            <div>
              <dt>Veículo</dt>
              <dd>{verify?.vehicle?.name}</dd>
            </div>
            <div>
              <dt>Registrado em</dt>
              <dd>{formatDateTime(conformity.checked_at)}</dd>
            </div>
            {notes && (
              <div>
                <dt>Notas</dt>
                <dd>{notes}</dd>
              </div>
            )}
          </dl>
          <button
            type="button"
            className="primary-button"
            onClick={() => void startScanner()}
          >
            Nova avaliação
          </button>
          <p className="hint muted-hint">
            Última verificação às {formatTime(conformity.checked_at)}
          </p>
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
