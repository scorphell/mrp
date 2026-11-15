/** Inscrição de equipe (público) — POST /api/v1/teams/register.
 *
 * Padrão de indústria: a equipe se cadastra no site e recebe o documento de
 * credenciais estilo nota fiscal, com 1 QR por participante e o QR do chassi.
 * Formulário com honeypot (campo "website" oculto) e consentimento LGPD.
 */

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch, errorMessage } from "../api/client";
import TeamIcon from "./TeamIcon";
import TeamShell from "./TeamShell";
import type {
  ApiErrorBody,
  ApiResult,
  TeamRegisterPayload,
  TeamRegisterResponse,
} from "../types";

interface MemberInput {
  name: string;
  email: string;
  ra: string;
  role: "leader" | "member";
}

const LGPD_TEXT =
  "Autorizo o uso dos meus dados pessoais (nome, e-mail e RA) para fins " +
  "exclusivos de credenciamento, controle de presença e conformidade técnica " +
  "da competição Mousetrap Racing 2026, conforme a Lei Geral de Proteção de " +
  "Dados (Lei 13.709/2018). Posso revogar o consentimento a qualquer momento.";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [registrationCode, setRegistrationCode] = useState("");
  const [password, setPassword] = useState("");
  const [vehicleName, setVehicleName] = useState("");
  const [members, setMembers] = useState<MemberInput[]>([
    { name: "", email: "", ra: "", role: "leader" },
    { name: "", email: "", ra: "", role: "member" },
    { name: "", email: "", ra: "", role: "member" },
  ]);
  const [consent, setConsent] = useState(false);
  // Honeypot anti-bot: campo invisível; bots preenchem e são rejeitados.
  const [website, setWebsite] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const updateMember = (
    index: number,
    field: keyof MemberInput,
    value: string,
  ) => {
    setMembers((current) =>
      current.map((member, i) =>
        i === index ? { ...member, [field]: value } : member,
      ),
    );
  };

  const addMember = () => {
    setMembers((current) => [
      ...current,
      { name: "", email: "", ra: "", role: "member" },
    ]);
  };

  const removeMember = (index: number) => {
    setMembers((current) => {
      const next = current.filter((_, i) => i !== index);
      return next.length >= 3 ? next : current;
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (members.length < 3 || members.length > 5) {
      setError("A equipe deve ter entre 3 e 5 integrantes.");
      return;
    }
    if (members.filter((member) => member.role === "leader").length !== 1) {
      setError("A equipe deve ter exatamente 1 líder.");
      return;
    }
    if (!consent) {
      setError("É necessário consentir com o uso dos dados pessoais.");
      return;
    }

    const payload: TeamRegisterPayload = {
      registration_code: registrationCode.trim(),
      password,
      website,
      members: members.map((member) => ({
        ...member,
        email: member.email.trim(),
        ra: member.ra.trim(),
        consent_version: 1,
      })),
      vehicle: { name: vehicleName.trim() },
    };

    setSubmitting(true);
    try {
      const result = await apiFetch<TeamRegisterResponse>(
        "/api/v1/teams/register",
        { method: "POST", body: payload },
      );
      if (!result.ok) {
        const body = result.data as ApiErrorBody | null;
        if (body?.code === "registration_closed") {
          setError(
            "Inscrições encerradas para esta edição. Procure a organização " +
              "para atendimento presencial.",
          );
          return;
        }
        if (body?.code === "team_already_registered") {
          setError("Esta equipe já está registrada. Entre no portal da equipe.");
          return;
        }
        throw new Error(errorMessage(result as ApiResult<unknown>));
      }
      navigate("/team/login", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <TeamShell variant="register">
      <div className="login-page team-register-page">
        <form className="card login-card team-form team-form--register" onSubmit={handleSubmit} noValidate>
          <div className="team-form__intro">
            <h1>Inscrição de Equipe</h1>
            <p className="subtitle">
              MRP2026 · Mousetrap Racing — cadastro de integrantes e chassi
            </p>
          </div>

          {/* Honeypot: invisível para humanos */}
          <div aria-hidden="true" style={{ display: "none" }}>
            <label htmlFor="register-website">Não preencha este campo</label>
            <input
              id="register-website"
              tabIndex={-1}
              autoComplete="off"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
            />
          </div>

          <div className="team-registration-basics">
            <div className="field">
              <label htmlFor="reg-code">Código de inscrição</label>
              <input
                id="reg-code"
                value={registrationCode}
                onChange={(event) => setRegistrationCode(event.target.value)}
                placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
                required
                autoFocus
              />
              <p className="hint">Informado pela organização da competição.</p>
            </div>

            <div className="field">
              <label htmlFor="reg-password">Senha de acesso ao portal</label>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
          </div>

          <fieldset className="field-group team-members">
            <legend>Integrantes ({members.length}/5)</legend>
            {members.map((member, index) => (
              <div className="field-group team-member" key={index}>
                <div className="field">
                  <label htmlFor={`member-name-${index}`}>Nome completo</label>
                  <input
                    id={`member-name-${index}`}
                    value={member.name}
                    onChange={(event) =>
                      updateMember(index, "name", event.target.value)
                    }
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor={`member-email-${index}`}>E-mail</label>
                  <input
                    id={`member-email-${index}`}
                    type="email"
                    inputMode="email"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    value={member.email}
                    onChange={(event) =>
                      updateMember(index, "email", event.target.value)
                    }
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor={`member-ra-${index}`}>RA</label>
                  <input
                    id={`member-ra-${index}`}
                    inputMode="text"
                    autoCapitalize="characters"
                    value={member.ra}
                    onChange={(event) =>
                      updateMember(index, "ra", event.target.value)
                    }
                    required
                  />
                </div>
                <div className="inline-options">
                  <label className="option-pill">
                    <input
                      type="radio"
                      name="member-role"
                      checked={member.role === "leader"}
                      onChange={() =>
                        updateMember(index, "role", "leader")
                      }
                    />
                    <span>Líder</span>
                  </label>
                  <label className="option-pill">
                    <input
                      type="radio"
                      name="member-role"
                      checked={member.role === "member"}
                      onChange={() =>
                        updateMember(index, "role", "member")
                      }
                    />
                    <span>Integrante</span>
                  </label>
                </div>
                {members.length > 3 && (
                  <button
                    type="button"
                    className="ghost-button team-member__remove"
                    onClick={() => removeMember(index)}
                  >
                    <TeamIcon name="remove" />
                    Remover integrante
                  </button>
                )}
              </div>
            ))}
            {members.length < 5 && (
              <button type="button" className="ghost-button team-add-member" onClick={addMember}>
                <TeamIcon name="plus" />
                Adicionar integrante
              </button>
            )}
          </fieldset>

          <div className="field">
            <label htmlFor="reg-vehicle">Nome do chassi (carrinho)</label>
            <input
              id="reg-vehicle"
              value={vehicleName}
              onChange={(event) => setVehicleName(event.target.value)}
              required
            />
            <p className="hint">
              O QR do chassi é gerado junto com as credenciais e fica aderido ao
              carrinho para a inspeção técnica.
            </p>
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>{LGPD_TEXT}</span>
          </label>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="primary-button team-submit" disabled={submitting}>
            {submitting ? "Registrando…" : "Registrar equipe"}
            <TeamIcon name="arrow" />
          </button>

          <p className="hint">
            Já tem conta?{" "}
            <Link to="/team/login" className="muted-link">
              Entre no portal da equipe
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
