# 🏨 Hostel PMS - Manifesto e Documentação do Sistema

**Data da Documentação:** Novembro de 2026
**Tipo de Aplicação:** Web App / PWA (Progressive Web App)
**Stack Tecnológica:** Python, Streamlit (Frontend/Backend) e Supabase (Banco de Dados PostgreSQL + Autenticação).

## 1. Visão Geral do Sistema

O Hostel PMS é um sistema integrado de gestão hoteleira focado em hostels. Ele abrange desde o controle operacional diário (mapa de ocupação, check-in/out, limpeza e manutenções) até a gestão financeira, vendas de PDV e controle de acesso de equipe. O sistema possui design responsivo, suporta temas Claro/Escuro e opera como um PWA (pode ser instalado como app em dispositivos móveis).

## 2. Estrutura de Arquitetura e Arquivos

O projeto foi desenhado de forma modular para facilitar a manutenção e escalabilidade.

* `app.py`: O coração do sistema. Gerencia o roteamento de páginas (Menu Lateral), injeção de CSS/Tema, PWA, inicializa a sessão persistente com tokens de segurança e exibe a central de alertas operacionais.

* `database.py`: O "cérebro" dos dados. Centraliza 100% das conexões com o Supabase. Contém funções complexas de união de tabelas (JOINs em Python), validação de login, regras de horários de turno e alertas de sistema.

* `modulos/`: Pasta contendo as telas e lógicas de negócios isoladas.

* `utils/`: Pasta de utilitários (Helpers).

  * `formatadores.py`: Validação de CPF/CNPJ, máscaras de data, cálculo de idade, conversão de imagens em Base64.

  * `exportadores.py`: Geração de relatórios em CSV (Pandas) e PDF estruturado.

## 3. Módulos e Funcionalidades (`modulos/`)

### 3.1. Cadastros (`cadastros.py`)

Central de registro de entidades fundamentais:

* **Hóspedes:** Cadastro com foto (upload ou câmera), conformidade LGPD, travamento legal para menores de idade (ECA - Art. 82 exigindo responsável) e distinção entre Nacionalidade (CPF) e Estrangeira (Passaporte).

* **Empresas:** Gestão de parceiros corporativos e faturamento.

* **Quartos e Camas (Leitos):** Estrutura hierárquica. Quartos possuem camas. Cada cama tem seu preço individual e status próprio (Disponível, Ocupado, Limpeza Pendente).

* **Colaboradores:** Registro de equipe. **Crucial:** Define os horários de início e fim de expediente e a flag `restringir_horario`.

* **Prestadores:** Cadastro de técnicos terceirizados para o módulo de manutenção.

### 3.2. Manutenção (`manutencao.py`)

Gestão de Ocorrências (Ordens de Serviço):

* **Corretivas e Preventivas:** Controle de prioridades, status e registro de custos (estimado vs real).

* **Blindagem de Payload:** As chamadas de banco de dados aqui são montadas dinamicamente para evitar envio de nulos (`None`), prevenindo erros na API do PostgREST.

### 3.3. Gestão e Acessos (`gestao.py`)

Módulo exclusivo para Administradores e Gerentes.

* **Autenticação Dupla:** Cria o usuário no `Supabase Auth` e simultaneamente registra as permissões nas tabelas internas.

* **Horários e Suspensões:** Permite editar a janela de expediente de qualquer operador ou revogar (suspender) o acesso imediatamente.

* **Relatórios Financeiros:** Compilação de Receita (Hospedagem + PDV + Eventos), saldo pendente, ADR (Diária Média) e exportações.

* **Seeder & Limpeza:** Ferramentas para popular dados de teste ou resetar o banco de dados operacional.

### 3.4. Outros Módulos Integrados

* `dashboard.py`: Painel geral.

* `hospedagem.py`: Mapa de ocupação, fluxo de reservas e painel de limpeza (visão para governança).

* `operacoes.py`: Loja de conveniência (PDV), gestão de eventos/experiências e central de devedores.

* `configuracoes.py`, `ajuda_lgpd.py` e `fiscal.py`: Regras de negócio auxiliares.

## 4. Segurança e Regras Críticas (Para Futuros Desenvolvedores)

Se um novo desenvolvedor assumir o projeto, ele DEVE estar ciente destas três regras fundamentais que adotamos:

1. **Row-Level Security (RLS) Desativado no Banco:**
   A segurança baseada em RLS do Supabase foi DESATIVADA no SQL (`ALTER TABLE nome_tabela DISABLE ROW LEVEL SECURITY;`). Isso foi feito de forma intencional porque **toda a lógica de bloqueio de acesso, perfil de usuário e verificação de sessões está codificada dentro do Python (`database.py` e `app.py`)**. Reativar o RLS sem escrever as "Policies" no Supabase fará com que o sistema apresente o erro `code 42501` e pare de salvar dados.

2. **Sessão Persistente (Token Auth):**
   Quando um usuário loga marcando "Lembrar de mim", o sistema gera um token local, salva na tabela `colaboradores` (ou `configuracoes` para admins mestres) e injeta na URL. O sistema valida esse token e o horário de expediente antes de desenhar a tela.

3. **Controle de Horário de Expediente:**
   Mesmo com a senha correta, um colaborador (nível Recepção ou Limpeza) não consegue entrar no sistema fora da janela de horário definida (ex: 08:00 às 17:00). Apenas perfis de Administrador ou Gerente ignoram essa trava.

## 5. Estrutura do Banco de Dados (Principais Tabelas no Supabase)

* `hospedes`: (id, nome, documento, contato, foto, lgpd_consentimento).

* `quartos`: (id, nome, ala, perfil, preco_base, ar_condicionado, pcd).

* `camas`: (id, quarto_id, numero, tipo_leito, preco_diaria, status).

* `reservas`: (id, hospede_id, cama_id, status, data_inicio, data_fim, valor_total).

* `vendas`: PDV da loja.

* `eventos` / `eventos_participantes`: Controle de festas e passeios.

* `colaboradores`: Dados da equipe + Controle de Ponto Eletrônico (`horario_inicio`, `horario_fim`, `restringir_horario`).

* `manutencoes`: (id, titulo, status, tipo, prioridade, data_agendada, custos, prestador_id).

* `configuracoes`: Tabela chave-valor para guardar logo da empresa, tokens mestres e preferências de tema.

## 6. Como Fazer o Deploy / Instalação Local

1. Instalar dependências: `pip install -r requirements.txt` (Bibliotecas principais: `streamlit`, `supabase`, `pandas`, `pytz`, `python-dotenv`).

2. Arquivo de Segredos: Criar um `.env` local ou preencher os Secrets do Streamlit Cloud com:
   `SUPABASE_URL="sua_url_aqui"`
   `SUPABASE_KEY="sua_chave_anon_aqui"`

3. Rodar a aplicação localmente: `streamlit run app.py`