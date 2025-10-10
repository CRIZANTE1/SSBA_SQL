# ⚠️ Sistema de Abrangência de Incidentes

Este é um aplicativo web construído com Streamlit e Python, projetado para gerenciar o registro, a análise e a disseminação de alertas de incidentes em múltiplas unidades operacionais. O sistema utiliza a IA do Google (Gemini) para automatizar a extração de informações de documentos e um fluxo de trabalho claro para garantir que as ações de bloqueio sejam avaliadas e implementadas.

---

## ✨ Funcionalidades Principais

- **Cadastro Inteligente de Alertas:** Administradores podem registrar novos incidentes fazendo o upload de documentos (PDF/DOCX) e fotos. A IA Gemini analisa o documento para extrair automaticamente um resumo, data, causas e recomendações.
- **Centralização no Google Drive:** Todas as evidências (fotos, anexos) são salvas de forma organizada em uma pasta central no Google Drive.
- **Dashboard Global de Incidentes:** Todas as unidades podem visualizar os incidentes registrados em um dashboard central com cards informativos.
- **Fluxo de Abrangência:** Cada unidade pode analisar um incidente global e registrar quais ações de bloqueio são pertinentes à sua realidade local.
- **Plano de Ação por Unidade:** Uma página dedicada para cada unidade acompanhar o status de implementação das ações de abrangência que se comprometeu a fazer.
- **Notificações Automáticas:** Um workflow do GitHub Actions executa um script diariamente para enviar um e-mail de alerta sobre ações de abrangência que estão com o prazo vencido.
- **Autenticação e Permissões:** Sistema de login que diferencia usuários de unidades e um Administrador Global com acesso a funcionalidades exclusivas.

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python
- **Frontend:** Streamlit
- **Análise de IA:** Google Gemini
- **Base de Dados:** Google Sheets
- **Armazenamento de Arquivos:** Google Drive
- **Manipulação de Dados:** Pandas
 - **Análise de IA:** Google Gemini (pode ser substituído por outro provedor)
 - **Base de Dados:** Supabase (Postgres) — substituiu Google Sheets
 - **Armazenamento de Arquivos:** Supabase Storage — substituiu Google Drive
 - **Manipulação de Dados:** Pandas

## 🚀 Guia de Instalação e Configuração

Siga os passos abaixo para configurar e executar o projeto em seu ambiente local.

### 1. Pré-requisitos

- Python 3.9 ou superior
- Git

### 2. Clone o Repositório

```bash
git clone https://github.com/CRIZANTE1/SSBA_VIBRA.git
cd SSBA_VIBRA
```

### 3. Crie e Ative um Ambiente Virtual

- **Windows:**
  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  ```
- **macOS/Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 4. Instale as Dependências

```bash
pip install -r requirements.txt
```

### 5. Credenciais — Supabase

Este projeto foi migrado para usar Supabase (Postgres + Storage). Para executar a versão atual você deve fornecer credenciais do Supabase via:

- Streamlit Secrets: `st.secrets['database']['connection_string']`, `st.secrets['supabase']['url']`, `st.secrets['supabase']['key']`
- Ou variáveis de ambiente: `DATABASE_CONNECTION_STRING`, `SUPABASE_URL`, `SUPABASE_KEY`

Antes de rodar a aplicação, crie no Supabase as tabelas e buckets necessários (veja o diretório `database/` para exemplos e scripts SQL). Ajuste as políticas de acesso dos buckets conforme sua necessidade (público vs privado).

### 6. Configure os IDs no Projeto

Abra o arquivo `gdrive/config.py` e preencha as seguintes variáveis com os IDs corretos:

- `MATRIX_SPREADSHEET_ID`: O ID da sua planilha Google principal (a Matriz).
- `CENTRAL_ALERTS_FOLDER_ID`: O ID da pasta no Google Drive onde os anexos dos incidentes serão salvos.

### 7. Configure as Variáveis de Ambiente (para Notificações)

Para que o envio de e-mails funcione (especialmente no GitHub Actions), você precisa configurar os "Secrets" no seu repositório do GitHub (`Configurações > Secrets e variáveis > Actions`):

- `GCP_SERVICE_ACCOUNT_CREDENTIALS`: Conteúdo completo do seu arquivo `credentials.json`.
- `SENDER_EMAIL`: O e-mail que enviará as notificações (ex: um Gmail).
- `SENDER_PASSWORD`: A senha de aplicativo do e-mail acima. ([Como gerar uma senha de aplicativo no Google](https://support.google.com/accounts/answer/185833)).
- `RECEIVER_EMAIL`: O e-mail (ou lista de e-mails, separados por vírgula) que receberá os relatórios.

## ▶️ Como Executar a Aplicação

Após concluir toda a configuração, execute o seguinte comando no seu terminal (com o ambiente virtual ativado):

```bash
streamlit run SSAB.py
```

A aplicação será aberta no seu navegador.

## 📄 Estrutura de Dados (Planilhas)

A estrutura das abas necessárias nas planilhas (tanto na Matriz quanto nas de cada unidade) é definida no arquivo `sheets_config.yaml`. Ao provisionar uma nova unidade através do painel de administração, o sistema cria uma nova planilha com estas abas automaticamente.

## 📜 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE.txt` para mais detalhes.
