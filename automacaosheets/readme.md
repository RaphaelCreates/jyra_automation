# 🤖 Automação de Status do Jira para Google Sheets

## Visão Geral do Projeto

Este projeto implementa uma solução de automação robusta em Python para sincronizar o status de tarefas do Jira com uma Planilha Google. Ele resolve o desafio da atualização manual de relatórios de projetos, fornecendo visibilidade em tempo real sobre o andamento das tarefas, reduzindo erros e aumentando a eficiência operacional.

### Valor e Benefícios

* **Eficiência Operacional:** Elimina a necessidade de extração e atualização manual de dados do Jira em planilhas.
* **Visibilidade em Tempo Real:** Relatórios de status sempre atualizados na Planilha Google, acessíveis a todos.
* **Tomada de Decisão Acelerada:** Informações precisas e atuais para decisões mais ágeis e assertivas.
* **Redução de Erros:** Minimiza imprecisões causadas pela intervenção humana.
* **Padronização:** Garante a consistência na forma como o status das tarefas é reportado.

### Como Funciona (Arquitetura)

A automação opera em um ciclo contínuo, orquestrado por um script Python:

1.  **Agendador:** Dispara o script Python em intervalos definidos (ex: diariamente, a cada hora).
2.  **Script Python:**
    * Autentica-se com o **Jira** (usando Token de API).
    * Executa uma consulta **JQL** para buscar tarefas específicas (filtradas por projeto, label e status).
    * Autentica-se com o **Google Sheets** (usando Conta de Serviço e Chave JSON).
    * Lê o estado atual da Planilha Google de destino.
    * Compara os dados do Jira com os da Planilha.
    * **Atualiza** o status (`status` e `outros` para data de conclusão) de tarefas existentes na Planilha Google se houver mudanças.
    * **Adiciona** novas tarefas na Planilha Google que foram encontradas no Jira e ainda não estavam lá.
3.  **Planilha Google:** Recebe e exibe as atualizações.

## Tecnologias Utilizadas

* **Python 3.x:** Linguagem de programação principal.
* **Jira Cloud/Server:** Sistema de gestão de projetos.
* **Google Sheets:** Serviço de planilha online.
* **Bibliotecas Python:**
    * `requests`: Para requisições HTTP à API do Jira.
    * `pandas`: Para manipulação e comparação eficiente de dados.
    * `google-api-python-client`: Para interagir com a API do Google Sheets.
    * `google-auth-oauthlib`, `google-auth-httplib2`, `google.oauth2.service_account`: Para autenticação com o Google APIs.
    * `python-dotenv`: Para carregar variáveis de ambiente de forma segura.

## Configuração do Ambiente de Desenvolvimento

Siga estes passos para configurar e testar o projeto em sua máquina local.

### 1. Pré-requisitos

* Python 3.8+ instalado.
* Acesso a uma conta Jira.
* Acesso a uma conta Google com permissões para Google Cloud Platform e Google Sheets.
* Conexão à internet.

### 2. Clonar o Repositório

```bash
git clone [https://github.com/RaphaelCreates/jyra_automation]
cd  automacaosheets
```

### 3. Configuração de Credenciais e Serviços

#### 3.1. No Jira: Obter Token de API

1.  Acesse seu perfil Jira > **Segurança** > **Tokens de API**.
2.  Gere um novo token, nomeie-o (ex: `automacao-sheets`), e **COPIE-O IMEDIATAMENTE**.
3.  Guarde este token para o passo de configuração do `.env`.

#### 3.2. No Google Cloud Platform (GCP): Credenciais da API do Google Sheets

1.  Acesse o [Google Cloud Console](https://console.cloud.google.com/) e selecione (ou crie) seu projeto.
2.  Em **"APIs e Serviços" > "Biblioteca"**, ative a **"Google Sheets API"**.
3.  Em **"APIs e Serviços" > "Credenciais"**:
    * Clique em **"Criar Credenciais" > "Conta de Serviço"**.
    * Dê um nome (ex: `automacao-sheets-jira`) e atribua a função de **"Editor de Planilhas"**.
    * **Gere uma nova chave JSON** para esta Conta de Serviço. Um arquivo (ex: `seu-projeto-id.json`) será baixado.
4.  **Renomeie este arquivo baixado para `credentials.json`** e coloque-o na **pasta raiz do seu projeto** (ao lado de `main.py`).

#### 3.3. Na Planilha Google: Estrutura e Compartilhamento

1.  Crie ou use uma Planilha Google existente.
2.  **Nome da Aba:** Anote o nome exato da aba que o script usará (ex: `Folha1`).
3.  **Cabeçalhos:** Na primeira linha da aba, defina as colunas com os nomes **EXATOS**: `id key`, `status`, `outros`.
4.  **Compartilhamento:** Clique em **"Compartilhar"** na planilha e cole o **endereço de e-mail da sua Conta de Serviço** (ex: `automacao-sheets-jira@seu-projeto.iam.gserviceaccount.com`). Dê permissão de **"Editor"**.

#### 3.4. No Jira: Definir e Aplicar Labels (Tags)

1.  **Escolha uma Label:** Defina uma label que o script usará para filtrar tarefas (ex: `monitorar-sheets`).
2.  **Aplique nas Tarefas:** No Jira, adicione esta label às tarefas específicas que a automação deve monitorar.

### 4. Configuração do Ambiente Python Local

1.  **Crie e Ative o Ambiente Virtual:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate   # Para Windows PowerShell
    # source venv/bin/activate # Para macOS/Linux
    ```
2.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    * Se você ainda não criou `requirements.txt` na sua máquina de desenvolvimento principal, use: `pip freeze > requirements.txt` e adicione este arquivo ao Git.

### 5. Crie o Arquivo `.env`

Na pasta raiz do seu projeto, crie um arquivo chamado **`.env`** (com o ponto na frente) e preencha com suas credenciais e configurações.

```dotenv
JIRA_URL=[https://sua-instancia.atlassian.net](https://sua-instancia.atlassian.net)
JIRA_EMAIL=seu.email@dominio.com
JIRA_API_TOKEN=SEU_TOKEN_DE_API_DO_JIRA_AQUI

GOOGLE_SHEETS_ID=ID_DA_SUA_PLANILHA_GOOGLE_AQUI
GOOGLE_SHEETS_ABA_NOME=Folha1
GOOGLE_SHEETS_COLUNA_JIRA_KEY=id key
GOOGLE_SHEETS_COLUNA_STATUS=status

JIRA_STATUS_CONCLUIDO_LIST=CONCLUÍDO,RESOLVIDO,FECHADO # Nomes exatos do Jira, separados por vírgula
```

### 6. Estrutura do Projeto

```
.
├── .env
├── .gitignore
├── credentials.json
├── main.py
└── venv/
└── requirements.txt
```

## Como Executar o Script

Com o ambiente configurado, você pode executar e testar a automação.

1.  **Prepare Tarefas de Teste no Jira:**
    * No projeto `KAN`, edite `KAN-1` e `KAN-2`.
    * Adicione a label `monitorar-sheets` a ambas.
    * Mude o status de `KAN-1` para `CONCLUÍDO`.
    * Mude o status de `KAN-2` para `EM ANDAMENTO`.
    * Crie uma nova tarefa (ex: `KAN-3`) e adicione a label `monitorar-sheets`. Deixe-a como `A FAZER`.

2.  **Abra sua Planilha Google:** Deixe-a aberta para ver as atualizações em tempo real.

3.  **Execute o Script:**
    * No terminal (com `venv` ativado) na pasta raiz do projeto:
        ```bash
        python main.py
        ```
    * Observe as mensagens no terminal (sucesso ou erros).

4.  **Verifique a Planilha Google:**
    * O status de `KAN-1` deve mudar para "Concluído" e a coluna `outros` deve ser preenchida com a data.
    * O status de `KAN-2` deve mudar para "Não Concluído".
    * Uma nova linha para `KAN-3` deve ser adicionada com o status "Não Concluído".

## Resolução de Problemas Comuns

* **`ModuleNotFoundError`:** Biblioteca não instalada no `venv`.
    * **Solução:** Ative o `venv` e `pip install -r requirements.txt`.
* **`Fatal error in launcher`:** Problema com o PATH do Python no `venv`.
    * **Solução:** Desative `venv`, exclua `venv/` e cache do pip, recrie `venv` e reinstale as libs.
* **`NameError: 'GOOGLE_CREDENTIALS_FILE' is not defined`:** Variável de configuração ausente.
    * **Solução:** Verifique `GOOGLE_CREDENTIALS_FILE = 'credentials.json'` no topo do `main.py`.
* **`[Errno 2] No such file or directory: 'credentials.json'`:** Arquivo JSON não encontrado.
    * **Solução:** Confirme que `credentials.json` está na mesma pasta do `main.py` e com o nome exato.
* **`HttpError 400: Unable to parse range`:** Nome da aba ou ID da planilha incorretos.
    * **Solução:** Verifique `GOOGLE_SHEETS_ABA_NOME` e `GOOGLE_SHEETS_ID` no `.env`.
* **`ValueError: X columns passed, passed data had Y columns`:** Planilha com inconsistência de colunas.
    * **Solução:** Lógica no script ajustada para pré-processar linhas vazias.
* **`KeyError: 'key_jira'`:** Problema ao acessar coluna no DataFrame mergeado.
    * **Solução:** Lógica de acesso a `jira_key` no script ajustada.
* **JQL retorna 0 tarefas:** Consulta JQL não encontra tarefas no Jira.
    * **Solução:** Teste a JQL diretamente no Jira, verifique labels, status e filtros de data.

## Deployment (Implantação)


* **Ambiente:** Máquina Virtual (VM) na nuvem (Google Cloud Compute Engine, AWS EC2) ou ambiente Serverless (Google Cloud Functions, AWS Lambda).
* **Credenciais em Produção:** O `.env` e o `credentials.json` não são copiados. As credenciais são configuradas de forma segura como **variáveis de ambiente** na plataforma de nuvem ou em um serviço de gerenciamento de segredos (ex: Google Cloud Secret Manager).
* **Agendamento:** O script é agendado para rodar automaticamente (ex: Cron no Linux, Cloud Scheduler no GCP).
* **Monitoramento:** Configuração de logs e alertas para notificar sobre falhas.

## Roadmap Futuro

* **Enriquecimento de Dados:** Adicionar mais campos do Jira (Resumo, Responsável, Tipo de Tarefa) na Planilha Google.
* **Interface Simplificada:** Desenvolver uma interface web básica para que usuários não-técnicos possam gerenciar parâmetros.
* **Escalabilidade:** Suporte a múltiplos relatórios ou a um volume maior de dados/projetos.

---
