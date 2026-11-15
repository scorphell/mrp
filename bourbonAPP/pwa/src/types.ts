/** Contratos de resposta da API v1 (ver docs/ARCHITECTURE.md §9). */

export interface ApiResult<T = unknown> {
  ok: boolean;
  status: number;
  data: T | null;
}

/** Corpo normalizado de erro da API (exceptions.py): {detail, code, fields}. */
export interface ApiErrorBody {
  detail?: string;
  code?: string;
  fields?: Record<string, unknown>;
}

export interface StaffLoginResponse {
  token: string;
  token_type: string;
  expires_in: number;
  staff: { id: number; username: string };
}

export interface VerifyResponse {
  valid: boolean;
  subject_type: "member" | "vehicle";
  subject_id: number;
  token_id: string;
  member?: { name: string; team: string; role: string } | null;
  vehicle?: {
    name: string;
    team: string;
    conformity_status: string | null;
  } | null;
}

export interface PresenceResponse {
  checkin_id: number;
  duplicate: boolean;
  subject_type: string;
  subject_id: number;
  uuid: string;
  last_seen_at: string;
}

export interface ConformityResponse {
  check_id: number;
  vehicle_id: number;
  result: string;
  conformity_status: string;
  checked_at: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db: string;
  signing: string;
}

export interface Session {
  id: number;
  name: string;
  kind: "validation" | "final";
  date: string;
  status: "planned" | "open" | "closed";
}

/** Checklist manual de conformidade (whitelist no settings do backend). */
export interface ConformityItems {
  dimensoes?: boolean;
  ratoeira?: boolean;
  materiais?: boolean;
}

/* ---- Portal de equipe (inscrição / credenciais) ---- */

export interface TeamRegisterPayload {
  registration_code: string;
  password: string;
  website: string;
  members: Array<{
    name: string;
    email: string;
    ra: string;
    role: "leader" | "member";
    consent_version: number;
  }>;
  vehicle: { name: string };
}

export interface TeamRegisterResponse {
  detail: string;
  team_id: number;
  team_name: string;
  member_count: number;
}

export interface TeamLoginResponse {
  token: string;
  token_type: string;
  expires_in: number;
  team: { id: number; name: string };
}

export interface TeamMember {
  id: number;
  name: string;
  email: string;
  ra: string;
  role: "leader" | "member";
  consent_at: string | null;
  consent_version: number;
}

export interface TeamMeResponse {
  team: {
    id: number;
    name: string;
    course: string;
    campus: string;
    status: string;
    registered_at: string | null;
    members: TeamMember[];
    vehicle: { id: number; name: string } | null;
  };
}

export interface CredentialIssueResponse {
  token_id: string;
  subject_type: "member" | "vehicle";
  subject_id: number;
  qr: string;
  issued_at: string;
}
