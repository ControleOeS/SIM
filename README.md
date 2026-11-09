# SIM — Sistema Integrado de Medições (Streamlit + Python + SQL)

Aplicação única que substitui os quatro Power Apps do SIM da O&S Gestão:

| Empresa | Módulo | Telas |
| --- | --- | --- |
| ASAP | Engenharia | BM Mensal, Cadastro Centro de Custo |
| ASAP | Administrativo | Faturamento |
| SUPERUS ENGENHARIA | Engenharia | BM Mensal, BM Semanal, Cadastro, Encerramento, Central de Ajuda |
| SUPERUS ENGENHARIA | Administrativo | Faturamento, Planejamento (mensal e semanal), Atualizar dados |

> **Situação atual: ambiente local de desenvolvimento.** O login local e o controle por centro de custo estão
> implementados, mas os dados e anexos ainda ficam em armazenamento local. A publicação em nuvem segue bloqueada
> até a escolha da plataforma, configuração de HTTPS/MFA, armazenamento compartilhado e validação operacional.
> O código-fonte deve permanecer em repositório privado; este checkout ainda não está configurado como Git e
> não tem repositório privado remoto. Não disponibilize o servidor de desenvolvimento na rede.

---

## 1. Instalação no Windows (uma vez)

Pré-requisitos: [Python 3.12 ou superior](https://www.python.org/downloads/) (marque *Add python.exe to PATH*
na instalação) e [VS Code](https://code.visualstudio.com/) com a extensão **Python** (a pasta já a recomenda).

1. No VS Code: **Arquivo → Abrir Pasta…** e escolha a raiz `sim-os-gestao-main`.
2. Abra o terminal: **Terminal → Novo Terminal** (PowerShell).
3. Execute, um por vez:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Os comandos chamam o Python do ambiente virtual diretamente, sem `Activate.ps1`, por isso funcionam mesmo
quando o Windows bloqueia scripts do PowerShell.

## 2. Executar

No terminal do VS Code, na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

O navegador abre em **http://localhost:8501**. Para encerrar, volte ao terminal e tecle `Ctrl+C`.

Alternativa: aba **Executar e Depurar** (Ctrl+Shift+D) → **SIM (Streamlit)** → ▶.

**Se o código for alterado com o SIM aberto:**
- O `app.py` detecta a mudança em `sim/` e recarrega todos os módulos juntos (`sim/recarga.py`). Isso evita
  misturar versões antigas e novas.
- Se uma tela mostrar erro, ela exibe um código de referência, os detalhes vão para `data\logs\sim.log` e as
  demais telas continuam acessíveis.
- Mudanças em `app.py`, `.streamlit/config.toml` ou nas migrações exigem reiniciar: `Ctrl+C` no terminal e o
  comando acima de novo.

Na primeira execução, o SIM cria o banco e aplica as migrações automaticamente. Com o banco sem nenhuma conta, a
página de login mostra a **Configuração inicial**: informe nome, e-mail e senha (mínimo 8 caracteres) para criar o
administrador. Essa tela some depois do primeiro usuário. Também é possível criar pelo terminal local (o comando pede
a senha sem exibi-la e só funciona se o banco não tiver nenhuma conta):

```powershell
.\.venv\Scripts\python.exe -m sim.admin_cli criar-primeiro-admin admin@empresa.com "Nome do administrador"
```

O domínio do administrador inicial é autorizado automaticamente. Novas pessoas pedem conta na aba
**Solicitar acesso** da tela de login (nome, e-mail, senha, classificação e centro de custo do contrato, em texto
livre). O pedido aparece no painel **Controle de acesso**, onde um administrador/aprovador escolhe a classificação
final e os centros de custo liberados e aprova ou recusa com parecer. Aprovadores podem aprovar novos
aprovadores. O perfil **Administrador geral** reúne o controlador geral (todas as obras) e o aprovador de acessos.

**Esqueci a senha:** na aba de mesmo nome do login, a pessoa recebe um código de 6 dígitos no e-mail (válido por
15 minutos) e cria uma senha nova. O envio é configurado em `.env` (`SIM_EMAIL_MODO`, ver `.env.example`). Sem
conta de envio, use `SIM_EMAIL_MODO=arquivo` só em desenvolvimento: os e-mails ficam em `data\emails\`. Nada é liberado sem aprovação, e o e-mail informado não é verificado automaticamente.
Confirme a identidade por canal independente antes de entregar a senha temporária. O usuário precisa trocá-la
no primeiro acesso; administradores podem redefinir senhas, mas nunca consultar a senha atual.

O sistema começa **vazio**: não há dados fictícios nem importação das listas SharePoint. O administrador com
perfil **Controlador geral** deve cadastrar centros de custo antes de concedê-los aos usuários. Depois:
1. Cadastre um centro de custo (ASAP ou SUPERUS) como controlador geral.
2. Lance BMs na tela BM Mensal da empresa.
3. Confira e altere o faturamento no módulo Administrativo.

Se for cadastrar registros só para teste, use nomes que os identifiquem, por exemplo o prefixo `DEV-`.

### Navegação

```
Início — "Bem-vindo ao SIM"
 ├─ ASAP ..................... ASAP · Engenharia → BM Mensal, Cadastro Centro de Custo
 ├─ Superus Engenharia ....... Superus · Engenharia → BM Mensal, BM Semanal, Cadastro, Encerramento, Central de Ajuda
 └─ Administrativo ........... seleção de empresa
      ├─ ASAP ADM ............ Faturamento
      └─ Superus ADM ......... Faturamento, Planejamento, Atualizar dados
```

- Cada módulo abre por uma **Visão geral**, que equivale à "Tela Inicial" de cada Power App. A barra lateral
  mostra só as telas do módulo aberto.
- A barra lateral também tem **Selecionar área**, que volta ao início. Nos módulos administrativos, há ainda
  **Trocar empresa (Administrativo)**.
- O cabeçalho de todas as telas mostra a O&S Gestão e o caminho atual, por exemplo
  `O&S Gestão › Administrativo › Superus ADM › Faturamento`. À direita aparece o logotipo da empresa do módulo.
- Os endereços continuam diretos, por exemplo `http://localhost:8501/asap-bm-mensal`. Recarregar a página
  (F5) inicia uma nova sessão: o centro de custo escolhido precisa ser selecionado de novo.

### Identidade visual

| Item | Onde |
| --- | --- |
| Logotipos oficiais (cópias exatas dos arquivos recebidos) | `assets/logos/oes-gestao.jpg`, `assets/logos/asap.png`, `assets/logos/superus-engenharia.png` |
| Paleta, logotipos e CSS centralizados | `sim/ui/tema.py` |
| Tema do Streamlit (cores, bordas, tabelas, barra lateral) | `.streamlit/config.toml` |
| Cabeçalho, barra lateral, cartões, estados vazios | `sim/ui/layout.py` |
| Mapa de navegação (áreas, módulos, telas) | `sim/ui/navegacao.py` |

As cores foram extraídas dos próprios logotipos:

| Empresa | Cores | Uso |
| --- | --- | --- |
| O&S Gestão | petróleo `#00495C`; lima `#C5EA2A` | Identidade principal: botões, links, títulos de seção. O lima aparece só em faixas decorativas |
| ASAP | azul `#1641FF`, azul escuro `#0027AF` | Acento das telas da ASAP |
| Superus Engenharia | verde escuro `#25382D`, verde-lima `#97C03B` | Acento das telas da Superus |

O lima e o verde-lima têm pouco contraste sobre branco, por isso não são usados em textos.

Padrão dos botões:

| Botão | Aparência |
| --- | --- |
| Salvar | Preenchido em petróleo |
| Cancelar / Limpar | Contorno |
| Excluir | Contorno vermelho |
| Confirmar exclusão | Vermelho preenchido, dentro da caixa de confirmação |

## 3. Onde ficam os dados e como fazer backup

| O quê | Onde |
| --- | --- |
| Banco de dados | `data\sim.db` (SQLite, arquivo único) |
| Anexos | `data\anexos\asap\bm\<id>\`, `data\anexos\superus\bm_mensal\<id>\`, `data\anexos\superus\bm_semanal\<id>\` |
| Log de erros técnicos | `data\logs\sim.log` |
| Opções das listas de escolha | `config\opcoes.json` |

Fechar e reabrir o Streamlit **não apaga nada**: tudo fica em `data\`. A pasta `data\` está no `.gitignore`
e nunca vai para o Git.

**Backup** (pode ser feito com o SIM aberto):

```powershell
.\.venv\Scripts\python.exe scripts\backup.py
```

Gera `backups\sim-backup-AAAAMMDD-HHMMSS.zip` com o banco (cópia consistente pela API de backup do SQLite) e
todos os anexos. Guarde o zip em local seguro, fora deste computador.

**Restauração:**
1. Feche o SIM.
2. Renomeie a pasta `data\` atual, para guardá-la.
3. Crie uma nova `data\` e extraia nela o `sim.db` e a pasta `anexos\` do zip.
4. Inicie o SIM.

Para mudar o local dos dados, copie `.env.example` para `.env` e ajuste `SIM_DATA_DIR`.

## 4. Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Resultado atual: **286 testes Python, todos passando nesta revisão**. Cada teste usa um banco próprio, criado pelas migrações do
Alembic, e nunca toca em `data\sim.db`.

| # | Verificação exigida | Onde |
| --- | --- | --- |
| 1 | CRUD de centros de custo (ASAP e SUPERUS) | `test_asap.py::test_crud_centro_custo`, `test_superus.py::test_crud_centro_custo` |
| 2 | CRUD de BMs mensais | `test_asap.py::test_crud_bm`, `test_superus.py::test_crud_bm_mensal` |
| 3 | BMs semanais (criar, consultar, filtrar, editar, excluir) | `test_superus.py::test_bm_semanal` |
| 4 | Separação ASAP × SUPERUS | `test_infra.py::test_separacao_entre_empresas` |
| 5 | Filtros (CC, mês, status, semana, PO parcial) | `test_asap.py::test_filtros_faturamento`, `test_superus.py::test_filtros_mensal_e_po_parcial`, `test_bm_semanal` |
| 6 | Data de aprovação automática (ASAP) | `test_asap.py::test_data_aprovacao_*`, `test_regra_pura_aprovacao_nao_sobrescreve` |
| 7 | Restrições de status | `test_asap.py::test_status_faturamento_so_atual_ou_faturado_total`, `test_superus.py::test_status_*` |
| 8 | Integridade dos relacionamentos | `test_infra.py::test_banco_recusa_*`, `test_asap.py::test_bm_com_cc_inexistente_e_recusado`, `test_cc_com_bm_nao_pode_ser_excluido` |
| 9 | Persistência após reiniciar | `test_infra.py::test_dados_persistem_apos_reiniciar` |
| 10 | Erros de gravação | `test_infra.py::test_falha_no_commit_vira_mensagem_e_nao_deixa_lixo`, `test_telas.py::test_erro_de_validacao_*` |
| 11 | Edição não cria registros | `test_asap.py::test_edicao_de_bm_inexistente_nao_cria`, `test_faturamento_nao_cria_registro` (ASAP e SUPERUS), `test_atualizar_dados_nao_cria_cc` |
| 12 | Upload e recuperação de anexos | `test_infra.py::test_anexos_upload_download_e_remocao`, `test_anexo_vazio_recusado` |
| 13 | Login, domínio autorizado, bloqueio, escopos por centro e controlador geral | `tests/test_access.py`, `tests/test_telas.py::test_login_local_e_conta_inicial_nao_configurada` |
| — | Todas as 18 telas abrem (banco vazio e com dados) e fluxos de tela | `test_telas.py` |
| — | Navegação: início com 3 áreas, seleção ADM, módulos levam às telas corretas, cabeçalho O&S + coligada, barra lateral só do módulo | `test_telas.py`, `test_navegacao.py` |
| — | Logotipos oficiais presentes e sem redimensionamento; cores da paleta | `test_navegacao.py` |

O que **não** é testado automaticamente:
- O `AppTest` do Streamlit não simula envio de arquivos nem clique em linha de tabela. Esses fluxos de
  tela (anexar, selecionar um BM para editar) foram cobertos na camada de serviço; confira-os manualmente no
  navegador.
- O comportamento visual em celular e em navegadores diferentes não foi testado.

## 5. O que foi implementado

### SIM ASAP — Engenharia
- **BM Mensal**
  - A tela começa pela "Escolha seu Centro de Custos". O OK exige uma seleção, e o CC escolhido vira o padrão
    dos novos BMs.
  - A lista mostra todos os BMs por ID decrescente, com valores em R$ no padrão brasileiro.
  - Inclusão, edição e exclusão (com confirmação), com anexos reais (upload e download).
  - Anexos em PDF ou imagem têm o botão **Visualizar**, que abre o arquivo numa janela dentro do SIM.
  - Na edição, o formulário carrega o CC do próprio registro.
  - Valor Emitido aparece só para consulta.
- **Data de aprovação:** ao salvar com status `BM Aprovado pelo Cliente` e a data vazia, grava a data e hora
  atuais. Uma data já gravada nunca é sobrescrita.
- **Cadastro de Centro de Custo:** só inclusão, como no original, com validação dos obrigatórios.
  - Início e Fim de Medição: dias de 1 a 31 em lista suspensa, com a mesma regra da SUPERUS (31 em fevereiro = 28).
  - Melhorias: bloqueio de título duplicado e lista de consulta dos CCs abaixo do formulário.

### SIM ASAP — Administrativo
- **Faturamento**
  - Filtros por mês, status e centro de custo, mais um botão "Limpar filtros".
  - Para alterar, selecione um BM na lista. Campos editáveis: Valor Emitido, Status (o atual ou `Faturado Total`,
    como no original) e Anexos.
  - Não existe modo de inclusão.

### SIM SUPERUS ENGENHARIA
- **Centro de custo:** "Escolha seu Centro de Custos" → "Confirme seu Centro de Custo", que mostra o CC,
  Obra/Cliente e Gestor. A escolha vale para BM Mensal, BM Semanal e Encerramento, e o vínculo é sempre pelo ID.
- **BM Mensal**
  - Campos do original, com obrigatórios iguais.
  - Status restrito a `BM em Análise do Cliente` e `BM Aprovado pelo Cliente`. Um status gravado pelo
    faturamento pode ser mantido na edição, mas não escolhido.
  - Filtro de mês, inclusão, edição, exclusão e anexos. A lista se atualiza após a exclusão.
- **BM Semanal:** nome do arquivo, mês, semana, valor acumulado e anexos, sem status. Filtros por mês e semana.
  Inclusão, edição e exclusão.
- **Cadastro:** coligada, CC, gestor, obra/cliente, início e fim de medição, todos obrigatórios.
  - Coligada: lista com SUPERUS ENGENHARIA, ACPL e SUPERUS HOLDING (o módulo SUPERUS reúne as três).
  - Início e Fim de Medição são dias de 1 a 31, sem mês. Se o mês tiver menos dias, vale o último dia dele
    (31 em fevereiro = 28). Início maior que o fim (ex.: 21 a 20) vai do dia 21 do mês anterior ao dia 20.
    A lista de centros mostra o período calculado para o mês atual.
  - Critério de duplicidade: o mesmo código (Título) do CC, sem diferenciar maiúsculas e espaços extras. O
    original pedia ao usuário que conferisse "o seu código" antes de cadastrar.
- **Encerramento** (também na ASAP): quem tem acesso ao centro de custo solicita o encerramento com justificativa
  obrigatória; Controlador geral ou Administrador geral aprova ou recusa, e também pode encerrar ou reativar
  diretamente (inclusive pelo checkbox **Ativo** na tabela do cadastro). Centro encerrado não aceita novos BMs. A regra dos 95% **não** foi
  implementada (seção 8).
- **Central de Ajuda:** glossário transcrito do original, sem acréscimos.

### SIM SUPERUS — Administrativo
- **Faturamento**
  - Filtros por CC, status, mês e PO. O PO aceita trecho do texto, sem diferenciar maiúsculas.
  - Campos editáveis: Status, Valor Liberado, Valor Emitido, Mês, FRS, PO e Anexos.
  - Valor Aprovado, Glosa, Valor BM e Postergado aparecem só para consulta.
- **Planejamento:** consulta de BMs mensais (filtros CC e mês) e semanais (filtros CC, mês e semana).
- **BM Mensal — uma resposta por mês** (2026-10-27): cada CC tem um único BM por mês. O gestor anexa todos os BMs
  do mês nessa resposta e informa o valor somado; o SIM avisa ao escolher um mês já usado e recusa ao salvar
  (também ao mudar o mês na edição ou no Faturamento). Conta também o histórico importado; os meses repetidos do
  histórico continuam editáveis. Índice único parcial no banco (`uq_superus_bm_mensal_mes`, só BMs novos).
  - Só aparecem meses já iniciados: cada mês fica disponível a partir do dia 1º (proteção contra lançamento
    adiantado). Exceção: em janeiro, também dezembro, gravado no ano anterior.
  - **BM por BM** (2026-10-27): o gestor preenche uma lista com uma linha por BM (identificação, valor do BM e
    valor aprovado). Valor BM/PO e Valor Aprovado são as somas, em campos não editáveis que acompanham a
    digitação; a comparação com o previsto usa a soma e o pedido de justificativa aparece na hora. Linhas em
    `superus_bm_mensal_itens`; BMs do histórico abrem na edição com uma linha com o valor já lançado. O
    Faturamento vê a lista.
  - O gestor não escolhe o ano: é o ano da data do lançamento (dezembro lançado em janeiro: ano anterior). Na
    edição, as mesmas regras valem a partir da data em que o BM foi lançado; o mês e o ano já gravados são mantidos.
    Testes fixam a data em `tests/conftest.py`.
- **Valor Previsto** (2026-10-27): quanto se espera medir em cada CC no mês.
  - Escolhido o mês, todos os CCs aparecem numa tabela editável; valor apagado remove o previsto.
  - Só Controle e Controle Geral alteram; Faturamento consulta.
  - No **BM Mensal**, Mês e Ano ficam acima do formulário e o previsto do mês aparece assim que o gestor os escolhe.
  - Se o Valor BM/PO ficar **mais de 5% acima ou abaixo** do previsto, o BM exige justificativa. Acima, o SIM
    pergunta qual foi a boa estratégia utilizada; abaixo, quais problemas fizeram o valor fugir do refinado
    anterior. Previsto zero com BM acima de zero também exige. Sem previsto no mês, não exige nada.
  - A comparação é por BM. Na edição, só é refeita se valor, mês ou ano mudarem; o previsto usado fica gravado
    no BM e o Faturamento vê o previsto e a justificativa.
- **Atualizar dados:** Quantidade de BMs, Cidade e Nº do Contrato de um CC selecionado. Não cria registros.

### Defeitos do original corrigidos

| Defeito | Correção |
| --- | --- |
| Salvar sem selecionar registro criava BM/CC novo (ASAP ADM, SUPERUS ADM Faturamento e Atualizar dados) | Telas administrativas só gravam sobre um registro selecionado; o serviço exige ID existente |
| Mensagem de sucesso mesmo com falha (SUPERUS Cadastro e Faturamento) | Sucesso só é exibido depois do commit confirmado |
| Edição trocava o CC (ASAP, P-01) | Formulário de edição carrega o CC do registro; na SUPERUS o CC do BM não muda |
| SubmitForm + Patch em sequência (ASAP, P-02) | Uma única transação grava todos os campos e anexos |
| Exclusão não atualizava a lista (SUPERUS BM Mensal) | Lista é recarregada após excluir |
| Filtros globais que nunca eram limpos | Botão "Limpar filtros" reinicia todos; mudar filtro limpa a seleção da tabela |
| BMs ligados ao CC pelo Título (CCs com mesmo nome se misturavam) | Chave estrangeira pelo ID; o banco recusa CC inexistente |
| Erros apagavam o formulário / mensagens técnicas | O formulário mantém o que foi digitado; mensagens claras; detalhes técnicos no log com código de referência |
| Valores digitados dependiam do idioma do navegador | Leitura pt-BR explícita (`1.234,56`), com validação de número, sinal e casas decimais |
| Exclusão sem confirmação ou modal inoperante | Confirmação "Sua ação não terá volta!" em todas as exclusões |
| Mensagem de erro presa na tela | O erro some assim que o usuário altera qualquer campo e volta a ser conferido na próxima tentativa de salvar |

## 6. Opções das listas de escolha (`config/opcoes.json`)

Os valores das colunas de escolha do SharePoint (Ano, Mês, Status, Tipo, Semana, EncerramentoManual) são
carregados pelo Power Apps em tempo de execução e **não estão nos pacotes exportados**. Por isso ficam
centralizados em `config/opcoes.json`, cada um marcado como `confirmado` ou `provisorio`, com a origem. Na tela,
campos com opções provisórias mostram ⚠.

| Opção | Situação | Origem |
| --- | --- | --- |
| Meses ASAP (Janeiro…Dezembro) | confirmado | filtro do SIM ASAP ADM |
| Status SUPERUS Engenharia (2 valores) | confirmado | fórmula do BM Mensal SUPERUS |
| `BM Aprovado pelo Cliente`, `Faturado Total` (ASAP) | confirmados | fórmulas do SIM ASAP e ASAP ADM |
| Status SUPERUS completo (7), Tipo (BM, PO, SPOT, Indenização), Semana 1–5 | confirmado | exportações das listas BMs/BM Semanal (2026-10-27) |
| Ano, EncerramentoManual, meses SUPERUS, Status ASAP | **provisório** | a confirmar com as exportações das listas |

Para alterar: edite o arquivo e reinicie o SIM. Registros gravados com valores fora da lista continuam visíveis
e editáveis.

## 7. Estrutura do projeto

```
app.py                  ponto de entrada: inicialização, gate de login, navegação autorizada
telas/                  páginas Streamlit, incluindo controle de acesso
assets/logos/           logotipos oficiais (O&S Gestão, ASAP, Superus Engenharia)
sim/
  config.py             configurações via variáveis de ambiente / .env
  database.py           engine e sessões SQLAlchemy (único ponto que conhece o banco)
  models.py             entidades, relações de negócio, contas, grants e auditoria
  auth.py               hashing/senha, sessão, identidade do usuário e verificação de escopos
  access_admin.py       administração de domínio, contas, funções e permissões por CC
  admin_cli.py          bootstrap local do primeiro administrador e recuperação de admin
  repositories/         consultas e persistência (sem regra de negócio)
  services/             regras, validações, transações e enforcement de escopos
  storage.py            armazenamento local provisório de anexos
  bootstrap.py          logs, migrações e verificação do esquema no início
  logging_setup.py      logs rotativos com máscara de senha em URLs
  errors.py             erros de domínio e autorização
  options.py            leitura das opções de config/opcoes.json
  formatters.py         moeda, números e datas pt-BR
  ui/                   authentication.py, tema.py, layout.py, navegação e componentes comuns
migrations/             migrações Alembic (0001 esquema, 0002 empresas, 0003 controle de acesso, 0004 solicitações,
                        0005 perfil administrador geral, 0006 códigos de redefinição de senha,
                        0007 encerramento de centro de custo, 0008 edição simultânea,
                        0009 perfis controle)
config/opcoes.json      opções das colunas de escolha
scripts/backup.py       backup do SQLite + anexos
tests/                  testes automatizados (pytest), inclusive isolamento por obra e login
index.html, css/, js/   protótipo HTML da fase 1; separado da aplicação principal
docs/                   documentação de desenvolvimento e continuidade para agentes
```

**Modelo de dados.** ASAP e SUPERUS têm tabelas próprias, porque as listas SharePoint têm colunas diferentes:

| Tabela | Lista SharePoint original |
| --- | --- |
| `empresas` | (nova) unidades da holding: ASAP, SUPERUS. Base para permissões por empresa |
| `asap_centros_custo` | Lista de Apoio ASAP |
| `asap_bms` | BMs ASAP |
| `superus_centros_custo` | Lista de Apoio (SUPERUS) |
| `superus_bms_mensais` | BMs (SUPERUS) |
| `superus_bms_semanais` | BM Semanal (SUPERUS) |
| `anexos` | anexos dos três tipos de BM; arquivo em disco + metadados (nome, tamanho, SHA-256) |
| `usuarios` | contas locais, hash de senha, perfil, bloqueio e versão de sessão |
| `dominios_permitidos` | lista explícita dos domínios que podem receber contas provisionadas |
| `acessos_centros_custo` | concessões individuais ASAP/SUPERUS por centro de custo |
| `auditoria_acessos` | trilha das alterações de usuários, domínios, perfis e grants |
| `solicitacoes_acesso` | pedidos de conta feitos no login, com CC informado, parecer e decisão do aprovador |

Todas as colunas das listas foram preservadas, inclusive as que nenhuma tela usa (FRS, UltimoAlerta, Meta BM,
prazos etc.). Cada coluna traz no código o nome interno de origem (`# sp: ...`), para a futura importação.
Valores em R$ usam `Numeric(15,2)`, nunca ponto flutuante. Toda tabela de negócio tem `criado_em` e
`atualizado_em`.

## 8. Limitações e pendências

**Dependem de informação que não está nos pacotes:**
- Valores completos das escolhas: Status, Ano, Tipo, Semana, Cidade (ASAP), EncerramentoManual e Competência
  de Emissão. Os meses da SUPERUS também precisam de confirmação. Precisam das exportações das listas.
- **Regra dos 95%:** aparece só como texto na tela Encerramento original. Não há fórmula; provavelmente estava
  num fluxo do Power Automate. **Não implementada.**
- **Fluxos externos** (Power Automate): alertas (`UltimoAlerta`), envio de BM para FRS, e-mails, preenchimento
  de prazos, Data de Faturamento, Mês de Apuração e metas. As colunas existem; nenhuma automação foi inventada.
- Significado exato de Início/Fim de Medição (provavelmente dia do mês), Quantidade de BMs e FRS (guardado como
  número, como na lista).
- Validações e permissões configuradas nas próprias listas SharePoint.
- Se `BM Semanal` (SUPERUS ADM) e `BM Semanal_1` (SUPERUS) são a mesma lista. Os nomes diferem entre os apps;
  foram tratadas como uma só.

**Diferenças conscientes em relação ao original:**
- O CC confirmado na SUPERUS vale para toda a sessão do navegador, e o botão "Mudar centro de custo" troca de
  CC. No original, o pop-up reaparecia a cada visita.
- O "Comunicado 03/06/2026" do BM Mensal SUPERUS (aviso pessoal com contatos) não foi reproduzido.
- Listas SUPERUS sem ordenação no original aparecem por ID decrescente.
- Valores aparecem com 2 casas decimais em todas as telas. Algumas galerias originais mostravam sem decimais.

**Ainda não feito nesta fase (por decisão):**
- Visão consolidada da holding.
- Importação dos dados reais. Antes dela, é preciso autorização e uma etapa de validação: colunas, duplicados,
  CCs inexistentes, anexos.
- Exclusão de centros de custo pela tela. O serviço existe e bloqueia CCs com BMs, mas nenhum app original
  tinha essa tela.
- MFA, integração de redefinição por e-mail e limitação de tentativas por IP. O login local atual é uma etapa
  inicial e **não deve ser exposto à Internet sem avaliação e controles adicionais da TI**.

## 9. Migração para o banco corporativo e publicação (para o TI)

### 9.1 Trocar o banco
A aplicação só conhece o banco por `DATABASE_URL`, lida pelo SQLAlchemy em `sim/database.py`. Telas, serviços e
repositórios não usam SQL específico do SQLite.

1. Definir com o TI o SGBD, o driver Python e a URL. Instale o driver em `requirements.txt`: por exemplo
   `pyodbc` para SQL Server ou `psycopg` para PostgreSQL. A escolha é do TI.
2. Criar o banco vazio e um usuário só com as permissões necessárias.
3. Configurar `DATABASE_URL` no servidor, por variável de ambiente ou cofre de segredos, **nunca no código**.
4. Criar o esquema com as migrações: `.\.venv\Scripts\python.exe -m alembic upgrade head`.
5. Em produção, usar `SIM_AUTO_MIGRATE=false`: a aplicação só confere a versão do esquema e não altera o banco.
6. Rodar os testes apontando para um banco de homologação (ajuste em `tests/conftest.py`).

**Pontos a revisar no banco escolhido (só mudar a URL não basta):**
- **Tipos:**
  - `Numeric` usa DECIMAL nativo nos bancos corporativos; no SQLite, o SQLAlchemy faz a conversão (aviso
    suprimido nos testes).
  - `DateTime` é gravado em UTC sem fuso. Avaliar `DATETIME2`/`timestamptz`.
  - `Text` vira `NVARCHAR(MAX)`/`TEXT`. Confirmar o *collation* para acentos e para comparação sem caixa.
- **Unicidade:** `titulo_chave` (título normalizado) garante CC único por empresa. Confirmar o *collation* e o
  limite de tamanho de índice (255 caracteres).
- **Chaves estrangeiras:**
  - BM → CC usa `RESTRICT`; anexo → BM usa `CASCADE`.
  - No SQL Server, verificar se os três `CASCADE` de `anexos` são aceitos (não há ciclos).
  - O SQLite só aplica FKs com `PRAGMA foreign_keys=ON`, já feito em `database.py`.
- **Nomes de constraints:** convenção explícita em `models.py`. O maior nome tem 61 caracteres, o que serve para
  SQL Server e PostgreSQL. Bancos com limite de 30 exigiriam encurtar.
- **CheckConstraint** `ck_anexos_um_dono` usa `CASE`, que é SQL padrão.
- **Transações e concorrência:** cada gravação é uma transação. Com vários usuários, avaliar o nível de
  isolamento e o controle de edição simultânea, que hoje segue "o último a salvar vence", como no SharePoint.
- **Migrações:** foram geradas no SQLite com `render_as_batch`. Rode `alembic upgrade head --sql` para revisar
  o DDL no banco escolhido antes de aplicar.
- **Importação dos dados do SharePoint:**
  - Montar um script à parte que leia as exportações, valide os dados e grave pelos serviços (que aplicam as
    validações).
  - Mapear o lookup pelo ID do SharePoint.
  - Baixar os anexos para o armazenamento definitivo.

### 9.2 Anexos
O armazenamento em `data\anexos` é **provisório** e local. Na publicação:
1. Escolher um armazenamento compartilhado: servidor de arquivos, SharePoint/OneDrive ou blob storage.
2. Implementar uma classe com a mesma interface de `LocalFileStorage` (`gravar`, `ler`, `existe`, `remover`) e
   trocá-la em `sim/services/common.py::get_storage`.
3. Migrar os arquivos, mantendo `caminho_relativo`.

### 9.3 Hospedagem e autenticação (antes de qualquer acesso de funcionários)
- O login local está implementado. Contas não se registram sozinhas, domínio deve estar autorizado e cada
  usuário comum recebe concessões explícitas por centro de custo. O perfil controlador geral alcança todas as
  empresas e obras; administrador de acessos gerencia contas sem receber automaticamente acesso aos dados.
- Senhas são armazenadas como PBKDF2-HMAC-SHA256 com salt individual. O usuário troca senha temporária no
  primeiro login; após cinco falhas consecutivas a conta fica bloqueada por 15 minutos. Redefinições
  incrementam a versão de sessão e encerram sessões anteriores.
- O administrador só **redefine**, nunca visualiza a senha. Senhas temporárias são mostradas uma vez na tela
  de controle; devem ser transmitidas por canal seguro.
- O sistema ainda **não implementa MFA**, e-mail de recuperação nem rate limit por IP. Como o público inclui
  usuários externos, não liberar acesso público até a TI aprovar esses riscos ou migrar para identidade
  corporativa com MFA.
- A tela e os serviços verificam permissões; consultas filtram por escopo e operações sobre registros/anexos
  revalidam a concessão no servidor. Não remova essas verificações ao refatorar.
- **Rede e segurança:**
  - O `.streamlit/config.toml` prende o servidor local a `127.0.0.1`. A plataforma só pode sobrescrever isso
    após estar atrás de HTTPS e com autenticação, banco e armazenamento configurados.
  - **Nunca expor o banco SQL à internet**; só o servidor da aplicação acessa o banco.
  - O provedor de nuvem ainda não foi escolhido. Registrar a decisão antes de criar arquivos específicos do
    provedor, endpoints públicos ou configuração de rede.
- **Operação:**
  - `scripts/backup.py` cobre somente SQLite local. Em produção, definir backup/restore do banco e anexos com a TI.
  - Logs centralizados, sem credenciais. O log já mascara senhas em URLs.
  - Ambiente de homologação separado.

### 9.4 Provisionamento de acesso local
1. Criar o administrador inicial diretamente no host:
   `.\.venv\Scripts\python.exe -m sim.admin_cli criar-primeiro-admin email "Nome"`.
2. O primeiro domínio é incluído automaticamente; outros são geridos no painel **Controle de acesso**.
3. Criar cada conta individualmente. O sistema gera senha temporária e obriga sua troca.
4. Conceder centros de custo um a um. Gerentes podem receber múltiplas concessões; o controlador geral tem
   escopo global. Para recuperar um administrador bloqueado, executar no host
   `.\.venv\Scripts\python.exe -m sim.admin_cli redefinir-senha-admin email`.
5. As contas e permissões são dados operacionais; manter backup seguro e trilha de auditoria.

### 9.4 Publicação gratuita (decisão de 2026-10-27)

Hospedagem escolhida pelo responsável: **gratuita**, login atual **sem MFA por ora**, endereço do provedor.

| Peça | Serviço | Observação |
|---|---|---|
| Aplicação | Streamlit Community Cloud (repositório GitHub **privado**) | Hiberna após 12 h sem uso; o primeiro acesso depois disso leva ~1 min. |
| Banco | Neon (PostgreSQL, plano grátis, sem cartão) | 0,5–1 GB; o banco "dorme" após 5 min e acorda em ~1 s. |
| Anexos | Tabela `anexos_conteudo` no mesmo banco (`SIM_ANEXOS_BACKEND=banco`) | O disco da hospedagem é apagado a cada reinício. Limite de 20 MB por arquivo. |

Configuração: copie `.streamlit/secrets.toml.example` para o painel **Secrets** do app (valores reais só lá).
O `app.py` copia essas chaves para variáveis de ambiente. As migrações rodam na primeira abertura
(`SIM_AUTO_MIGRATE` padrão). A tela de configuração inicial exige `SIM_CODIGO_CONFIGURACAO`, para que ninguém
além do responsável crie o primeiro Controle Geral num endereço público.

Limitações aceitas: sem MFA, sem envio de e-mail (redefinição só pelo Controle Geral), espaço pequeno para
anexos (rever quando o histórico do Power Apps for importado), sem SLA. Backup: exportar periodicamente pelo
painel do Neon (o plano grátis guarda histórico curto).

## 9.5 Importação do histórico do SIM antigo (SUPERUS)

As listas do SharePoint exportadas em Excel (`Base <lista> Lists.xlsx`) entram pelo comando:

```
.venv\Scripts\python.exe -m sim.importacao_legado <pasta com as planilhas>            # simula e mostra o relatório
.venv\Scripts\python.exe -m sim.importacao_legado <pasta com as planilhas> --aplicar  # grava no banco do DATABASE_URL
```

- Lista de Apoio → centros de custo; BMs → BM mensal; BM Semanal → BM semanal (com `id_legado` = ID do item).
- Valor Previsto → valor previsto por CC e mês (ano 2026; a lista não tem ano; item repetido: vale o último).
- Cada BM mensal importado recebe o previsto do seu CC no mês (`valor_previsto`), sem justificativa: o SIM antigo
  não pedia. Editar esses BMs sem mudar valor, mês ou ano não exige justificativa.
- Historico BMs só é consultado para recuperar o CC de BMs que perderam o vínculo. Anexos não vêm na exportação:
  BMs importados ficam sem anexo e podem ser editados sem exigir um.
- CC "1 - Cliente X Y Z" (coligada O&S) e seus BMs são de teste e ficam de fora. CC sem coligada recebe a dos
  outros CCs do mesmo cliente, com aviso. CC com Encerramento Manual entra encerrado, com registro em
  `encerramentos_cc`.
- Repetível: CC já existente e BM com o mesmo `id_legado` são mantidos, sem sobrescrever o que mudou no SIM novo.
- Para publicar: rodar o mesmo comando com `DATABASE_URL` apontando para o banco da hospedagem.

## 10. Rastreabilidade com os originais

- O checkout atual não contém os pacotes Power Apps originais nem os arquivos de relatório citados em versões
  anteriores desta documentação; não usar essas referências como se estivessem disponíveis aqui.
- O mapeamento implementado e os limites conhecidos estão descritos neste README e em
  `docs/GUIA_DESENVOLVIMENTO_E_CONTINUIDADE_IA.md`.

## 11. Protótipo HTML anterior

`index.html`, `css/`, `js/` e `tests/unit|e2e` são o protótipo da fase 1, com dados fictícios em memória. Foram
preservados, mas o SIM em Streamlit não os usa. O arquivo `js/data/` necessário para executar esse protótipo
não existe no checkout atual; use o app Streamlit como implementação principal.

## Segurança

- Não há credenciais, tokens, URLs de SharePoint nem dados reais neste projeto.
- `.env`, `data\`, `backups\`, bancos e planilhas estão no `.gitignore`.
- O Streamlit está configurado para não enviar estatísticas de uso (`gatherUsageStats = false`).
