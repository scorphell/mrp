# Arquitetura — Projeto 7: Smart Check-In & Credenciamento com QR Code Criptográfico

Documento de referência. Toda decisão de arquitetura do Projeto 7 vive aqui e é a fonte da verdade para os builders. Status: **aprovada** (2026-09-12).

---

## 1. Contexto e problema

O **Projeto 7** do Mousetrap Racing 2026 automatiza o credenciamento dos competidores e veículos evitando planilhas de papel e filas. Texto-fonte (caderno oficial):

> *"O sistema consistirá em uma plataforma de retaguarda (banco de dados PostgreSQL + backend Django/Python) que gera, na inscrição do grupo (3 a 5 integrantes), um código QR criptografado exclusivo **para cada participante** e para o **respectivo chassi de carrinho**. No dia da entrega digital/física, os professores e fiscais utilizarão um aplicativo móvel leitor que decodifica as informações criptografadas e registra a **presença** e **conformidade técnica** no banco de dados centralizado instantaneamente."*

### Ponto pedagógico registrado

O caderno diz "QR criptografado". Tecnicamente é **assinatura digital** (Ed25519): não há segredo no QR — combate-se **falsificação**, não confidencialidade. Isso fica explícito na documentação e na apresentação.

### Resposta a dúvida recorrente do grupo

O QR é gerado **por participante** (uma credencial para cada um dos 3–5 integrantes) **e por chassi** (um QR para o carrinho da equipe, usado no box técnico para o checklist de conformidade). No modelo, `QrToken.subject_type ∈ {member, vehicle}`.

---

## 2. Escopo e Não-escopo

### Dentro do escopo (Projeto 7)

1. Cadastro de equipes (3–5 integrantes) e veículo via **portal REST de auto-cadastro** (MVP) + Django Admin restrito ao centro de comando.
2. Geração de **QR assinado** por participante e por chassi, com token revogável.
3. **App leitor (PWA)** decodifica → confere → registra **presença** e **conformidade técnica** (checklist manual do fiscal).
4. LGPD interna obrigatória (consentimento, retenção, exportação, revogação, logs raspados).
5. Deploy: Oracle Cloud (prod) + fallback LAN no local.

### Fora do escopo (não implementar)

Votação/vitrine (P1) · contador de público (P2) · chatbot (P3) · trivia (P4) · AR (P5) · mapa (P6) · kanban/marcos 60%/90% (P8) · auditoria CAD (P9) · matchmaking (P10) · painel LGPD compliance (P11) · blockchain de autoria (P12) · leaderboard/telão (P13) · sensores de pista (P14) · simuladores físicos (P15/17/22) · video velocity (P16) · balança IoT (P18) · Green Label (P19) · eco-carbon (P20) · marketplace (P21) · IA de chassis (P23) · portal de vídeos (P24) · digital twin (P25).

- **Dashboard de corrida/resultados/votação: proibido.** Não há tela de dashboard no PWA nem endpoint de resumo público.
- **Medição automatizada (P18) / certificação Green Label (P19): proibido.** Conformidade técnica é checklist **manual** do fiscal.
- LGPD interna é obrigação nossa; o produto do P11 pertence a outro grupo.

---

## 3. Requisitos-chave

| ID | Requisito | Fonte |
|----|-----------|-------|
| R1 | Backend PostgreSQL + Django/Python | P7 |
| R2 | QR exclusivo → 1 por participante + 1 por chassi | P7 |
| R3 | App leitor móvel decodifica e registra presença + conformidade técnica em tempo real | P7 |
| R4 | Criptografia assimétrica anti-fraude | P7 |
| R5 | Times de 3–5 integrantes | P7 |
| R6 | Sem dados pessoais expostos no QR (LGPD / minimização) | time |
| R7 | HTTPS no leitor (câmera) — prod nuvem + fallback LAN | time |
| R8 | Check-in idempotente (sem duplicatas) | time |
| R9 | Auditoria de quem escaneou / quando / de onde | time |

---

## 4. Stack cravada (versões pinadas)

Decisão: **Django LTS 5.2.17 + DRF 3.17.2** (não 6.1 — 1 mês de vida; não 3.16 — sem suporte Python 3.14; não 3.18 — breaking change recente). Tudo com wheels aarch64/cp314.

| Componente | Versão | Justificativa |
|---|---|---|
| Python | **3.14.4** (dev nativo Ubuntu 26.04; prod: 3.14 via deadsnakes p/ Ubuntu 24.04) | Todo o caminho suporta 3.14 oficialmente |
| Django | **5.2.17 LTS** | Segurança até abr/2028; py3.14 desde 5.2.8; 17 patches de maturação |
| DRF | **3.17.2** | 1ª linha madura com py3.14 + Django 5.2 |
| psycopg | **3.2.13 (`psycopg[binary]`)** | py3.14 desde 3.2.13; PG 10–18 |
| cryptography | **50.0.1** | Wheel abi3 aarch64; Ed25519 do QR |
| ReportLab | **4.5.1** | PDF A4 de credenciais |
| segno | **1.6.6** | QR 100% pure-Python |
| PyJWT[crypto] | pin na requirements | JWT Ed25519 (auth) |
| gunicorn | pin na requirements | Servidor da API |
| django-cors-headers | pin na requirements | PWA de origem ≠ API |
| PostgreSQL | **18** (apt: Ubuntu 26.04 nativo; VM Oracle: PGDG `noble-pgdg` arm64) | Paridade dev/prod |
| Node | **26** dev (`.nvmrc`), `engines >=24` | Vite 7 +

Wheels em tudo que houver binário: `pip install --only-binary=:all:`.

---

## 5. Estrutura do repositório

```
bourbonAPP/
├── AGENTS.md              # regras para os agents
├── CONTRIBUTING.md        # conventional commits, hooks, PR, SemVer
├── .pre-commit-config.yaml       # ruff, detect-secrets, conventional-pre-commit
├── .gitignore             # .env, backend/secrets/, .venv/, node_modules/, dist/
├── docs/
│   └── ARCHITECTURE.md    # ESTE documento
├── backend/
│   ├── manage.py
│   ├── requirements.txt   # versões pinadas (seção 4)
│   ├── .env.example       # SECRET_KEY, DB_*, ED25519_PATH, DEBUG, ALLOWED_HOSTS, CORS
│   ├── config/            # settings/urls/wsgi/asgi
│   ├── apps/
│   │   ├── core/          # base models, timezone, auditoria (AuditLog)
│   │   ├── registry/      # Team, Member, Vehicle, EventSession + admin + portal
│   │   ├── credentials/   # QrToken, assinatura Ed25519, emissão PNG/PDF
│   │   └── checkin/       # CheckIn, ConformityCheck, verify/presence/conformity + merge LAN
│   ├── scripts/
│   │   ├── run_postgres.sh        # pg_ctl via nohup (sem systemd)
│   │   ├── generate_keys.py       # par Ed25519 → secrets/ (chmod 600)
│   │   ├── seed_demo.py           # 30 equipes fictícias
│   │   ├── bootstrap_lan.sh       # snapshot Oracle → LAN (manhã do evento)
│   │   ├── export_checkins.py / import_checkins.py   # merge idempotente pós-evento
│   │   └── run_server.sh          # gunicorn nohup
│   └── secrets/           # chave privada (NUNCA versionar)
└── pwa/
    ├── package.json / vite.config.ts / index.html / .nvmrc
    └── src/
        ├── main.tsx / App.tsx / types.ts
        ├── api/client.ts          # endpoint configurável + timeout 1500ms
        ├── auth/LoginPage.tsx + AuthContext.tsx
        ├── scan/ScanPage.tsx      # câmera → verify → presence
        ├── checklist/ChecklistPage.tsx  # conformidade manual (pass/fail + notas)
        ├── settings/SettingsPage.tsx    # troca manual de endpoint (Nuvem/LAN)
        └── sw.ts                  # precache do app shell (offline-first)
```

---

## 6. Modelo de dados

| Entidade | Campos-chave | Observação |
|---|---|---|
| `EventSession` | `id`, `name`, `kind` (`validation`/`final`), `date`, `status` (`planned`/`open`/`closed`) | O QR vale para todas as sessões; não re-gerar por dia |
| `Team` | `id`, `name` (unique), `course`, `campus`, `status`, `registration_code` (UUID único de inscrição) | 3–5 membros (validação no serializer) |
| `Member` | `id`, `team` FK, `name`, `email` (unique), `ra` (unique), `role` (`leader`/`member`), **`consent_at`**, **`consent_version`** | Dados pessoais minimizados |
| `Vehicle` | `id`, `team` OneToOne, `name`, `conformity_status` (null/pass/fail — denormalizado), `conformity_checked_at` | |
| `QrToken` | `id`, `subject_type` (`member`/`vehicle`), `member` FK null, `vehicle` FK null, `token_id` (UUID unique), `payload_json`, `signature`, `status` (`active`/`revoked`), `issued_at`, `revoked_at` | **1 ativo por sujeito**; emitir novo revoga o anterior na mesma transação |
| `CheckIn` | `id`, `session` FK, `subject_type`, `member`/`vehicle` FK, `staff` FK, `last_seen_at`, `uuid` (chave do merge LAN) | **Idempotente**: `unique(session, subject_type, subject)` |
| `ConformityCheck` | `id`, `vehicle` FK, `session` FK, `staff` FK, `result` (pass/fail), `items` JSON (whitelist de chaves), `notes`, `checked_at` | Checklist **manual** do fiscal; histórico auditável |
| `AuditLog` | `id`, `actor` FK null, `action`, `target_type`, `target_id`, `meta` JSON, `ip_hash`, `created_at` | Sem dados pessoais nos campos |

Item do checklist de conformidade (definível por whitelist em settings): dimensões máx. do edital **60×30×30 cm**, ratoeira **90×165 mm (±10%)**, materiais sustentáveis **≥50% da massa**.

---

## 7. QR Code e criptografia

### Formato do payload do QR (assinado, sem PII)

```
MRP1.<base64url(payload)>.<base64url(assinatura_ed25519_64bytes)>
```

```json
{"v":1, "k":"m", "ti":"<uuid4-hex do QrToken>", "iat":<epoch>, "exp":<iat+180d>}
```

- **`ti`** = `QrToken.token_id` (revogação trivial, anti-reuso). `k` = `m`ember ou `v`ehicle.
- **NÃO há** nome/e-mail/time no QR (LGPD + minimização). O leitor resolve o dado pessoal via `verify` no servidor (staff autenticado). Offline: mostra "Token válido" e sincroniza depois.
- Tamanho medido no M2: payload JSON compacto (`sort_keys` + `separators=(',',':')`) ≈ 98 B → QR completo ≈ 216–223 chars → **versão 13-ECC Q**, imprimível a partir de ~2,5–3 cm.

### Criptografia — decisão

- **Ed25519** (lib `cryptography`): assinatura de 64 bytes → QR menor/mais robusto; sem risco de padding; sem depender de WebCrypto no navegador.
- **Validação server-side**: chave privada **só no servidor** (`secrets/`, `chmod 600`). O PWA apenas decodifica e envia o conteúdo bruto do QR.
- Anti-fraude completo: assinatura (não falsificável) + `token_id` (revogável) + `exp` (180 dias: inscrição→final) + idempotência + `AuditLog`.
- **Rotação de chaves pós-evento** invalida QRs antigos se necessário.

---

## 8. Autenticação e PII/LGPD

### Auth

- **JWT stateless Ed25519** via `PyJWT[crypto]`, **mesma chave privada do QR** (zero biblioteca extra).
- Token de **equipe**: 12h (portal de cadastro). Staff/aplicador: Django Admin + sessão ou JWT curto.
- JWT válido tanto em prod (Oracle) quanto no LAN (falback) porque a validação é por assinatura, não por sessão — exige que a chave privada seja **compartilhada Oracle↔LAN** fora do git e a chave pública esteja disponível no client.

### Regra de ouro (PII)

- **QR**: UUID opaco assinado apenas.
- **Logs**: UUID pode aparecer; **combinação `UUID + nome/e-mail` nunca na mesma linha**.
- **Django `LOGGING`**: filtro `pii_scrubber`; formatter JSON redact de `email`, `name`, `Authorization`, `Cookie`; sem `request.body`.
- **AuditLog**: `actor_id`, `action`, `target_type`, `target_id`, `ip_hash` (SHA256+sal). Nunca dados do `Member` além do `id`.
- **gunicorn access log**: formato custom `%({X-Request-ID}i) %h %s %b %D` (sem User-Agent/query).
- **Caddy access log**: JSON, redact de query/headers/cookies; sem body.
- **Consentimento**: `consent_at` + `consent_version` no `Member`; finalidade explícita ("check-in e credenciamento no evento acadêmico, dias X–Y"); base legal **consentimento (Art. 7º, I, LGPD)**; retenção 12 meses; revogação de token 24h.

### Endpoints LGPD

- `GET /teams/me/export` — exporta os dados do membro (Art. 18, II).
- `POST /teams/me/consent/revoke` — anonimiza `Member` (mantém `id` + check-ins p/ integridade referencial; zera nome/email/time).

---

## 9. APIs REST

| Método | Rota | Função |
|---|---|---|
| POST | `/api/v1/auth/staff/login` | Login de staff (capataz/fiscal) → JWT Ed25519 (12h); throttle anti brute force |
| GET | `/api/v1/sessions` | Lista sessões do evento (staff; opcional `?status=open`) |
| POST | `/api/v1/teams/register` | Portal auto-cadastro: código de inscrição → equipe + 3–5 membros + veículo + senha. Bloqueia após o cutoff de inscrição (24h antes da sessão; `REGISTRATION_CUTOFF_HOURS`) |
| POST | `/api/v1/teams/login` | Login de equipe → JWT Ed25519 (12h) |
| GET | `/api/v1/teams/me` | Dados da própria equipe (p/ gerar credencial) |
| GET | `/api/v1/teams/me/export` | Exportar dados (LGPD) |
| POST | `/api/v1/teams/me/consent/revoke` | Revogar consentimento (LGPD) |
| POST | `/api/v1/credentials/issue/{member|vehicle}/{pk}` | Emitir/reemitir QR (revoga anterior); retorna PNG/data-URI |
| GET | `/api/v1/credentials/team/{team_id}/pdf` | PDF A4 da equipe estilo nota fiscal (membros + chassi). Staff: qualquer; equipe: somente a própria |
| POST | `/api/v1/checkin/verify` | Valida assinatura/`ti`/`exp`; **não grava**; retorna nome/time p/ conferência visual |
| POST | `/api/v1/checkin/presence` | Registra CheckIn (idempotente) + AuditLog |
| POST | `/api/v1/checkin/conformity` | Valida QR do veículo e grava ConformityCheck + status no Vehicle |
| GET | `/api/v1/health` | Healthcheck (PWA, badge de conectividade) |

**Não existe** endpoint de resumo de sessão/dashboard público (decisão do time).

Segurança: JWT/DRF auth + throttles em `verify`/`presence` (anti força bruta) + `DEBUG=False` fora de dev local.

---

## 10. PWA leitor

- Vite + React 19 + TS + `html5-qrcode` (camera decode) + `vite-plugin-pwa`.
- Páginas: **Login**, **Scan** (câmera → verify → presença), **Checklist** (conformidade manual por item), **Settings** (troca manual de endpoint — ver §11).
- **Sem tela de dashboard** (decisão do time).
- Service worker: **exclusivamente precache do app shell** (app abre offline quando a nuvem cai; essencial para a troca de endpoint funcionar).
- `api/client.ts`: endpoint em **localStorage** (`checkin.api.endpoint`) + timeout 1500ms.

---

## 11. Deploy e fallback LAN

### Prod (dia do evento)

- **Oracle Cloud Always Free** — VM ARM aarch64 com Django + PostgreSQL 18 nativos (mesmo arch do dev; sem Docker). VM sempre ligada (sem cold start/sleep em 6–12h).
- **Caddy** com HTTPS automático (Let's Encrypt) para o PWA (câmera exige contexto seguro). Domínio a definir (decisão aberta).
- Latência nuvem→shopping é irrelevante p/ 1 POST de ~1KB + healthcheck.

### Fallback LAN (quando o Wi-Fi do shopping oscilar)

Escada de contingência:

1. **Nuvem (Oracle)** — padrão.
2. **LAN** — hotspot dedicado (TP-Link recomendado) + backend no notebook + **Caddy com CA interna self-signed** (instalada nos 5+ celulares no ensaio, pré-requisito não-negociável; Android 14+ validar confiança standalone).
3. **Cloudflared quick tunnel** — plano C improvisável (depende de internet).
4. **Papel impresso** — último recurso se tudo falhar.

Regras:

- **Troca MANUAL** em `Settings` (localStorage). **Sem auto-failover** (evita split-brain entre celulares). Badge de saúde passivo: `fetch('/health')` timeout 1500ms a cada 60s; o **coordenador anuncia e o grupo troca junto**.
- **Dados**: `pg_dump` da Oracle → restore no LAN **na manhã do evento** (`bootstrap_lan.sh`). Contingência grava no Postgres do LAN. **Merge idempotente pós-evento** (`export_checkins` / `import_checkins`, chave = `uuid` do check-in com unique constraint).
- **Auth no LAN**: JWT Ed25519 validado por assinatura (mesma chave pública) — token emitido na Oracle funciona no LAN; o LAN re-emite com a mesma chave privada se expirar.

### Fluxo de inscrição (dia anterior ao evento)

Padrão de indústria (Swoogo/Conference Badges/NYRR): o cadastro online fecha **24h antes** da sessão (`REGISTRATION_CUTOFF_HOURS`, default 24) para o coordenador conferir dados, imprimir o documento estilo nota fiscal e montar a distribuição. No dia, o fiscal só escaneia (~60 s/pessoa no app).

1. A equipe acessa o PWA em `/register` e informa o `registration_code` (UUID) entregue pela organização + 3–5 integrantes (1 líder) + nome do chassi + senha + consentimento LGPD (honeypot `website` protege contra bots).
2. A equipe entra em `/team/login` e, em `/me`, gera os QRs individuais (member/vehicle) e baixa o **PDF estilo nota fiscal** (`POST /credentials/issue/...` + `GET /credentials/team/{id}/pdf`).
3. O coordenador imprime: **1 QR por participante** + **1 QR do chassi** (p/ adesão no carrinho e inspeção técnica).
4. Após o cutoff, `teams/register` responde `403 registration_closed`; perdidos na hora são atendidos presencialmente pelo coordenador via Admin/emissão imediata.

---

## 12. Planos de implementação (marcos)

| Marco | Conteúdo | Verificação |
|---|---|---|
| **M0** | Git + docs + hooks; Postgres 18 apt + `run_postgres.sh`; venv + requirements (wheels); `startproject config`; `.env.example` | `manage.py check`; migração inicial; `createsuperuser` |
| **M1** | `registry`/`checkin`: models + migrations + Admin | `manage.py test`; constraint 3–5 membros, unique check-in |
| **M2** | `generate_keys.py` → secrets/; serviço de assinatura; emissão PNG + PDF A4 por time | Testes: payload adulterado → rejeitado; token revogado → rejeitado |
| **M3** | Auth JWT; portal register/login/me; verify/presence/conformity; AuditLog; LGPD (export/revoke); throttles | Testes de integração DRF do fluxo completo |
| **M4** | PWA: scaffold, Login, Scan, Checklist, Settings; SW precache; Caddy prod | `tsc --noEmit` + `build`; câmera em celular real |
| **M5** | `seed_demo.py` (30 equipes); Caddy prod + LAN (CA nos celulares); bootstrap_lan + merge; runbook; ensaio no shopping | Check-in ponta a ponta em 2+ aparelhos simultâneos |

---

## 13. Riscos e mitigação

| ID | Risco | Mitigação |
|---|---|---|
| R1 | Wheels aarch64/cp314 (psycopg) | Testar no M0 com `--only-binary`; fallback `libpq5` apt |
| R2 | Câmera bloqueada sem HTTPS | Túnel/Let's Encrypt (prod) + CA LAN instalada no ensaio |
| R3 | Memória do container | Política de wheels em todo projeto; sem builds nativos pesados |
| R4 | QR pequeno/danificado no papel | ECC Q, ≥2,5–3 cm; teste de impressão antes |
| R5 | Fraude social (tocar QR alheio) | Conferência visual do nome no leitor + Auditoria (staff, IP, horário) |
| R6 | Rede instável no shopping | Check-in idempotente; fallback LAN; papel como contingência |
| R7 | Split-brain (2 endpoints) | Troca manual coordenada; merge idempotente por `uuid` |
| R8 | Django/Admin expostos | `DEBUG=False`, SECRET_KEY forte via env, staff-only, senhas trocadas pré-evento |

---

## 14. Decisões abertas (não bloqueiam M0)

1. Todos os celulares são Android? (iPhone muda o fluxo de CA iOS + "Trust")
2. Domínio público do PWA/Caddy (ex.: `checkin.mousetrap2026.com`)
3. Quem coordena a troca LAN no dia + canal de comunicação
4. Hotspot dedicado (TP-Link) ou do notebook como plano A do modo LAN
5. Hora do snapshot na manhã do evento (sugestão: 1h antes do credenciamento)
6. **Item 18 (security headers)**: CSP via Caddy (M5), não via Django. Django fornece nosniff + XFO DENY + referrer-policy. Caddy adiciona CSP/Strict-Transport-Security.

---

## 15. Registro de decisões (ADR resumido)

| # | Data | Decisão | Alternativa descartada |
|---|------|---------|------------------------|
| 1 | 2026-09-12 | Django 5.2.17 LTS + DRF 3.17.2 | 6.1/3.18 (recente, breaking); 3.16 (sem py3.14) |
| 2 | 2026-09-12 | QR com UUID opaco assinado (sem PII explícita) | Payload com nome/time em base64 |
| 3 | 2026-09-12 | Ed25519, validação server-side | RSA; verificação no navegador |
| 4 | 2026-09-12 | Banco local PostgreSQL 18 via apt (paridade dev/prod) | SQLite dev + PG prod |
| 5 | 2026-09-12 | Portal REST de auto-cadastro + Admin restrito | Só Django Admin |
| 6 | 2026-09-12 | QR por participante E por chassi (2 tipos de token) | QR único por equipe |
| 7 | 2026-09-12 | Deploy Oracle Cloud Always Free (VM ARM) | Cloud Run/Render (Docker+sleep) |
| 8 | 2026-09-12 | Fallback LAN manual + Caddy CA local + merge idempotente | Replicação contínua; auto-failover |
| 9 | 2026-09-12 | **Sem dashboard público** (resumo só no Admin) | Dashboard web com polling |
| 10 | 2026-09-12 | PWA React 19 + TS (sem dashboard) | Vue 3; app nativo |
| 11 | 2026-09-12 | Hooks: pre-commit Python (ruff/secret/conventional) | Husky+commitlint+lint-staged |
| 12 | 2026-09-12 | Dev em Python 3.13.13 (Termux nativo, aarch64/bionic) com paridade de comportamento; prod Oracle pode usar 3.14.4 — toda a stack (Django 5.2 LTS, DRF 3.17.2, psycopg 3.2.13) suporta 3.13 | Python 3.14.4 no dev (Termux não oferece; exigiria container PROot divergente do ambiente real) |
| 13 | 2026-09-12 | Dev usa cryptography 48.0.1 nativo do Termux (venv com `--system-site-packages`); prod pode pinar 50.0.1 — API Ed25519 é estável entre 48 e 50 | Wheel manylinux 50.0.1 no dev (não instala em bionic/aarch64); build nativo do source (risco de OOM no Android) |
| 14 | 2026-09-12 | Dev usa `psycopg==3.2.13` em modo puro Python (ctypes sobre a libpq nativa do Termux); requirements mantém `psycopg[binary]` para prod glibc | Wheel `psycopg[binary]` para bionic/aarch64 (inexistente); build nativo do psycopg-c (risco de OOM) |
| 15 | 2026-09-12 | Ruff 0.15.19 nativo do Termux (python-ruff) via hook `repo: local` no pre-commit; reverte para ruff-pre-commit quando houver wheel bionic/aarch64 | Repo astral-sh/ruff-pre-commit (tag v0.13.18 inexistente e sem wheel bionic/aarch64) |
| 16 | 2026-09-12 | QR assinado com JSON canônico (`sort_keys`+separators) → versão 13-ECC Q (≈216–223 chars); chave privada em PEM PKCS8 (`secrets/ed25519_private.pem`, chmod 600); assinatura gravada como base64url sem padding no `QrToken.signature`; serialização única compartilhada por sign/verify | Versão ~12 (estimativa inicial); PKCS1 (formato RSA, incorreto p/ Ed25519); armazenar bytes/hex da assinatura |
| 17 | 2026-09-13 | Auth M3: JWT EdDSA via PyJWT (mesma chave Ed25519 do QR); staff = `User` Django (`is_staff`), equipe = `TeamAuth` OneToOne (PBKDF2) + `Team.registered_at`; **senha de equipe validada pelos `AUTH_PASSWORD_VALIDATORS` já ativos = mínimo 8** (NIST SP 800-63B §5.1.1.2, OWASP ASVS v4 V2.1.2), `validate_password` → 400 com `fields.password`; REST em `apps/api` (camada fina) + `apps/core` (AuditLog/JWT); throttles scoped (DRF) e CORS por env. Desvio #1: `BearerJwtAuthentication` NÃO filtra `status=active` — o bloqueio pós-revogação vive no domínio (login 401 / issue 409 / QR 410; `/export` e `/me` pós-revogação seguem 200 = portabilidade LGPD, dados já anonimizados). Desvio #2: token staff de usuário não-staff autentica mas recebe 403 via `IsStaff` (erro de autorização, não de auth). | simplejwt; mínimo de 5 chars (sem exigência textual no edital e abaixo de NIST/OWASP); views de negócio nos apps de domínio |

**Política de ambientes:** Termux nativo (Android aarch64, libc bionic) é o ambiente canônico de desenvolvimento; produção roda na Oracle Cloud em Ubuntu glibc, com wheels manylinux. Divergências de versão de binários entre os dois ambientes são gerenciadas por ADR — dev e prod podem pinar versões distintas desde que a API alvo (ex.: Ed25519) seja idêntica e coberta por testes, garantindo paridade de comportamento.

---

## 16. Segurança operacional (produção)

Estado da checklist de segurança sob a ótica de **deploy/infraestrutura**. Itens já resolvidos no código (1, 2, 6, 7, 8, 10, 11, 13, 14, 15, 16, 17) e os cobertos por `DEBUG=False` (9, 19) não são re-detalhados aqui. Item 4 (RLS) foi decidido **não implementar**: a fronteira de segurança é a camada de aplicação (JWT Ed25519 + validação server-side + throttles), não o banco.

| # | Tema | Estado | Detalhe |
|---|------|--------|---------|
| 3 | Distribuição da chave pública Ed25519 (Public Key DB) | Configuração operacional (dia do evento) | §16.1 |
| 5 | Criptografia de dados (trânsito + repouso) | Configuração operacional (Oracle) | §16.2 |
| 12 | Bot protection no `register` | Implementado (M3) | §16.3 |
| 18 | Security headers (Django + Caddy) | Django ativo; CSP no Caddy (M5) | §16.4 |
| 19 | Forçar HTTPS | Implementado (`DEBUG=False`) | §16.5 |
| 20 | Scam de dependências (supply chain) | Parcial; hash-checking no M5 | §16.6 |

### 16.1 Item 3 — Distribuição da chave pública Ed25519 (Public Key DB)

- `ed25519_public.pem` (PEM PKCS8, `ED25519_PUB_PATH`) deve ser **compartilhada Oracle ↔ LAN por canal seguro** (USB/SCP) **na manhã do evento**, no mesmo momento do snapshot (`bootstrap_lan.sh`, §11). Fora do git e nunca por canal não-autenticado (chat/e-mail sem criptografia).
- O **frontend (PWA) precisará da chave pública para verificar JWTs em modo offline** (fallback LAN / troca de endpoint, §10–11): a validação é por assinatura, não por sessão (§8). No runtime normal a verificação segue server-side; a pública no client cobre a contingência sem nuvem.
- Rotação pós-evento (§7) invalida QRs antigos; a nova pública é redistribuída no próximo evento.

### 16.2 Item 5 — Criptografia de dados

- **Em trânsito (banco):** PostgreSQL Oracle em prod com `sslmode=verify-full` na DSN — cifra a conexão e **valida o certificado do servidor** (protege `pg_dump`/merge e autentica a VM de origem).
- **Em repouso:** **disco da VM criptografado** — LUKS no volume de boot ou **block volume criptografado** do Oracle Cloud — protege `secrets/`, `.env` e dumps no filesystem.
- **LAN:** o PostgreSQL roda no notebook (loopback); a proteção equivalente é o disco criptografado do notebook + acesso físico controlado + Caddy com CA interna (§11).

### 16.3 Item 12 — Bot protection no `register`

- `POST /api/v1/teams/register` protegido por **honeypot** — campo `website` invisível no PWA (`serializers.py`); bots que preenchem são rejeitados — **+ throttle `register: 5/hour`** (`settings.py`), suficiente para o volume do evento (dezenas de equipes).
- **Evolução futura:** reCAPTCHA (v3) no PWA como camada extra se houver abuso em produção. Não bloqueia M0–M5.

### 16.4 Item 18 — Security headers (Django + Caddy)

- **Django (já ativo):** `X-Content-Type-Options: nosniff` + `X-Frame-Options: DENY`; com `DEBUG=False` emite também **HSTS** (31 536 000 s, `includeSubDomains`, `preload`) e **Referrer-Policy** `no-referrer`.
- **Caddy (planejado p/ M5):** injeta **CSP** — restrita ao PWA (câmera `getUserMedia` + origens da API via `CORS_ALLOWED_ORIGINS`) — e reforça HSTS/referrer-policy como defesa em profundidade antes do HTML servido. O Django opera atrás do proxy (`SECURE_PROXY_SSL_HEADER`).

### 16.5 Item 19 — Forçar HTTPS

- Bloco `if not DEBUG:` em `settings.py` já ativa quando `DEBUG=False`:
  - `SECURE_SSL_REDIRECT = True` — redirect HTTP → HTTPS;
  - `SESSION_COOKIE_SECURE = True` e `CSRF_COOKIE_SECURE = True` — cookies só por HTTPS;
  - `SECURE_PROXY_SSL_HEADER` — versão correta do esquema atrás do Caddy.
- Vale para prod **e** LAN: o Caddy (Let's Encrypt ou CA interna) serve o PWA por HTTPS — a câmera do leitor exige contexto seguro (§11).

### 16.6 Item 20 — Scam de dependências (supply chain)

- `requirements.txt` usa **versões pinadas (`==`)** — builds reprodutíveis hoje.
- **Sem `--require-hashes` ainda:** hash-checking será habilitado no **M5**, junto da entrega do Caddy e do freeze do lockfile de wheels para prod — adicionar hashes exige regenerar o lock a cada bump; não vale antes da estabilização pré-evento.
- Reforços já ativos: `--only-binary=:all:` (sem execução de `setup.py` arbitrário em prod) + `detect-secrets` no pre-commit (CONTRIBUTING §4).
