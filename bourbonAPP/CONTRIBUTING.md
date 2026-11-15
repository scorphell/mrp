# Contributing — Mousetrap Racing 2026 · Projeto 7

Guia de contribuição do repositório **Smart Check-In & Credenciamento com QR Code Criptográfico** (Projeto 7).

Escopo restrito ao Projeto 7 — ver `docs/ARCHITECTURE.md` (seção "Não-escopo") antes de qualquer alteração.

---

## 1. Workflow básico

1. Crie uma branch a partir de `main` (nunca commite direto em `main`).
2. Faça commits pequenos e atômicos (1 mudança lógica = 1 commit).
3. Abra um Pull Request; aguarde revisão de **mínimo 1 revisor**.
4. Após merge, `main` é a fonte da verdade. Não faça self-merge.

### Nomes de branch

```
feat/<desc>      → nova funcionalidade
fix/<desc>       → correção de bug/regressão
docs/<desc>      → documentação
refactor/<desc>  → refatoração sem mudar comportamento
chore/<desc>     → manutenção, dependências, ferramentas
test/<desc>      → testes sem mudar código de produção
```

Exemplos: `feat/emissao-credentials`, `fix/checkin-idempotente`, `docs/lgpd-logs`.

---

## 2. Conventional Commits

Todas as mensagens seguem a especificação [Conventional Commits](https://www.conventionalcommits.org/). Isso é **validado por hook no `commit-msg`** — commits fora do formato são rejeitados.

### Formato

```
<type>[scope opcional]: <subject>

[corpo opcional — explica o PORQUÊ]

[footers opcionais — Ref, BREAKING CHANGE, etc.]
```

### Types permitidos

| Type      | Uso                                                    |
|-----------|--------------------------------------------------------|
| `feat`    | Nova funcionalidade (imperativa: "adiciona", não "adicionei") |
| `fix`     | Correção de bug                                        |
| `docs`    | Documentação (sem código)                              |
| `style`   | Formatação, whitespace — sem mudança de lógica          |
| `refactor`| Sem mudar comportamento                                |
| `perf`    | Melhoria de performance                                |
| `test`    | Adiciona/altera testes                                 |
| `build`   | Build, dependências, scripts de build                   |
| `ci`      | CI, hooks, ferramentas de qualidade                     |
| `chore`   | Manutenção geral; atualização de deps                  |
| `revert`  | Reverte um commit `revert: <type>(<scope>): <subject>` |

### Scopes deste repositório

`backend` · `pwa` · `docs` · `deploy` · `scripts` · `ci`

Cada commit afeta **no máximo um scope** — se tocar dois, divida.

### Regras do subject

- Verbo no **imperativo** e no presente ("adiciona", "corrige", "remove").
- **Minúscula** inicial; sem ponto final.
- **≤ 72 caracteres**.
- Sem jargão interno: o leitor deve entender sem contexto.

### Exemplos

```
feat(backend): adiciona emissão de QR assinado por participante
fix(pwa): ignora check-in duplicado na resposta de presence
docs(backend): documenta retenção de dados LGPD
refactor(backend): unifica validação de token em serviço único
test(backend): cobre fluxo de revogação de token
```

Corpo (quando aplicável):

```
feat(checkin): registra presença idempotente por sessão

Re-leitura do mesmo QR atualiza o timestamp em vez de duplicar linha,
evitando duplicatas quando o fiscal escaneia duas vezes seguidas.
```

---

## 3. Breaking changes

Uma mudança é **breaking** se quebra contrato público: formato do QR, contrato de API, campos de resposta, base de dados (migração destrutiva), versão do Python/Django.

### Como declarar

1. Sufixo `!` no type/scope:

   ```
   feat(api)!: remove campo session_id de /checkin/verify
   ```

2. **E** footer `BREAKING CHANGE:` no corpo (obrigatório):

   ```
   feat(api)!: remove campo session_id de /checkin/verify

   BREAKING CHANGE: o campo session_id foi substituído por session_uuid.
   QRs emitidos antes de 2026-09-12 são invalidados; reemitir todos.
   ```

### Consequência

- `BREAKING CHANGE` **sempre** exige bump de **major** no versionamento SemVer (`v1.x → v2.0`).
- Registro de dupla checagem: `git log --oneline --grep="BREAKING"`.

---

## 4. Hooks de commit (pre-commit)

Adotamos **pre-commit (Python)** — sem Husky/Node no root. Config em `.pre-commit-config.yaml`.

### Hooks ativos

| Hook                       | Stage       | Função                                      |
|---------------------------|-------------|---------------------------------------------|
| `ruff` (lint)             | pre-commit  | Lint/flake do Python (backend)              |
| `ruff` (format)           | pre-commit  | Formatação automática do backend            |
| `check-added-large-files` | pre-commit  | Bloqueia arquivos >500 KB                   |
| `end-of-file-fixer`       | pre-commit  | Garante nova linha final                    |
| `trailing-whitespace`     | pre-commit  | Remove whitespace no fim de linha           |
| `check-json` / `check-yaml`| pre-commit | Valida sintaxe de JSON/YAML                 |
| `detect-secrets`          | pre-commit  | Bloqueia segredos/chaves (tem allowlist)     |
| `conventional-pre-commit` | commit-msg  | Valida a mensagem de commit (seção 2)        |

### Instalação

```bash
python3 -m pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

### Uso diário

```bash
pre-commit run --all-files   # roda tudo a qualquer momento
git commit                   # roda hooks automaticamente
```

### Contorno de segredos legítimos (testes/demo)

Nunca edite o `.pre-commit-config.yaml` para desligar `detect-secrets`. Se um segredo **falso-positivo** (ex.: chave demo de teste) precisar passar, adicione à allowlist do repositório:

```bash
detect-secrets scan --baseline .secrets.baseline
# revise o baseline e comprometa-o junto (dê permissão mínima)
pre-commit run detect-secrets --all-files
```

### `--no-verify`

Emergência apenas (ex.: em produção com hook quebrado). Todo uso deve gerar follow-up em PR para corrigir a causa raiz. **Nunca** use para "passar por cima" de lint/mensagem.

### Pre-push (manual, documentado)

Os hooks não executam a suíte inteira (demora). Antes de push/PR:

```bash
# Backend
cd backend && source .venv/bin/activate
python manage.py test
python manage.py check --deploy --fail-level WARNING

# PWA
cd pwa && npx tsc --noEmit && npm run build
```

Se um pre-push automático for desejado, documentamos `pre-commit install --hook-type pre-push` com `pre-push` executando apenas um smoke test.

---

## 5. Pull Requests

### Checklist de PR

- [ ] Commit mensagens em Conventional Commits (sem `--no-verify` desnecessário).
- [ ] Sem PII em logs, commits ou nomes de arquivo (ver `AGENTS.md` → PII).
- [ ] Migrações Django incluídas e não destrutivas.
- [ ] Nenhum segredo, `.env` ou `backend/secrets/` versionado.
- [ ] Testes novos/correspondentes verdes (`python manage.py test`).
- [ ] Escopo limitado ao Projeto 7 (nada dos Projetos 1–25 exceto o 7 — ver Não-escopo).

### Revisão

- Mínimo **1 revisor** (2 se envolver crypto/segurança — alterações em assinatura, QR ou auth obrigam 2).
- Revisor aponta, autor resolve; sem self-merge em `main`.
- Pull request pequeno vence: bifurque em PRs de <300 linhas quando possível.

---

## 6. Versionamento (SemVer) e changelog

- Toda release sob `main` é **tagged** com SemVer: `vMAJOR.MINOR.PATCH`.
- `v0.x` durante desenvolvimento inicial; `v1.0.0` ao abrir para o evento.
- **Major ao menos reestruturou o QR ou a API; minor = feat backward-compatible; patch = fix.**
- Changelog derivado do `git log`: `git log --oneline --grep="feat\|fix" $(git describe --tags --abbrev=0..)`.

---

## 7. Segurança — regras absolutas

1. Nunca commitar: `.env`, `backend/secrets/`, `*.key`, `*.pem`, tokens, senhas.
2. Segredos entram só via variável de ambiente ou arquivos fora do git.
3. Ao detectar segredo vazado em commit histórico: renovar imediatamente e reescrever o histórico (não basta apagar o arquivo).
4. Dados pessoais (nome/e-mail de participantes) — a decisão de versionar dados de teste segue `AGENTS.md` (regra PII).
