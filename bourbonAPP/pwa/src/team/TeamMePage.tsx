/** Portal da equipe (/me): dados, QRs individuais e PDF estilo nota fiscal. */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  apiFetch,
  downloadTeamPdf,
  errorMessage,
  getStoredTeamToken,
} from "../api/client";
import { useTeamAuth } from "./TeamAuthContext";
import TeamIcon from "./TeamIcon";
import TeamShell from "./TeamShell";
import type {
  ApiResult,
  CredentialIssueResponse,
  TeamMeResponse,
} from "../types";

export default function TeamMePage() {
  const { teamLogout, isTeamAuthenticated } = useTeamAuth();
  const navigate = useNavigate();
  const [team, setTeam] = useState<TeamMeResponse["team"] | null>(null);
  const [qrBySubject, setQrBySubject] = useState<Record<string, string>>({});
  const [issueError, setIssueError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [issuing, setIssuing] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const vehicle = team?.vehicle ?? null;

  const load = useCallback(async () => {
    if (!getStoredTeamToken()) {
      return;
    }
    const result = await apiFetch<TeamMeResponse>("/api/v1/teams/me", {
      teamAuth: true,
    });
    if (result.ok && result.data) {
      setTeam(result.data.team);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isTeamAuthenticated) {
    navigate("/team/login", { replace: true });
    return null;
  }

  const issueQr = async (
    subjectType: "member" | "vehicle",
    subjectId: number,
  ) => {
    setIssueError(null);
    setIssuing(`${subjectType}:${subjectId}`);
    try {
      const result = await apiFetch<CredentialIssueResponse>(
        `/api/v1/credentials/issue/${subjectType}/${subjectId}`,
        { method: "POST", teamAuth: true },
      );
      if (!result.ok || !result.data?.qr) {
        setIssueError(
          errorMessage(result as ApiResult<unknown>) ??
            "Não foi possível gerar o QR.",
        );
        return;
      }
      setQrBySubject((current) => ({
        ...current,
        [`${subjectType}:${subjectId}`]: result.data!.qr,
      }));
    } finally {
      setIssuing(null);
    }
  };

  const downloadPdf = async () => {
    if (!team) {
      return;
    }
    setPdfError(null);
    setDownloading(true);
    try {
      const result = await downloadTeamPdf(team.id);
      if (!result.ok) {
        setPdfError("Não foi possível gerar o PDF das credenciais.");
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleLogout = () => {
    teamLogout();
    navigate("/team/login", { replace: true });
  };

  const roleLabel = (role: string) => (role === "leader" ? "Líder" : "Integrante");

  return (
    <TeamShell variant="portal">
      <div className="page team-page team-portal">
        <div className="card team-portal__frame">
          <div className="team-header">
            <div>
              <h2>{team?.name ?? "Portal da Equipe"}</h2>
              {team && (
                <p className="subtitle">
                  {team.course} · {team.campus}
                </p>
              )}
            </div>
            <button type="button" className="ghost-button team-logout" onClick={handleLogout}>
              <TeamIcon name="logout" />
              Sair
            </button>
          </div>

          {!team ? (
            <p className="hint">Carregando dados da equipe…</p>
          ) : (
            <>
              <div className="card team-portal__panel">
                <h3>Credenciais dos participantes</h3>
                <p className="hint">
                  Toque em "Gerar QR" para emitir a credencial individual (só é
                  preciso uma vez; o token é revalidado automaticamente).
                </p>
                {team.members.map((member) => {
                  const key = `member:${member.id}`;
                  const qr = qrBySubject[key];
                  return (
                    <div className="credential-row" key={member.id}>
                      <div className="credential-info">
                        <strong>{member.name}</strong>
                        <span className="hint">
                          {roleLabel(member.role)} · RA {member.ra}
                        </span>
                      </div>
                      {qr ? (
                        <img
                          className="qr-card-img"
                          src={qr}
                          alt={`QR de ${member.name}`}
                        />
                      ) : (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={issuing === key}
                          onClick={() => issueQr("member", member.id)}
                        >
                          <TeamIcon name="qr" />
                          {issuing === key ? "Gerando…" : "Gerar QR"}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              {vehicle && (
                <div className="card team-portal__panel">
                  <h3>Chassi</h3>
                  <div className="credential-row">
                    <div className="credential-info">
                      <strong>{vehicle.name}</strong>
                      <span className="hint">
                        QR p/ adesão no carrinho — inspeção técnica
                      </span>
                    </div>
                    {qrBySubject[`vehicle:${vehicle.id}`] ? (
                      <img
                        className="qr-card-img"
                        src={qrBySubject[`vehicle:${vehicle.id}`]}
                        alt={`QR do chassi ${vehicle.name}`}
                      />
                    ) : (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={issuing === `vehicle:${vehicle.id}`}
                        onClick={() => issueQr("vehicle", vehicle.id)}
                      >
                        <TeamIcon name="qr" />
                        {issuing === `vehicle:${vehicle.id}`
                          ? "Gerando…"
                          : "Gerar QR"}
                      </button>
                    )}
                  </div>
                </div>
              )}

              {issueError && (
                <p className="error" role="alert">
                  {issueError}
                </p>
              )}

              <div className="card team-portal__panel team-portal__document">
                <h3>Documento de inscrição (estilo nota fiscal)</h3>
                <p className="hint">
                  Reúne todos os QRs em um único PDF para impressão. Imprima e
                  leve no dia.
                </p>
                <button
                  type="button"
                  className="primary-button team-download"
                  disabled={downloading}
                  onClick={() => void downloadPdf()}
                >
                  <TeamIcon name="download" />
                  {downloading ? "Gerando…" : "Baixar PDF"}
                </button>
                {pdfError && (
                  <p className="error" role="alert">
                    {pdfError}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </TeamShell>
  );
}
