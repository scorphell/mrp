# Design Changelog — Portal de Equipes

## Reformulação visual

- **`RegisterPage.tsx` (`/register`):** composição responsiva do formulário, agrupamento visual dos dados de inscrição e cartões individuais de integrantes. Melhorias em campos, seleção de papéis, consentimento e ações, sem alterar textos ou validações.
- **`TeamLoginPage.tsx` (`/team/login`):** cartão de autenticação com nova hierarquia visual, espaçamentos, campos, links e botão de entrada, preservando os fluxos de login.
- **`TeamMePage.tsx` (`/me`):** atualização da apresentação das credenciais, dos integrantes, do chassi e do download do PDF, preservando requisições, estados e ações.
- **`team.css` (novo):** estilos limitados à classe `.team-surface`, com paletas roxas próprias para os dois temas, traçado decorativo de pista, padrão quadriculado discreto, foco visível, responsividade e suporte a redução de movimento.
- **`TeamIcon.tsx` (novo):** ícones SVG locais e decorativos, sem dependências externas.

## Temas

- **`TeamShell.tsx` (novo):** estrutura visual compartilhada das três páginas e controle para alternar entre tema claro e escuro.
- A preferência é armazenada no navegador com a chave `mrp2026.team.theme`, recuperada na renderização inicial e sincronizada entre abas pelo evento `storage`.
- O padrão permanece escuro quando não há preferência registrada. O tema é aplicado somente às páginas envolvidas, sem alterar estilos, rotas ou autenticação de outras áreas.

## Escopo preservado

- Não foram modificados `TeamAuthContext.tsx`, APIs, rotas, validações, estruturas de dados, configurações, dependências ou arquivos fora da pasta `team`.
- Os textos visíveis originais das três páginas foram preservados. Os únicos rótulos novos são os necessários ao alternador de tema.

## Verificações realizadas

- Análise sintática e transformação TypeScript/TSX sem erros nos arquivos da pasta `team`.
- Análise sintática de `team.css` sem erros.
- Inspeção visual estática dos layouts claro e escuro nas larguras de 360, 390, 768 e 1440 px, sem rolagem horizontal.
- Comparação automatizada dos textos JSX originais e atualizados, sem remoções ou acréscimos nas três páginas.
- A compilação completa com `npm run build` e os testes funcionais integrados não puderam ser executados neste ambiente porque a instalação de dependências externas ficou indisponível (acesso ao registro npm bloqueado). Devem ser executados em ambiente com dependências instaladas.
