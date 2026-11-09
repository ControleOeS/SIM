# SIM — Guia detalhado de desenvolvimento e continuidade para agentes de IA

## 1. Objetivo e estado deste documento

Este documento é o ponto de entrada para uma pessoa desenvolvedora ou agente de IA que precise continuar o SIM
sem repetir o mapeamento inicial. Ele registra a arquitetura observada no código, os fluxos já implementados,
as decisões recentes de autenticação/autorização, comandos de desenvolvimento, regras que não podem ser
quebradas e pendências que ainda dependem da empresa ou da TI.

**Leia este arquivo e o `README.md` antes de alterar o sistema.** O `README.md` é o guia resumido para operar o
projeto; este documento é a referência mais aprofundada para entender as relações entre telas, serviços, banco,
permissões e testes.

### Estado de implementação

- Aplicação principal: Python, Streamlit, SQLAlchemy e Alembic.
- Protótipo antigo: HTML/CSS/JavaScript separado; não é usado pelo Streamlit e não compartilha o banco.
- Banco de desenvolvimento: SQLite em arquivo local, substituível por URL SQLAlchemy.
- Dados de negócio: começam vazios; não há importação real de SharePoint.
- Autenticação local: implementada, com contas provisionadas por administrador, domínio permitido, hash de
  senha, troca obrigatória de senha temporária, bloqueio por tentativas e invalidação de sessão.
- Autorização de negócio: implementada na navegação e nos serviços, por centro de custo, além do perfil global
  de controlador.
- Controle de acessos: painel Streamlit de administrador, incluindo domínios, usuários, perfis, concessões,
  revogações, auditoria e a fila de **solicitações de acesso** (seção 4.6).
- Primeiro administrador: criado pela tela de configuração inicial (só aparece com o banco sem nenhum usuário)
  ou pelo comando no host. Depois do primeiro usuário, não há cadastro público.
- Publicação externa: **em preparação (2026-10-27)** — Streamlit Community Cloud + Neon, ver README 9.4. A plataforma de nuvem ainda não foi identificada; MFA, armazenamento
  compartilhado de anexos, SQL de produção, operação, backup/restore e implantação ainda precisam de decisões
  e validação com a TI.
- Código fechado: manter o repositório e pipeline privados. Os usuários acessam a aplicação hospedada; não
  precisam receber o repositório. Um container/imagem de servidor também deve ser tratado como artefato privado.
- O checkout disponível não está dentro de um repositório Git configurado; portanto, a privacidade do código
  ainda precisa ser estabelecida operacionalmente ao criar/publicar um repositório privado.

## 2. Visão funcional

O produto principal substitui os fluxos de quatro Power Apps:

| Empresa | Área | Telas funcionais |
|---|---|---|
| ASAP | Engenharia | BM Mensal; cadastro de centro de custo |
| ASAP | Administrativo | Faturamento |
| SUPERUS | Engenharia | BM Mensal; BM Semanal; cadastro de centro de custo; encerramento; central de ajuda |
| SUPERUS | Administrativo | Faturamento; planejamento mensal/semanal; atualização de dados |

Além destas, há início, seleção de empresa administrativa, uma visão geral por módulo e o painel de controle de
acesso. O mapa funcional único da aplicação está em `sim/ui/navegacao.py`; as implementações das páginas estão
em `telas/`.

### Funcionalidades existentes

**ASAP — Engenharia**

- Seleção de centro de custo.
- Consulta de BMs mensais em ordem de ID decrescente.
- Filtro de centro de custo, mês e status.
- Criação, edição e exclusão de BM, com confirmação.
- Upload, download e remoção de anexos.
- O BM precisa manter ao menos um anexo.
- Se o status é `BM Aprovado pelo Cliente` e não há data, o serviço grava a data atual sem sobrescrever uma
  data já existente.
- Cadastro de centro de custo ASAP. A tela original só inclui; o serviço também tem atualização/exclusão
  controladas.

**ASAP — Administrativo**

- Filtros por mês, status e centro de custo.
- Edição de faturamento de BM existente: valor emitido, status permitido e anexos.
- Não há inclusão administrativa de BM.

**SUPERUS — Engenharia**

- Escolha e confirmação do centro de custo.
- BMs mensais: criação, edição, exclusão, anexos e filtro de mês.
- BMs semanais: criação, edição, exclusão, anexos, filtro de mês/semana.
- Status de engenharia limitado às opções configuradas, preservando status existente na edição.
- Encerramento: ver seção 4.8 (vale para ASAP e SUPERUS). A regra textual dos 95% não foi inventada
  porque a fonte original não contém fórmula.
- Central de ajuda/glossário.

**Cadastro de Centro de Custo — ASAP e SUPERUS (regras definidas pelo responsável em 2026-10-26)**

- Nomes (decisão de 2026-10-27): as áreas operacionais aparecem só como **ASAP** e **SUPERUS** (sem
  "Superus Engenharia" nem chip "Engenharia"; `navegacao.NOME_EMPRESA`, `nome_tipo`, `tema.IDENTIDADES`). O
  código interno do módulo continua `ENG` e os arquivos `telas/superus_eng_*` mantêm o nome.
- Coligada: o módulo **SUPERUS reúne Superus Engenharia, ACPL e Superus Holding**. No cadastro SUPERUS a coligada
  é uma lista obrigatória com `superus.COLIGADAS` (substituiu a coligada fixa de 2026-10-26); a edição pelo
  serviço também aceita trocar. No cadastro ASAP o campo é só informativo ("ASAP"; a tabela não tem coluna).
- Início e Fim de Medição: só o **dia** (lista 1 a 31, sem mês), validado por `Validador.dia_do_mes` e guardado
  na coluna numérica existente (sem migração).
- Regra do período em `sim/medicao.py::periodo_medicao(inicio, fim, ano, mes)`: dia maior que o mês vira o
  último dia dele (31 em fevereiro = 28/29; 31 em abril = 30); início <= fim fica dentro do mês; início > fim
  começa no mês anterior (21 a 20 em março = 21/02 a 20/03). A tela mostra a coluna "Período em MM/AAAA".
  A interpretação de início > fim é uma inferência (os dados de teste já usavam 21/20); confirmar com o negócio.
- A regra de dias vale para todas as coligadas: ASAP (`asap._validar_cc`, `telas/asap_eng_cadastro.py`) e SUPERUS.
  Textos de ajuda compartilhados em `sim/medicao.py` (`AJUDA_DIA`, `EXEMPLOS_PERIODO`).

**SUPERUS — Administrativo**

- Faturamento mensal: filtros de centro de custo, status, mês e trecho de PO; edição de status, valores,
  referências e anexos.
- Planejamento: consultas mensais e semanais somente leitura.
- Atualização de dados: quantidade de BMs, cidade e número de contrato em centro existente.

**Regras comuns**

- Valores monetários são `Decimal`/`Numeric`, não `float`.
- Entrada pt-BR e opções de escolha centralizadas em `config/opcoes.json`.
- Gravações passam por transações SQLAlchemy; erros de persistência geram log e referência.
- Centros de custo com BMs não podem ser excluídos.
- IDs estáveis e chaves estrangeiras ligam BM ao centro de custo; não usar título como chave de relação.
- Há campos mantidos no modelo mesmo quando nenhuma tela os edita, para compatibilidade/futura importação.

## 3. Arquitetura e ciclo de uma requisição Streamlit

Fluxo principal:

1. `app.py` identifica alterações nos módulos `sim.*` por `sim/recarga.py`.
2. Define o tema e inicializa configurações, logs, engine e migrações por `sim/bootstrap.py`.
3. Antes de registrar páginas de negócio, `sim/ui/authentication.py` valida a sessão Streamlit contra a conta
   ativa, versão de sessão e domínio permitido. Sem conta válida, somente login aparece.
4. Conta com senha temporária é direcionada à troca de senha; nenhuma página de negócio é executada nessa
   condição.
5. `app.py` monta as páginas permitidas para o perfil e escopos do usuário.
6. A execução da página ocorre dentro de `usando_principal(principal)`, contexto obrigatório dos serviços.
7. A página chama serviço; serviço verifica a autorização e chama repositório/SQLAlchemy.
8. Para anexos, a leitura valida novamente o centro de custo dono do anexo antes de abrir o arquivo.
9. O sidebar mostra somente rotas autorizadas e permite encerrar a sessão.

Camadas:

| Camada | Responsabilidade | Diretórios/arquivos |
|---|---|---|
| Entrada | Configurar Streamlit, inicializar, autenticar e resolver navegação | `app.py` |
| Páginas | Widgets, formulários, tabelas, composição de fluxos | `telas/` |
| UI comum | Cabeçalho, tema, formulários, tabelas, login, sidebar | `sim/ui/` |
| Segurança | Identidade local, hash de senha, escopos e regras de autorização | `sim/auth.py`, `sim/access_admin.py` |
| Serviços | Regras do domínio, validação, permissões, transações | `sim/services/` |
| Repositórios | Consultas SQLAlchemy e carregamento de relações | `sim/repositories/` |
| Persistência | Engine, sessões, modelos e anexos | `sim/database.py`, `sim/models.py`, `sim/storage.py` |
| Esquema | Versões aplicáveis do banco | `migrations/` |
| Configuração | Variáveis de ambiente e opções de campos | `sim/config.py`, `config/opcoes.json` |
| Testes | Domínio, infraestrutura, navegação, telas e isolamento por escopo | `tests/` |

**Não misturar responsabilidades.** Uma regra ou autorização importante não deve existir apenas no widget da
tela. A interface pode esconder uma rota, mas o serviço continua sendo a fronteira que protege os dados.

## 4. Autenticação e ciclo de vida de sessão

### 4.1 Decisão atual

O login atual é local, com e-mail e senha. A decisão do responsável foi priorizar validação simples, gestão de
contas e redefinição de senha pelo administrador, além de restringir os domínios permitidos. Não foi escolhido
provedor corporativo nem provedor de nuvem.

Não há cadastro automático. Qualquer pessoa pode **pedir** uma conta na aba "Solicitar acesso" do login
(seção 4.6), mas a conta só existe depois que um administrador aprova. Um domínio permitido não cria conta
sozinho.

### 4.2 Perfis

Valores persistidos em `usuarios.perfil` (refeitos em 2026-10-27, migração 0009; constantes e grupos em
`sim/auth.py`, propriedades em `Principal`):

| Perfil (rótulo) | Obras (BMs, encerramento) | Área administrativa | Cadastro CC / decidir encerramento | Controle de acesso |
|---|---|---|---|---|
| `usuario` (Usuário de obras) | só centros liberados | não | não (só pede encerramento) | não |
| `planejador` (Planejador) | todas | não | não (só pede encerramento) | não |
| `faturamento` (Faturamento) | não (lê dados nas telas ADM) | sim, ASAP e SUPERUS, todas as obras | não | não |
| `controle` (Controle) | todas | sim | sim | parcial (abaixo) |
| `controle_geral` (Controle Geral) | todas | sim | sim | tudo |

- Propriedades: `area_obras`, `area_adm`, `ve_todas_obras`, `controlador` (cadastro/encerramento),
  `administrador_acessos` (Controle e Controle Geral), `controle_geral`. Serviços: `exigir_area_obras` (gravações de
  BM e pedido de encerramento), `exigir_area_adm` (faturamento, filtros ADM, atualizar dados), `exigir_controlador`,
  `exigir_administrador_acessos`, `exigir_controle_geral`. `escopos_centros` é global para `ve_todas_obras` e
  `area_adm`. As telas (`app._telas_autorizadas`) só escondem; a regra está nos serviços.
- **Controle no Controle de acesso:** aprova/recusa pedidos, cria contas, libera/retira centros, muda perfis e
  desativa contas — mas **não** adiciona/desativa domínios, **não** redefine senhas e **não** concede, altera
  nem desativa contas de nível Controle/Controle Geral (`access_admin._exigir_pode_gerir_perfil`).
- Sempre resta pelo menos uma conta Controle Geral ativa (`_manter_um_controle_geral`). O primeiro administrador
  criado na tela de configuração é Controle Geral.
- Troca voluntária da própria senha: só Controle e Controle Geral.
- Migração das contas: administrador geral → Controle Geral; controlador geral e administrador de acessos →
  Controle. No banco local, por decisão do responsável, só henrique.galoro ficou Controle Geral (Bernardo Borba
  passou a Controle pelo serviço, com auditoria).

Um gerente de várias obras continua sendo `usuario` e recebe vários registros em `acessos_centros_custo`.
Não criar um papel “gerente” só para representar multiplicidade de centros.

### 4.3 Senhas, bloqueio e reset

- Hash implementado em `sim/auth.py`: PBKDF2-HMAC-SHA256, salt aleatório de 16 bytes e 600.000 iterações.
- Comprimento mínimo de senha: 8 caracteres (reduzido de 12 a pedido do responsável em 2026-10-26); máximo: 256.
- Após cinco falhas consecutivas, bloqueio de conta por 15 minutos.
- Mensagem de falha não distingue e-mail inexistente, senha incorreta, conta inativa ou domínio desautorizado.
- Usuários criados no painel recebem senha aleatória temporária e devem trocá-la antes de ver páginas de
  negócio.
- O domínio allowlist é uma comparação exata do domínio do endereço normalizado; não há correspondência
  automática de subdomínio. Como o SIM não verifica posse de e-mail, o administrador deve confirmar identidade
  e endereço por canal independente antes de entregar a senha temporária.
- O administrador pode redefinir a senha; o código jamais retorna ou armazena a senha anterior em texto claro.
- A redefinição gera uma senha temporária apresentada uma única vez pelo painel, incrementa `versao_sessao`,
  limpa bloqueio e força troca no próximo login.
- O bloqueio é por conta; ainda não há limitação por IP nem MFA. A recuperação por e-mail está implementada
  (seção 4.7), mas depende de conta remetente configurada.
- Desativar conta/domínio ou alterar senha/perfil invalida a sessão ao alterar `versao_sessao`; cada rerun
  carrega a identidade do banco e verifica domínio/estado novamente.

### 4.4 Primeiro administrador e recuperação

**Pela tela (padrão, decisão do responsável em 2026-10-26):** enquanto a tabela `usuarios` estiver vazia, a página de
login mostra "Configuração inicial" (`sim/ui/authentication.py::_pagina_configuracao_inicial`). Ela chama
`sim.auth.criar_primeiro_administrador`, que valida nome/e-mail/senha, recusa se já houver qualquer usuário, autoriza
o domínio do e-mail e já inicia a sessão. **Risco:** quem abrir primeiro o sistema vazio vira administrador. Por
isso, em qualquer ambiente acessível pela rede, criar o administrador antes de liberar o acesso (ou usar o comando).

**Pelo comando**, no host da aplicação, em terminal com acesso ao banco (usa a mesma função):

```powershell
.\.venv\Scripts\python.exe -m sim.admin_cli criar-primeiro-admin admin@empresa.com "Nome"
```

O comando aplica migrações conforme configuração, pede senha de forma oculta, só funciona se não houver
nenhuma conta, cria o perfil `administrador_acessos` e autoriza o domínio desse e-mail. Não colocar a senha em
argumento, script, `.env`, chat ou log.

Para recuperar um administrador ativo pelo host:

```powershell
.\.venv\Scripts\python.exe -m sim.admin_cli redefinir-senha-admin admin@empresa.com
```

No Linux, chamar o mesmo módulo com o Python do ambiente virtual, por exemplo:
`./.venv/bin/python -m sim.admin_cli redefinir-senha-admin admin@empresa.com`.

Esse bypass administrativo local só é seguro se o acesso ao host/console de nuvem for restrito à TI. Não
transformar os comandos em endpoints HTTP.

### 4.5 Concessões por centro de custo

`acessos_centros_custo` guarda:

- usuário alvo;
- empresa;
- exatamente um dos campos `asap_centro_custo_id` ou `superus_centro_custo_id`.

A empresa e o centro são validados em `sim/access_admin.py`; `carregar_principal` também descarta concessões
inconsistentes caso a empresa não corresponda ao centro. FKs impedem concessões órfãs e a constraint impede
que um grant aponte simultaneamente para ambos os modelos.

Todas as operações de domínio usam `exigir_centro`, `escopos_centros` ou `exigir_controlador`. Listas filtram
IDs de centro em SQLAlchemy. `obter`, criar, atualizar, faturamento, encerramento e exclusão verificam a
permissão no registro-alvo. `ler_anexo` resolve o registro proprietário e faz a mesma verificação.
Criar/revogar uma concessão também incrementa a versão de sessão do usuário, obrigando novo login para carregar
o escopo atualizado.

### 4.6 Solicitação e aprovação de acesso (decisão do responsável em 2026-10-26)

Fluxo:

1. Na tela de login, aba **Solicitar acesso**, a pessoa informa nome, e-mail, senha (mínimo 8), classificação
   desejada e **centro de custo do contrato**. Este último é texto livre, sem lista, sugestão ou autopreenchimento
   (`autocomplete="off"`), por pedido explícito: o aprovador compara o texto com os centros cadastrados.
2. `access_admin.solicitar_acesso` (pública, sem principal) grava em `solicitacoes_acesso` com status
   `pendente` e a senha **só como hash**. E-mail já cadastrado ou com pedido pendente não gera registro e recebe
   a mesma resposta, para não revelar quais e-mails existem. Teto de 500 pendentes contra enchimento do banco.
   **Domínio fora de `dominios_permitidos` (ou inativo) é barrado na hora** com erro no campo e-mail
   (`MSG_DOMINIO_NAO_AUTORIZADO`; decisão do responsável em 2026-10-27).
3. O `administrador_acessos` (rótulo "Administrador / Aprovador de acessos") vê a fila no topo de
   `telas/controle_acesso.py` e um aviso na tela inicial. Para cada pedido, define a classificação final (pode
   diferir da pedida), escolhe os centros a liberar (só para `usuario`), escreve um parecer e aprova ou recusa.
4. `aprovar_solicitacao` cria a conta com o hash escolhido pelo solicitante (`deve_trocar_senha=False`), concede
   os centros e audita tudo. **Não autoriza domínio**: se o domínio não estiver ativo, recusa a aprovação (o
   domínio só entra pela seção Domínios autorizados, para um erro de digitação não virar acesso). `recusar_solicitacao` exige parecer. Nas
   duas decisões o hash é apagado da solicitação.
5. Aprovadores podem aprovar novos aprovadores (pedidos com perfil `administrador_acessos`).
- Mensagens de erro: use `exc.descricao()` (em `ValidationError` traz o motivo de cada campo) quando a tela não
  destaca campos; `exc.message` sozinho mostra só "Corrija os campos indicados" (defeito corrigido em 2026-10-27).
- Própria conta no Controle de acesso: "Desativar conta" e "Redefinir senha" ficam desabilitados. A troca da
  própria senha é pelo botão **Trocar senha** da barra lateral (`authentication.dialogo_trocar_senha`, aberto
  enquanto `TROCA_SENHA_ABERTA` estiver na sessão; `on_dismiss` fecha).
- **Troca voluntária de senha só para administradores** (`PERFIS_ADMIN`; decisão de 2026-10-27): o botão só
  aparece para eles e `auth.trocar_senha` recusa os demais com `MSG_TROCA_SO_ADMIN`, exceto na troca obrigatória
  da senha temporária (`deve_trocar_senha`). Usuários de obra vão pedir a troca por e-mail (funcionalidade a criar).
6. Criação direta (seção "Criar usuário" do Controle de acesso, sem `st.form` para os campos dependentes): para
   usuário de obra aparecem **Coligada** (ASAP ou SUPERUS, `navegacao.NOME_EMPRESA`) e depois os **centros de
   custo** (multiseleção; na SUPERUS lista os das três coligadas, com a coligada no rótulo). `access_admin.criar_usuario(..., centros=...)` exige pelo
   menos um centro para `usuario` e concede tudo na mesma transação (2026-10-27).

Classificações oferecidas ao solicitante: `ROTULOS_PERFIL` em `sim/access_admin.py` (usuário de obra, controlador
geral, administrador/aprovador). Não foram criados perfis novos; um quarto perfil exigiria migração da
CheckConstraint de `usuarios.perfil` e regras de autorização nos serviços.

Limites: o pedido é público e não há verificação de posse do e-mail, CAPTCHA ou limite por IP; o aprovador deve
confirmar a identidade por canal independente antes de aprovar. O solicitante não recebe aviso da decisão (não há
e-mail); ele descobre tentando entrar.

### 4.7 Redefinição de senha por e-mail (2026-10-26)

Aba **Esqueci a senha** no login (`sim/ui/authentication.py::_formulario_redefinicao`), regra em
`sim/redefinicao_senha.py`, envio em `sim/envio_email.py`:

- `solicitar_codigo(email)`: só gera código para conta ativa com domínio ativo; resposta igual para qualquer
  e-mail. Código de 6 dígitos, HMAC-SHA256 com salt em `codigos_redefinicao_senha`, validade 15 min, intervalo
  mínimo de 60 s e no máximo 5 códigos por hora por conta; um código novo invalida os anteriores.
- `redefinir_com_codigo(email, codigo, nova, confirmacao)`: até 5 tentativas por código; no sucesso grava a nova
  senha, incrementa `versao_sessao` (derruba sessões abertas), limpa bloqueio e audita
  `redefinir_senha_por_email` (ator = o próprio usuário).
- Envio por `SIM_EMAIL_MODO`: `desativado` (padrão; a aba orienta a pedir ao administrador), `arquivo` (SOMENTE
  desenvolvimento; grava `.eml` em `<SIM_DATA_DIR>/emails`, inclusive com o código em claro) ou `smtp`
  (`SIM_SMTP_HOST`, `SIM_SMTP_PORTA`, `SIM_SMTP_STARTTLS`, `SIM_SMTP_USUARIO`, `SIM_SMTP_SENHA`,
  `SIM_EMAIL_REMETENTE`). A senha SMTP fica fora do `repr` de `Settings` e nunca no código.
- **Pendente:** conta remetente real. No Microsoft 365, SMTP AUTH costuma vir desativado por padrão; o TI pode
  habilitá-lo para uma caixa de serviço ou optar por Microsoft Graph (exigiria nova implementação em
  `envio_email.py`). Falha de envio vai para o log e não aparece na tela.
- Esta máquina de desenvolvimento usa `.env` local com `SIM_EMAIL_MODO=arquivo`.

### 4.8 Encerramento de centro de custo (decisão do responsável em 2026-10-26)

- Encerrar = deixar o CC **inativo** (`ativo=False` em `asap_centros_custo`/`superus_centros_custo`). CC inativo
  não aceita novos BMs (`encerramento.verificar_cc_ativo` em `asap.criar_bm`, `asap.atualizar_bm` quando o BM
  muda de CC, `superus.criar_bm_mensal` e `superus.criar_bm_semanal`). BMs já lançados continuam editáveis.
- Fluxo parecido com a solicitação de acesso: quem tem acesso ao CC **solicita** com justificativa obrigatória
  (`solicitar_encerramento`); **controlador geral ou administrador geral** (`exigir_controlador`) aprova/recusa
  (recusa exige parecer), encerra direto (justificativa obrigatória; atende pedidos pendentes) ou reativa.
- Telas: `asap_enc` e `sup_enc` (ambas via `sim/ui/encerramento.py::tela_encerramento`), visíveis a todos com
  acesso ao módulo; o usuário de obra só vê o formulário de pedido. Tela inicial avisa quem decide.
- Cadastro de CC: coluna **Ativo** (`sim/ui/encerramento.py::tabela_centros`, `st.data_editor`). Desmarcar pede
  justificativa e chama `definir_ativo` → `encerrar`; marcar → `reativar`. Só quem decide edita.
- Histórico em `encerramentos_cc` (acao encerrar/reativar, status pendente/aprovada/recusada, justificativa,
  parecer, solicitante, decisor). Na SUPERUS, `encerramento_manual` ("Sim"/"Não") e `motivo_encerramento`
  acompanham o status. A antiga `superus.registrar_encerramento` foi removida.
- A regra dos 95% do app original continua não implementada (não há fórmula).

### 4.9 Vários usuários ao mesmo tempo (2026-10-27)

- **Bloqueio otimista** em `asap_centros_custo`, `asap_bms`, `superus_centros_custo`, `superus_bms_mensais` e
  `superus_bms_semanais`: coluna `versao` (`models.VersaoMixin`, `version_id_col` do SQLAlchemy). Toda função de
  edição/exclusão desses registros aceita `versao=` (a versão que a tela mostrou) e chama
  `services.common.conferir_versao`, que recusa com `ConflictError` se mudou e sempre marca o registro como
  alterado (inclusive quando só os anexos mudam). A corrida entre essa conferência e o commit vira
  `StaleDataError` → `ConflictError` em `transacao`. `versao=None` não confere (uso interno/testes).
- Formulários de dados usam `with ui.formulario():` + `ui.botoes_formulario` (st.button), **não** `st.form`: cada
  alteração chega ao servidor, e `ui.erros(ns)` descarta os erros guardados assim que algum campo com chave
  `ui.chave(ns, ...)` muda em relação à tentativa de salvar (decisão do responsável em 2026-10-27). `st.form` ficou
  só nas telas de login/senha/solicitação de acesso e no domínio do controle de acesso.
- Telas: `ui.versao_lida(ns, registro, ctx)` guarda a versão de quando o formulário abriu, até gravar/cancelar
  (nova versão de chaves) ou desmarcar a linha (chamar com `None`). **Toda tela nova de edição deve usar isso e
  passar `versao=lida` ao serviço.** A mensagem orienta a clicar em Cancelar para recarregar.
- Pedidos pendentes únicos garantidos no banco (índices parciais `uq_*_pendente` em `encerramentos_cc` e
  `solicitacoes_acesso`), não só pela consulta prévia; a violação vira a mesma mensagem de "já existe pedido".
- SQLite: `database.py` liga WAL, `synchronous=NORMAL` e espera de 15 s (`SQLITE_ESPERA_SEGUNDOS`); "database is
  locked" vira mensagem "sistema ocupado" (`MSG_OCUPADO`). Com WAL, copie o banco só com `scripts/backup.py` (API
  de backup) ou com o app parado, levando também `sim.db-wal`. Para uso online com muitos usuários: PostgreSQL.
- Testes: `tests/test_edicao_simultanea.py`.

## 5. Banco e dados

### 5.1 Configuração

`sim/config.py` carrega `.env` sem sobrescrever variáveis já definidas. Padrões:

- `SIM_DATA_DIR=data`
- `DATABASE_URL=sqlite:///<SIM_DATA_DIR>/sim.db`
- `SIM_ANEXOS_DIR=<SIM_DATA_DIR>/anexos`
- `SIM_LOGS_DIR=<SIM_DATA_DIR>/logs`
- `SIM_AUTO_MIGRATE=true`
- `SIM_SQL_ECHO=false`
- `SIM_MAX_ANEXO_MB=50`

`sim/database.py` é o único ponto que cria engine e sessão. SQLite ativa `check_same_thread=False` e
`PRAGMA foreign_keys=ON`. Para SQL de produção, definir URL/driver no host e testar migrações. Não introduzir
SQL exclusivo do SQLite em serviços/repos.

### 5.2 Tabelas

| Tabela | Finalidade / relação |
|---|---|
| `empresas` | códigos estruturais ASAP e SUPERUS, sem dados de sessão |
| `asap_centros_custo` | centros de custo ASAP e atributos originais |
| `asap_bms` | BMs ASAP, FK para `asap_centros_custo` |
| `superus_centros_custo` | centros de custo SUPERUS |
| `superus_bms_mensais` | BMs mensais SUPERUS, FK para centro |
| `superus_bms_semanais` | BMs semanais SUPERUS, FK para centro |
| `anexos` | metadados de arquivo e FK exclusiva para um dos três tipos de BM |
| `usuarios` | e-mail normalizado único, nome, hash, perfil, estado, bloqueio e versão de sessão |
| `dominios_permitidos` | allowlist de domínios |
| `acessos_centros_custo` | escopos explícitos do perfil usuário |
| `auditoria_acessos` | ator, alvo, ação e detalhes não secretos das mudanças de acesso |
| `solicitacoes_acesso` | pedidos de conta feitos no login; status, CC informado (texto livre), parecer e decisão |
| `codigos_redefinicao_senha` | códigos de redefinição por e-mail (hash, validade, tentativas, uso) |
| `encerramentos_cc` | pedidos e histórico de encerramento/reativação de CC (ASAP ou SUPERUS) |
| `alembic_version` | revisão de esquema atualmente aplicada |

Migrações existentes:

1. `0001_esquema_inicial.py`: tabelas funcionais originais e metadados de anexos.
2. `0002_empresas.py`: registros estruturais ASAP/SUPERUS.
3. `0003_controle_de_acesso.py`: contas, domínios, escopos e auditoria.
4. `0004_solicitacoes_acesso.py`: pedidos de acesso e decisão do aprovador.
5. `0005_perfil_administrador_geral.py`: amplia as CheckConstraints de perfil.
6. `0006_codigos_redefinicao_senha.py`: códigos de redefinição de senha por e-mail.
7. `0007_encerramento_centro_custo.py`: coluna `ativo` nos CCs e tabela `encerramentos_cc`.
8. `0008_edicao_simultanea.py`: coluna `versao` nos CCs e BMs e índices de pedido pendente único.
9. `0009_perfis_controle.py`: perfis usuário, planejador, faturamento, controle e controle geral.
10. `0010_anexos_no_banco.py`: tabela `anexos_conteudo` (conteúdo de anexos quando `SIM_ANEXOS_BACKEND=banco`).
11. `0011_id_legado.py`: `id_legado` (ID SharePoint, único) nos BMs SUPERUS mensais e semanais, usado pela
    importação do histórico (`sim/importacao_legado.py`, README 9.5). BM com `id_legado` não exige anexo na edição.
12. `0012_valor_previsto.py`: tabela `superus_valores_previstos` (único por CC, ano e mês) e, em
    `superus_bms_mensais`, `valor_previsto` (previsto usado no lançamento) e `justificativa_variacao`. Regras em
    `sim/services/previsto.py` (tolerância de 5%, `conferir_variacao` chamado pelo serviço do BM mensal dentro da
    transação); tela `telas/superus_adm_valor_previsto.py` (escrita só `exigir_controlador`).
13. `0013_um_bm_por_mes.py`: índice único parcial `uq_superus_bm_mensal_mes` (CC, ano, mês) para BMs sem
    `id_legado`. O serviço (`superus._conferir_mes_livre`) também recusa mês ocupado por BM do histórico. Ano do
    BM: `superus.ano_de_referencia` / `ano_do_mes` (não vem do formulário); meses selecionáveis:
    `superus.meses_permitidos` (até o mês atual; em janeiro, também dezembro do ano anterior).
14. `0014_itens_do_bm_mensal.py`: `superus_bm_mensal_itens` (linhas da resposta mensal). Com `dados["itens"]`,
    `superus._validar_itens` calcula `valor_bm`/`valor_aprovado` (somas) e substitui as linhas na edição; sem
    `itens` (testes/uso interno) os valores vêm direto. A tela usa `st.data_editor` (num_rows="dynamic").

**Atenção (SQLite):** o modo batch recria a tabela. Com `foreign_keys=ON` isso disparava ON DELETE CASCADE
(apagaria grants em silêncio) ou RESTRICT (falhava com BMs). Desde 2026-10-26, `migrations/env.py` desliga o
PRAGMA durante a migração e roda `PRAGMA foreign_key_check` no fim; `tests/test_migracoes_com_dados.py` cobre.
Se uma migração SQLite falhar no meio, pode sobrar tabela `_alembic_tmp_*`: confira e remova antes de repetir
(o DDL do pysqlite não é totalmente transacional). Faça cópia do `sim.db` antes de migrar dados reais.

Não editar uma migração já aplicada em qualquer ambiente compartilhado. Criar revisão nova com `alembic
revision --autogenerate -m "..."`, revisar manualmente o resultado, testar upgrade e downgrade. Migrações usam
`render_as_batch` para SQLite.

### 5.3 Anexos

`sim/storage.py::LocalFileStorage` grava conteúdo em disco dentro de `SIM_ANEXOS_DIR`, organiza por empresa,
tipo de BM e ID, normaliza nomes e impede path traversal. O banco guarda caminho relativo, nome original,
tamanho, MIME type e SHA-256.

Este armazenamento é local/provisório. Em nuvem:

- a instância da aplicação precisa de armazenamento persistente e compartilhado se houver mais de uma réplica;
- definir blob/object storage ou solução corporativa aprovada;
- manter uma interface equivalente a `gravar`, `ler`, `existe`, `remover`;
- preservar caminhos/metadados durante migração;
- executar backup e teste real de restauração.

Uma pasta efêmera local dentro de container não é armazenamento válido para produção.

### 5.4 Inventário da API de serviços

Todas as funções abaixo são chamadas pelo servidor; operações de negócio devem ocorrer dentro do contexto
`usando_principal`. O principal não é recebido dos campos do formulário: ele vem da sessão validada pelo app.

**`sim.services.asap`**

| Função | Efeito |
|---|---|
| `listar_centros_custo()` | Lista ASAP visível ao usuário |
| `criar_centro_custo(dados)` | Cria CC; exige controlador geral |
| `atualizar_centro_custo(cc_id, dados)` | Atualiza CC concedido |
| `excluir_centro_custo(cc_id)` | Exclui CC sem BMs, se concedido |
| `listar_bms(centro_custo_id=None, mes=None, status=None)` | Lista BMs dentro dos escopos |
| `obter_bm(bm_id)` | Carrega BM, CC e anexos só se autorizado |
| `criar_bm(dados, anexos)` | Cria BM em `dados["centro_custo_id"]`; exige grant e anexo |
| `atualizar_bm(bm_id, dados, novos_anexos, remover_anexo_ids=None)` | Atualiza BM/anexos; verifica CC antigo e destino |
| `excluir_bm(bm_id)` | Exclui BM e remove arquivos depois do commit |
| `opcoes_filtro_faturamento()` | Meses estáticos e status/CC derivados de dados autorizados |
| `atualizar_faturamento(bm_id, valor_emitido, status, novos_anexos, ...)` | Atualiza faturamento de BM existente |
| `aplicar_data_aprovacao(bm, agora=None)` | Regra pura de data de aprovação |
| `status_permitidos_faturamento(status_atual)` | Regra pura para escolhas de faturamento |

**`sim.services.superus`**

| Função | Efeito |
|---|---|
| `listar_centros_custo()` / `obter_centro_custo(cc_id)` | Lista/abre CCs SUPERUS dentro do escopo |
| `criar_centro_custo(dados)` | Cria CC; exige controlador geral |
| `atualizar_cadastro(cc_id, dados)` / `excluir_centro_custo(cc_id)` | Atualiza/exclui CC concedido, respeitando FKs |
| `atualizar_dados_cc(cc_id, qtd_bms, cidade, numero_contrato)` | Atualiza os campos da tela ADM |
| `registrar_encerramento(cc_id, encerramento_manual, motivo_encerramento)` | Atualiza encerramento manual |
| `listar_bms_mensais(centro_custo_id=None, mes=None, status=None, po=None)` | Consulta mensal filtrada por escopo |
| `obter_bm_mensal(bm_id)` / `criar_bm_mensal(centro_custo_id, dados, anexos)` | Leitura/criação autorizadas |
| `atualizar_bm_mensal(...)` / `excluir_bm_mensal(bm_id)` | Edição/exclusão autorizadas, incluindo anexos |
| `listar_bms_semanais(centro_custo_id=None, mes=None, semana=None)` | Consulta semanal filtrada por escopo |
| `obter_bm_semanal(bm_id)` / `criar_bm_semanal(centro_custo_id, dados, anexos)` | Leitura/criação autorizadas |
| `atualizar_bm_semanal(...)` / `excluir_bm_semanal(bm_id)` | Edição/exclusão autorizadas, incluindo anexos |
| `opcoes_filtro_faturamento()` | Centros visíveis e status configurados/observados nos CCs visíveis |
| `atualizar_faturamento(bm_id, ...)` | Atualiza campos administrativos de BM mensal autorizado |
| `status_permitidos_engenharia(status_atual=None)` | Regra pura para opções de status da Engenharia |

**`sim.access_admin`**

- Domínios: `listar_dominios`, `adicionar_dominio`, `desativar_dominio`.
- Contas: `listar_usuarios`, `criar_usuario`, `redefinir_senha`, `definir_usuario_ativo`, `alterar_perfil`.
- Escopos: `listar_centros_custo(empresa_codigo)`, `listar_acessos(usuario_id)`,
  `conceder_acesso(usuario_id, empresa_codigo, centro_custo_id)`,
  `revogar_acesso(usuario_id, acesso_id)`.
- Auditoria: `listar_auditoria(limite=100)`.
- Solicitações: `solicitar_acesso(...)` (**única função pública**, sem principal), `listar_solicitacoes(status)`,
  `contar_solicitacoes_pendentes`, `dominio_autorizado`, `aprovar_solicitacao(id, perfil, centros, parecer)`,
  `recusar_solicitacao(id, parecer)`.
- Todos, exceto `solicitar_acesso`, verificam `administrador_acessos`; não confiar na rota Streamlit como única barreira.
- `criar_usuario` retorna `(usuario_id, senha_temporaria)`; nunca registrar/retornar essa senha em outro lugar.

**`sim.services.common`**

- `Validador`: agrega erros e converte texto, escolhas, moeda e número.
- `transacao(operacao, storage=None)`: commit único; se erro, rollback e limpeza de novos arquivos; exceções
  de domínio passam; erros inesperados são logados e transformados em `PersistenceError`.
- `leitura()`: consulta com tratamento/log técnico.
- `validar_arquivos`, `contar_anexos_finais`, `get_storage`.
- `verificar_anexo(anexo_id)`: confere escopo do BM proprietário e existência do arquivo, sem ler o conteúdo.
- `ler_anexo(anexo_id)`: única rota de leitura do conteúdo; exige escopo do BM proprietário.
- `carregador_anexo(anexo_id)`: função sem argumentos usada pelo `st.download_button` (download sob demanda,
  2026-10-26). O Streamlit a executa em outra thread no clique, onde o ContextVar do principal não existe; por
  isso ela captura o principal na renderização e reentra em `usando_principal` antes de chamar `ler_anexo`.
  Não trocar por leitura direta do storage. A tela (`ui.anexos_download`) não lê bytes ao renderizar.
- Visualizar (2026-10-26): PDF e imagens têm botão **Visualizar** em `ui.anexos_download`, que abre
  `ui._visualizar_anexo` (`st.dialog` largo) com `st.pdf` (depende do pacote oficial `streamlit-pdf`, fixado em
  `requirements.txt`) ou `st.image`. A janela chama `ler_anexo`, então a permissão é conferida de novo. Optou-se
  por janela dentro do SIM em vez de nova aba porque uma aba exigiria URL própria do arquivo, fora da sessão
  autenticada. Tipos aceitos em `ui.tipo_visualizavel`.

## 6. Mapa de arquivos e módulos

### Raiz

- `app.py`: configuração Streamlit; entrada de login; filtro de páginas por perfil; contexto de principal;
  tratamento de erro técnico por referência.
- `requirements.txt`: dependências Python pinadas.
- `alembic.ini`: localização de migrações; URL vem de `sim.config`, não é gravada aqui.
- `.env.example`: exemplos de configuração local; não contém credenciais.
- `.streamlit/config.toml`: tema, limites de upload e binding de desenvolvimento em `127.0.0.1`.
- `README.md`: instalação, utilização e publicação resumida.
- `config/opcoes.json`: opções das listas do SharePoint; várias marcadas como provisórias.

### `sim/`

- `config.py`: caminhos/URL/env.
- `database.py`: engine global, sessões, transação de sessão.
- `models.py`: SQLAlchemy 2.x; colunas, relações, restrições e mixin de auditoria técnica.
- `auth.py`: `Principal`, ContextVar, senha, login, loading de identidade e funções de escopo.
- `access_admin.py`: API administrativa protegida por perfil; criação/redefinição de conta, domínio, grants e
  auditoria.
- `admin_cli.py`: bootstrap/recuperação executados localmente no host.
- `bootstrap.py`: logs, migrations e verificação de versão do esquema no startup.
- `errors.py`: `SimError`, `ValidationError`, `NotFoundError`, `AuthorizationError`, `PersistenceError`.
- `formatters.py`: números, moeda, datas e normalização usada para unicidade.
- `logging_setup.py`: logs rotativos; máscara de senha em URL.
- `options.py`: leitura cacheada de `config/opcoes.json`.
- `storage.py`: armazenador local de anexos.
- `repositories/base.py`: CRUD genérico e acesso a empresa.
- `repositories/asap.py`: queries ASAP.
- `repositories/superus.py`: queries SUPERUS, filtros e carregamentos de BM/CC/anexos.
- `services/common.py`: validação, anexos, contexto de transação/leitura e leitura autorizada de anexo.
- `services/asap.py`: regras/serviços ASAP Engenharia e Administrativo.
- `services/superus.py`: regras/serviços SUPERUS Engenharia e Administrativo.
- `ui/authentication.py`: tela de login, sessão e troca obrigatória de senha.
- `ui/navegacao.py`: telas, módulos, rotas e migalhas.
- `ui/layout.py`: tema aplicado, cabeçalhos, sidebar e cartões.
- `ui/common.py`: controles reutilizados nas telas Python.
- `ui/superus.py`: seletor/estado do centro de custo SUPERUS.
- `ui/tema.py`: identidade visual e caminhos dos logotipos.
- `recarga.py`: recarga coerente dos módulos `sim.*` quando código muda no servidor.

### `telas/`

- `inicio.py`: cartões que são filtrados pelas rotas autorizadas.
- `adm_selecao.py`: seleção apenas das empresas administrativas concedidas.
- `modulo_asap_eng.py`, `modulo_superus_eng.py`, `modulo_asap_adm.py`, `modulo_superus_adm.py`: entradas de
  módulo.
- `asap_eng_bm_mensal.py`, `asap_eng_cadastro.py`, `asap_adm_faturamento.py`: telas ASAP.
- `superus_eng_bm_mensal.py`, `superus_eng_bm_semanal.py`, `superus_eng_cadastro.py`,
  `superus_eng_encerramento.py`, `superus_eng_help.py`: telas SUPERUS Engenharia.
- `superus_adm_faturamento.py`, `superus_adm_planejamento.py`, `superus_adm_atualizar_dados.py`: telas
  SUPERUS Administrativo.
- `controle_acesso.py`: tela exclusiva de `administrador_acessos`.

### Protótipo web antigo

`index.html`, `css/` e `js/` são uma implementação de fase anterior para a ASAP, com dados fictícios. `js/config.js`
seleciona `mock`; `ApiRepository` ainda é uma API futura. `js/main.js` referencia módulos em `js/data/`, que
não existem no checkout analisado. Não usar esse protótipo para concluir que há API, banco compartilhado ou
persistência web. O entrypoint suportado atualmente é `app.py`.

### Diretórios de execução, não versionados

- `data/sim.db`, `data/anexos/`, `data/logs/`: padrão de desenvolvimento/runtime.
- `backups/`: destino de `scripts/backup.py`.
- `.venv/`: ambiente virtual.

Não copiar estes diretórios para Git nem incluir banco/anexos reais nos artefatos públicos.

## 7. Comandos de desenvolvimento e validação

PowerShell, na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m sim.admin_cli criar-primeiro-admin admin@empresa.com "Nome"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\backup.py
```

O comando `criar-primeiro-admin` cria ou migra o banco padrão e exige terminal local. Para testes, cada teste usa
SQLite próprio em diretório temporário; a fixture `ambiente` em `tests/conftest.py` define principal de
controlador geral para manter os testes de domínio independentes do login interativo. Testes de isolamento
criam `Principal` com escopo explícito.

### Testes por objetivo

- `tests/test_access.py`: filtros entre obras, tentativa de acessar/alterar BM e anexo de outra obra, múltiplos
  centros, controlador global, domínio, login e concessão/auditoria.
- `tests/test_asap.py`: serviços ASAP e regras de faturamento/aprovação.
- `tests/test_superus.py`: serviços SUPERUS mensais/semanal/faturamento.
- `tests/test_infra.py`: schema, empresa, FKs, persistência, anexos e erro de transação.
- `tests/test_telas.py`: páginas Streamlit, navegação, login, controle de acesso e fluxos de formulário.
- `tests/test_navegacao.py`: mapa e identidade visual.
- `tests/test_recarga.py`, `tests/test_logs.py`, `tests/test_formatters.py`: infra e utilitários.
- `tests/unit/`, `tests/e2e/`: testes JavaScript do protótipo antigo; não substituem os testes Python.
- Contagem na revisão deste guia: 286 testes Python coletados (inclui `tests/test_importacao_legado.py` e `tests/test_valor_previsto.py`); `pytest -q` passou. `alembic check` também
  confirmou que não há operações de migração pendentes em relação aos modelos.

Ao adicionar operação de negócio, criar teste negativo que prove a negação entre dois centros de custo. Ao
adicionar página nova, revisar o mapa de navegação, a filtragem no `app.py`, o sidebar e testes de acesso.

## 8. Regras de manutenção que não devem ser violadas

1. **Falhar fechado:** serviço invocado sem `Principal` deve negar acesso; não introduzir principal global
   padrão para operação real.
2. **Autorização no serviço:** esconder botão, página ou opção não substitui verificação do centro no serviço.
3. **Anexo protegido:** não ler arquivos diretamente em uma tela; usar `common.ler_anexo`, que valida o dono.
4. **Escopo de listas:** consulta sem filtro de centro deve continuar limitada a IDs permitidos no próprio SQL.
5. **Escrita:** criação de BM exige grant no CC de destino; edição/exclusão/faturamento exigem grant no CC do BM.
   Se um fluxo permitir trocar o CC do BM, exigir autorização nos dois centros.
6. **Cadastro de CC:** somente `controlador_geral` cria; administrador de acessos não recebe privilégio de
   negócio automaticamente.
7. **Sessões:** reset, desativação, alteração de perfil e alteração de concessões incrementam a versão e
   invalidam sessões existentes.
8. **Segredos:** nunca registrar senha/hash temporário/token/URL com credencial; log não substitui auditoria.
9. **Migrações:** não alterar revisions aplicadas; validar upgrade/downgrade em banco temporário e no driver alvo.
10. **Transação de arquivo + banco:** preservar compensação de arquivos de `services/common.py`.
11. **Valores monetários:** manter `Decimal`, `Numeric` e parsing explícito pt-BR.
12. **Opções:** não completar valores SharePoint por suposição; atualizar a origem/situação em `opcoes.json`.
13. **Privacidade do código:** não publicar repositório, workflow, logs, `.env`, bancos ou anexos.
14. **Compatibilidade:** a interface principal é Streamlit; não adicionar dependência do protótipo sem decisão
    explícita de migração.

## 9. Pendências e sequência recomendada

### Bloqueadores antes de uso público

1. **Definir nuvem e responsável operacional.** O provedor não foi informado. Não criar DNS, listener público,
   configuração de rede nem integração específica assumindo Azure/AWS.
2. **Reavaliar autenticação.** A senha local foi implementada conforme preferência atual, mas para convidados
   externos deve haver aprovação da TI. Recomendação: identidade gerenciada (Entra/OIDC ou equivalente), MFA e
   redefinição no provedor; se mantido login local, adicionar MFA, política/rate-limit por origem e processo
   seguro de recuperação.
3. **Definir banco SQL real.** Escolher SGBD/driver, testar migration DDL, precisão `Numeric`, constraints,
   índices, transações e concorrência. Aplicação já seleciona URL por `DATABASE_URL`, mas não há credencial,
   servidor ou driver corporativo configurado.
4. **Definir storage de anexos compartilhado.** Substituir `LocalFileStorage` antes de múltiplas instâncias ou
   container com disco efêmero.
5. **Configurar produção:** HTTPS, segredo em vault, banco privado, backup/restore ensaiado, ambiente de
   homologação, métricas/logs, política de retenção, processo de incidentes e acesso restrito ao host.
6. **Auditoria e privacidade:** revisar prazo de retenção e acesso à tabela de auditoria; avaliar trilha de
   alterações de dados operacionais além da trilha de permissões.
7. **Importação SharePoint:** obter exportações autorizadas; conferir esquemas, duplicatas, lookups, anexos e
   valores provisórios; preparar ferramenta de migração com reconciliação.
8. **Conteúdo funcional:** confirmar opções de escolha e os campos/fluxos externos listados no README.

### Limites atuais conhecidos

- Sem MFA; login local usa senha e bloqueio por conta, ainda não por IP.
- Reset no painel gera senha temporária que precisa ser entregue manualmente em canal seguro.
- Recuperação de senha por código no e-mail implementada; envio real depende de SMTP do TI. Não há convite
  automático por e-mail.
- Login local não comprova identidade corporativa; allowlist de domínio e provisionamento manual são controles
  de acesso, não SSO.
- Armazenamento de anexo e SQLite são locais.
- `server.address` está explicitamente em `127.0.0.1` para desenvolvimento. Não ampliar esse binding em máquina
  compartilhada sem proxy/HTTPS/autenticação e firewall.
- Telas devem acessar páginas opcionais com `P.get(...)`/`if chave in P`: o usuário de obra não recebe `asap_cc`
  nem `sup_cc`. Até 2026-10-26 as telas SUPERUS e a visão geral do módulo usavam `P["sup_cc"]` e
  quebravam para esse perfil (corrigido; `tests/test_telas.py::test_usuario_de_obra_*` cobre).
- A UI não implementa permissões por função operacional (Engenharia vs Administrativo): todo usuário comum
  pode executar os fluxos disponíveis para os centros que lhe foram concedidos, conforme a solicitação atual.
  Se isso mudar, incluir capability separada e aplicar também nos serviços.
- Dados SharePoint reais, domínios reais e nomes de provedores não foram fornecidos.

## 10. Notas para a próxima IA

- Primeiro leia `README.md`, este guia e as definições em `sim/models.py`, `sim/auth.py` e `sim/services/`.
- Confirme os arquivos existentes no checkout; documentação antiga pode citar `docs/` e `referencias_power_apps/`
  que não estão necessariamente presentes.
- Não conclua que o projeto está publicado porque há uma configuração de `DATABASE_URL`: isso só permite
  selecionar um driver quando o operador o configurar.
- Não conclua que “código fechado” é obtido escondendo arquivos no navegador: proteger o código exige controle
  do repositório, build e artefato de servidor; autorização de dados é um requisito separado.
- Antes de aplicar políticas novas, escreva testes para dois usuários com CCs diferentes e tente ler, listar,
  alterar, excluir e baixar anexo cruzando os escopos.
- Se a TI escolher identidade externa, manter `Principal`/grants e substituir apenas o mecanismo que estabelece
  a identidade, sem duplicar permissões no provedor e no SIM sem sincronização definida.
- Toda recomendação de implantação deve identificar explicitamente a dependência ainda pendente (provedor,
  SQL, storage, MFA ou configuração da TI); não representar desenvolvimento local como produção pronta.
