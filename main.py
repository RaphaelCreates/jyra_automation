import os
import requests
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# --- 1. Carregar Configurações e Credenciais ---
load_dotenv() # Carrega as variáveis do arquivo .env

# Configurações do Jira (do arquivo .env)
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

# Configurações do Google Sheets (do arquivo .env)
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
GOOGLE_SHEETS_ABA_NOME = os.getenv('GOOGLE_SHEETS_ABA_NOME')
GOOGLE_SHEETS_COLUNA_JIRA_KEY = os.getenv('GOOGLE_SHEETS_COLUNA_JIRA_KEY')
GOOGLE_SHEETS_COLUNA_STATUS = os.getenv('GOOGLE_SHEETS_COLUNA_STATUS')

# Nome do arquivo JSON da conta de serviço Google
GOOGLE_CREDENTIALS_FILE = 'credentials.json'

# Status do Jira que significam "Concluído" (do arquivo .env, dividido por vírgula)
JIRA_STATUS_CONCLUIDO = [s.strip() for s in os.getenv('JIRA_STATUS_CONCLUIDO_LIST', 'Done').split(',')]

# --- 2. Funções de Conexão e API ---

def get_jira_issues(jql_query):
    """
    Busca tarefas no Jira usando JQL. Implementa paginação básica.
    Retorna uma lista de dicionários com os dados das issues.
    """
    all_issues = []
    start_at = 0
    max_results = 100 # Máximo de resultados por requisição à API do Jira

    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/search"

    print(f"Buscando tarefas no Jira com JQL: {jql_query}")

    while True:
        params = {
            "jql": jql_query,
            # Campos que você quer puxar. Adicione/remova conforme sua necessidade.
            "fields": "key,summary,status,assignee,project,labels,resolutiondate",
            "startAt": start_at,
            "maxResults": max_results
        }
        try:
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status() # Levanta um erro para status HTTP 4xx/5xx
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao conectar ou puxar dados do Jira: {e}")
            break # Sai do loop em caso de erro

        issues = data.get('issues', [])
        if not issues:
            break # Não há mais issues para buscar

        all_issues.extend(issues)
        
        # Verifica se há mais resultados (total > startAt + maxResults)
        total_issues = data.get('total', 0)
        if start_at + max_results >= total_issues:
            break # Buscou todas as issues

        start_at += len(issues)
        print(f"Puxados {len(all_issues)} de {total_issues} issues do Jira...")
    
    print(f"Total de {len(all_issues)} tarefas puxadas do Jira.")
    return all_issues

def get_google_sheets_service():
    """Autentica e retorna o serviço da API do Google Sheets."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        print(f"Erro na autenticação do Google Sheets: {e}")
        print("Verifique se 'credentials.json' está na pasta correta e se a Conta de Serviço tem permissão.")
        return None

def read_google_sheet(service, spreadsheet_id, range_name):
    """Lê dados de uma Planilha Google."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name
        ).execute()
        values = result.get('values', [])
        return values
    except HttpError as e:
        print(f"Erro ao ler Planilha Google: {e}")
        print("Verifique se o ID da planilha e o nome da aba estão corretos e se a Conta de Serviço tem permissão de leitura.")
        return None

def update_google_sheet_batch(service, spreadsheet_id, updates_data):
    """Atualiza múltiplas células na Planilha Google em lote."""
    if not updates_data:
        return
    body = {
        'valueInputOption': 'RAW',
        'data': updates_data
    }
    try:
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()
        return result
    except HttpError as e:
        print(f"Erro ao atualizar Planilha Google: {e}")
        print("Verifique se o ID da planilha e os ranges de atualização estão corretos.")
        return None

def append_google_sheet_rows(service, spreadsheet_id, sheet_name, values_to_append):
    """Adiciona novas linhas no final de uma aba da Planilha Google."""
    if not values_to_append:
        return
    body = {
        'values': values_to_append
    }
    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A1', # Adiciona a partir da primeira célula da aba
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        return result
    except HttpError as e:
        print(f"Erro ao adicionar novas linhas à Planilha Google: {e}")
        print("Verifique se o ID da planilha e o nome da aba estão corretos e se a Conta de Serviço tem permissão de escrita.")
        return None

# --- 3. Lógica Principal da Automação ---
def run_automation():
    print("--- Iniciando automação Jira para Google Sheets ---")

    # --- A. Puxar Dados do Jira ---
    # AJUSTE ESTA JQL! Mude os códigos dos projetos e a label conforme sua configuração.
    # Esta JQL busca tarefas dos projetos X e Y que tenham a label 'automacao-status-sheets'
    # e que estejam em qualquer um dos status de interesse (para poder verificar o status atual).
    jql_query_jira = f'project in ("PROJETO_A", "PROJETO_B") AND labels = "automacao-status-sheets" AND status in ("To Do", "In Progress", "Done", "Resolved", "Closed", "Backlog", "Blocked") ORDER BY updated DESC'
    
    jira_issues_raw = get_jira_issues(jql_query_jira)

    if not jira_issues_raw:
        print("Nenhuma tarefa relevante encontrada no Jira com a JQL especificada. Encerrando.")
        return

    # Processar dados do Jira em um DataFrame
    jira_data_for_df = []
    for issue in jira_issues_raw:
        jira_data_for_df.append({
            'key': issue.get('key'),
            'summary': issue['fields'].get('summary', ''),
            'status_jira': issue['fields'].get('status', {}).get('name', ''),
            'assignee': issue['fields'].get('assignee', {}).get('displayName', 'Não Atribuído'),
            'project': issue['fields'].get('project', {}).get('name', ''),
            'resolutionDate': issue['fields'].get('resolutiondate', '') # Pode ser None
        })
    df_jira = pd.DataFrame(jira_data_for_df)
    
    # Mapear status do Jira para "Concluído"/"Não Concluído"
    df_jira['Status_Formatado_Conclusao'] = df_jira['status_jira'].apply(
        lambda s: "Concluído" if s in JIRA_STATUS_CONCLUIDO else "Não Concluído"
    )
    print(f"Total de {len(df_jira)} tarefas processadas do Jira para a comparação.")

    # --- B. Puxar Dados da Planilha Google Existente ---
    sheets_service = get_google_sheets_service()
    if not sheets_service:
        print("Não foi possível conectar ao serviço do Google Sheets. Encerrando.")
        return

    # O range para leitura precisa cobrir todas as colunas possíveis da sua planilha.
    # Ajuste 'A:Z' para o range real de colunas que você usa (ex: 'A:G').
    range_to_read = f'{GOOGLE_SHEETS_ABA_NOME}!A:Z'
    sheet_values = read_google_sheet(sheets_service, GOOGLE_SHEETS_ID, range_to_read)

    if not sheet_values:
        print("Planilha Google vazia ou sem dados iniciais. Adicionando todas as tarefas do Jira como novas.")
        # Se a planilha está vazia, precisamos adicionar o cabeçalho e todos os dados
        # AJUSTE A ORDEM DAS COLUNAS AQUI para o cabeçalho inicial da sua planilha!
        header_for_new_sheet = [GOOGLE_SHEETS_COLUNA_JIRA_KEY, 'Resumo da Tarefa', GOOGLE_SHEETS_COLUNA_STATUS, 'Responsável', 'Projeto']

        # Prepara todos os dados do Jira para serem adicionados como novas linhas
        initial_data_to_add = []
        for _, row in df_jira.iterrows():
            initial_data_to_add.append([
                row['key'],
                row['summary'],
                row['Status_Formatado_Conclusao'],
                row['assignee'],
                row['project']
            ])
        
        # Adiciona o cabeçalho + os dados iniciais
        append_google_sheet_rows(sheets_service, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_ABA_NOME, [header_for_new_sheet] + initial_data_to_add)
        print("Planilha Google preenchida com as tarefas iniciais do Jira. Encerrando por esta execução.")
        return # Encerrar pois o objetivo inicial de preenchimento foi alcançado

    # O cabeçalho é a primeira linha da planilha
    sheet_header = sheet_values[0]
    # Os dados começam da segunda linha (índice 1)
    df_google_sheet = pd.DataFrame(sheet_values[1:], columns=sheet_header)
    print(f"Puxadas {len(df_google_sheet)} linhas da Planilha Google.")

    # --- C. Comparar e Preparar Atualizações/Novas Inserções ---
    updates_for_sheets_api = []
    new_rows_for_sheets_api = []

    # Localizar o índice da coluna de Status e Jira Key na planilha (baseado no cabeçalho)
    try:
        col_index_jira_key = sheet_header.index(GOOGLE_SHEETS_COLUNA_JIRA_KEY)
        col_index_status = sheet_header.index(GOOGLE_SHEETS_COLUNA_STATUS)
        col_letter_status = chr(ord('A') + col_index_status) # Converte índice para letra da coluna (ex: 0->A, 1->B)
    except ValueError as e:
        print(f"ERRO: Coluna '{e}' não encontrada no cabeçalho da Planilha Google. Verifique os nomes no .env!")
        return

    # Usar merge para comparar os DataFrames (Google Sheet vs. Jira)
    df_merged = pd.merge(
        df_google_sheet,
        df_jira,
        left_on=GOOGLE_SHEETS_COLUNA_JIRA_KEY, # Coluna da Jira Key na planilha
        right_on='key', # Coluna da Jira Key no DataFrame do Jira
        how='outer', # Outer join para pegar tudo de ambos os lados
        suffixes=('_sheet', '_jira'),
        indicator=True # Adiciona coluna para indicar a origem da linha (both, left_only, right_only)
    )

    print("Iniciando comparação de dados...")
    # Iterar sobre o DataFrame mergeado para determinar o que fazer
    for index_merged, row in df_merged.iterrows():
        jira_key = row['key_jira'] if pd.notna(row['key_jira']) else row[GOOGLE_SHEETS_COLUNA_JIRA_KEY]
        
        if row['_merge'] == 'both': # Tarefa existe no Jira e na Planilha
            status_atual_jira = row['Status_Formatado_Conclusao']
            status_na_planilha = row[GOOGLE_SHEETS_COLUNA_STATUS]

            if status_atual_jira != status_na_planilha:
                # O status mudou, preparar atualização
                # A API do Sheets usa índices baseados em 1 e a linha do cabeçalho conta
                # original_sheet_row_index é o índice do Pandas no df_google_sheet (0-based, sem cabeçalho)
                # row_number_in_sheet é o número real da linha na Planilha Google (1-based, com cabeçalho)
                original_sheet_row_index = df_google_sheet[df_google_sheet[GOOGLE_SHEETS_COLUNA_JIRA_KEY] == jira_key].index[0]
                row_number_in_sheet = original_sheet_row_index + 2 # +1 para 1-based, +1 para o cabeçalho

                range_to_update = f"{GOOGLE_SHEETS_ABA_NOME}!{col_letter_status}{row_number_in_sheet}"
                updates_for_sheets_api.append({
                    'range': range_to_update,
                    'values': [[status_atual_jira]]
                })
                print(f"   -> UPDATE: {jira_key} de '{status_na_planilha}' para '{status_atual_jira}'")

        elif row['_merge'] == 'right_only': # Tarefa é nova, existe no Jira mas não na Planilha
            # Preparar nova linha para ser adicionada
            # AJUSTE A ORDEM DAS COLUNAS AQUI para corresponder à sua planilha!
            new_rows_for_sheets_api.append([
                row['key_jira'],
                row['summary_jira'],
                row['Status_Formatado_Conclusao'],
                row['assignee_jira'],
                row['project_jira']
                # ... adicione aqui outros campos do Jira que você queira na nova linha
            ])
            print(f"   -> NOVO: {row['key_jira']} será adicionado com status '{row['Status_Formatado_Conclusao']}'")

        # Se for 'left_only', significa que a tarefa está na planilha mas não foi encontrada no Jira.
        # Por padrão, este script ignora, mas você pode adicionar lógica para, por exemplo, marcar como 'Removida'.
        # elif row['_merge'] == 'left_only':
        #     print(f"   -> REMOVIDO?: {row[GOOGLE_SHEETS_COLUNA_JIRA_KEY]} está na planilha mas não no Jira.")

    # --- D. Executar Atualizações e Inserções na Planilha Google ---
    print("\nExecutando ações na Planilha Google...")
    if updates_for_sheets_api:
        print(f"Enviando {len(updates_for_sheets_api)} atualizações de status...")
        update_google_sheet_batch(sheets_service, GOOGLE_SHEETS_ID, updates_for_sheets_api)
        print("Atualizações de status concluídas.")
    else:
        print("Nenhuma atualização de status necessária.")

    if new_rows_for_sheets_api:
        print(f"Adicionando {len(new_rows_for_sheets_api)} novas tarefas...")
        append_google_sheet_rows(sheets_service, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_ABA_NOME, new_rows_for_sheets_api)
        print("Novas tarefas adicionadas.")
    else:
        print("Nenhuma nova tarefa para adicionar.")

    print("--- Automação concluída com sucesso! ---")

# Garante que a função 'run_automation' seja chamada quando o script for executado
if __name__ == "__main__":
    run_automation()