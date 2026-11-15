# AGENTS.md — Projeto 7 (Smart Check-In & Credenciamento)

Regras de trabalho para os agentes e humanos que atuam neste repositório. Leia obrigatoriamente `docs/ARCHITECTURE.md` e `CONTRIBUTING.md` antes de qualquer tarefa.

---

## Missão / Escopo ESTRITO

Este repositório implementa **apenas o Projeto 7** do Mousetrap Racing 2026:

> Plataforma de retaguarda (PostgreSQL + Django) que gera QR criptografado **por participante** e **por chassi**, e um **app leitor** que decodifica e registra **presença** e **conformidade técnica** em tempo real.

### Não-escopo — NÃO implementar (é de outro grupo)

Votação/vitrine (P1) · contador de público (P2) · chatbot (P3) · trivia (P4) · AR (P5) · mapa (P6) · kanban/marcos 60%/90% (P8) · auditoria CAD (P9) · matchmaking (P10) · painel LGPD compliance (P11) · blockchain de autoria (P12) · leaderboard/telão de corrida (P13) · sensores de pista (P14) · simuladores físicos (P15/17/22) · video velocity (P16) · balança IoT (P18) · Green Label (P19) · eco-carbon (P20) · marketplace (P21) · IA de chassis (P23) · portal de vídeos (P24) · digital twin (P25).

- Dashboard de corrida/resultados/votação: **proibido**.
- Medição automatizada de dimensões/peso (P18) e certificação Green Label (P19): **proibido** — a conformidade é **checklist manual** do fiscal.
- LGPD interna (consentimento/logs) é obrigação **nossa**, não o produto P11.

Antes de implementar algo, pergunte: *"isso é exigência textual do Projeto 7?"* Se não, não faça.

---

## Ambiente de execução

- Container **Ubuntu aarch64 via PROot/Termux/Android**. **Sem systemd** (serviços sobem com `nohup`/`pg_ctl`/`tmux`). **Sem Docker**.
- Evitar build nativo pesado (OOM): usar **wheels pré-compilados** (`pip install --only-binary=:all:`).
- Python **3.14.4**, Node **26** (PWA), PostgreSQL **18** (instalar via apt, subir com `scripts/run_postgres.sh`).
- Navegador headless (se calhar): Chromium com `--no-sandbox --disable-dev-shm-usage --disable-gpu`.

## Stack cravada (tabela em ARCHITECTURE.md §6)

Django 5.2.17 LTS · DRF 3.17.2 · psycopg[binary] 3.2.13 · cryptography 50.0.1 · segno 1.6.6 · ReportLab 4.5.1 · PyJWT[crypto] · gunicorn · PWA Vite + React 19 + TS + html5-qrcode.

---

## Comandos (rodar SEMPRE para validar)

```bash
# Backend
cd backend && source .venv/bin/activate
python manage.py check            # valida project antes de tudo
python manage.py migrate          # aplicar migrações
python manage.py test             # suíte de testes
python manage.py check --deploy --fail-level WARNING

# Qualidade (pré-commit já roda; rodar manual também)
pre-commit run --all-files

# PWA
cd pwa && npx tsc --noEmit && npm run build

# Postgres
bash scripts/run_postgres.sh     # sobe/verifica o PG em background
```

### Preparar ambiente do zero (M0)

```bash
sudo apt install postgresql 2>/dev/null || apt install postgresql
python3 -m venv backend/.venv
backend/.venv/bin/pip install --only-binary=:all: -r backend/requirements.txt
python3 -m pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

---

## Regras de trabalho

1. **Pronto = evidência.** Nunca declare "funciona" sem rodar testes/lint e mostrar a saída. Nada de "deve funcionar".
2. **Mudanças mínimas** e direcionadas; não toque em arquivos fora da tarefa.
3. Reuse padrões existentes; código novo segue o estilo lint (ruff/default Django).
4. Para tarefas grandes ou ambíguas: proponha plano e confirme marcos antes do passo final.
5. **Hooks de commit:** mensagens em Conventional Commits (validado no `commit-msg`). Commits pequenos e atômicos. **Só commitar quando o usuário pedir.**
6. Nunca edite artefatos gerados (`dist/`, `.pwa/`, `staticfiles/`, lockfiles de build).
7. Timeouts em comandos longos; preferir idempotência.
8. Estilo de código googlável e legível, sem comentários supérfluos.

## PII — LGPD (regra de ouro)

- **QP no payload:** apenas o UUID opaco do token (`ti`) + metadados assinados. Nome/time **nunca** no QR.
- **Logs:** UUID pode aparecer; a **combinação `UUID + nome/e-mail` nunca** na mesma linha. Logs Django/gunicorn/Caddy raspados (ver ARCHITECTURE §8).
- Dados de teste: usar `seed_demo.py` com nomes **fictícios**; nunca versionar dados reais de participantes em fixtures/commits/PRs.
- Consentimento: `Member.consent_at` + `consent_version` obrigatórios; termo com finalidade explícita; retenção definida no termo (12 meses) e revogação de QR em 24h.
- Campos de exportação/revogação de consentimento: `GET /teams/me/export` e `POST /teams/me/consent/revoke` (implementar no M3).

---

## Segurança

- `backend/secrets/`, `.env`, `*.key`, `*.pem` **fora do git**; chave Ed25519 privada com `chmod 600`.
- `DEBUG=False` em qualquer execução fora de development local.
- Auth: JWT stateless Ed25519 (mesma chave do QR); token de equipe 12h; staff por acesso Django + sessão.
- Rotação de chaves pós-evento (invalida QRs antigos se necessário).

---

## Definição de pronto (Definition of Done)

1. Lint + format (pre-commit) verdes.
2. `python manage.py test` verde para o escopo alterado.
3. Migrações incluídas; `python manage.py check --deploy` sem WARNING novo.
4. PWA (`tsc --noEmit` + `build`) verde se houve mudança front.
5. Sem PII vazada (revisar diff e `git log`).
6. Escopo: nada além do Projeto 7.
