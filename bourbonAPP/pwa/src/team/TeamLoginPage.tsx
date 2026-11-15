/** Login da equipe (público) — POST /api/v1/teams/login. */

import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useTeamAuth } from "./TeamAuthContext";
import TeamIcon from "./TeamIcon";
import TeamShell from "./TeamShell";

export default function TeamLoginPage() {
  const { teamLogin, isTeamAuthenticated } = useTeamAuth();
  const navigate = useNavigate();
  const [registrationCode, setRegistrationCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isTeamAuthenticated) {
    return <Navigate to="/me" replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await teamLogin(registrationCode.trim(), password);
      navigate("/me", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao entrar.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <TeamShell variant="login">
      <div className="login-page team-login-page">
        <form className="card login-card team-form team-form--login" onSubmit={handleSubmit}>
          <div className="team-form__intro">
            <h1>Portal da Equipe</h1>
            <p className="subtitle">
              MRP2026 — credenciais e documento de inscrição
            </p>
          </div>

          <div className="field">
            <label htmlFor="team-login-code">Código de inscrição</label>
            <input
              id="team-login-code"
              placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={registrationCode}
              onChange={(event) => setRegistrationCode(event.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="team-login-password">Senha</label>
            <input
              id="team-login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="primary-button team-submit" disabled={submitting}>
            {submitting ? "Entrando…" : "Entrar"}
            <TeamIcon name="arrow" />
          </button>

          <p className="hint">
            Ainda não se inscreveu?{" "}
            <Link to="/register" className="muted-link">
              Cadastre a equipe
            </Link>
          </p>
          <p className="muted-hint">
            Área de staff?{" "}
            <Link to="/login" className="muted-link">
              Acesso do fiscal
            </Link>
            .
          </p>
        </form>
      </div>
    </TeamShell>
  );
}
