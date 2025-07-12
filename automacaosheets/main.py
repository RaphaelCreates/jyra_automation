import os
import requests 
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# --- 1. Carregar Configurações e Credenciais ---
load_dotenv() # Carrega as variáveis do arquivo .env

# Configurações do Jira (serão usadas DEPOIS, quando você integrar o Jira real)
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

# Configurações do Google Sheets (puxadas do arquivo .env)
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
GOOGLE_SHEETS_ABA_NOME = os.getenv('GOOGLE_SHEETS_ABA_NOME')

# AJUSTADO: Nomes das colunas da sua planilha
GOOGLE_SHEETS_COLUNA_JIRA_KEY = "id key"     
GOOGLE_SHEETS_COLUNA_STATUS = "status" 

# Status do Jira que significam "Concluído" (puxados do arquivo .env, divididos por vírgula)
# Converte para maiúsculas para comparação case-insensitive
JIRA_STATUS_CONCLUIDO = [s.strip().upper() for s in os.getenv('JIRA_STATUS_CONCLUIDO_LIST', 'Done').split(',')]


# Parâmetros para a JQL (mantidos para referência, mas não usados na função simulada)
JIRA_PROJETOS_PARA_MONITORAR = ["KAN"] 
JIRA_LABEL_PARA_MONITORAR = "automacao-status-sheets" 


#Funções de Conexão e API ---


# A versão de simulação (com simulated_issues) deve estar comentada ou removida.
def get_jira_issues(jql_query):
    """
    Busca tarefas no Jira usando JQL. Implementa paginação básica.
    Retorna uma lista de dicionários com os dados das issues.
    """
    all_issues = []
    start_at = 0
    max_results = 100 

    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/search"

    print(f"Buscando tarefas no Jira com JQL: {jql_query}")

    while True:
        params = {
            "jql": jql_query,
            "fields": "key,summary,status,assignee,project,labels,resolutiondate",
            "startAt": start_at,
            "maxResults": max_results
        }
        try:
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status() 
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro ao conectar ou puxar dados do Jira: {e}")
            break 
        issues = data.get('issues', [])
        if not issues:
            break 
        all_issues.extend(issues)
        total_issues = data.get('total', 0)
        if start_at + max_results >= total_issues:
            break 
        start_at += len(issues)
        if total_issues > 0:
            print(f"Puxados {len(all_issues)} de {total_issues} issues do Jira...")
    print(f"Total de {len(all_issues)} tarefas puxadas do Jira.")
    return all_issues


def get_google_sheets_service():
    """Autentica e retorna o serviço da API do Google Sheets usando o arquivo credentials.json."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    try:
        # Usa o arquivo credentials.json para autenticação
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        print(f"Erro na autenticação do Google Sheets: {e}")
        print(f"Verifique se '{GOOGLE_CREDENTIALS_FILE}' está na pasta correta e se a Conta de Serviço tem permissão.")
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

# --- Lógica Principal da Automação ---
def run_automation():
    print("--- Iniciando automação Jira para Google Sheets ---")

    #Puxar Dados do Jira 
    
    # updated >= "-1d" -> Ajuste o período de atualização conforme sua necessidade (ex: "-1w", "startOfMonth()").
    jql_query_jira = 'project = "KAN" AND labels = "monitorar-sheets" AND status IN ("Em andamento", "IDEIA", "A FAZER", "TESTES", "CONCLUÍDO") AND updated >= "-1d" ORDER BY updated DESC'
    
    jira_issues_raw = get_jira_issues(jql_query_jira) # Esta função agora faz requisições reais ao Jira

    if not jira_issues_raw:
        print("Nenhuma tarefa relevante encontrada no Jira com a JQL especificada. Encerrando.")
        return

    # Processar dados do Jira em um DataFrame
    jira_data_for_df = []
    for issue in jira_issues_raw:
        status_name = issue['fields'].get('status', {}).get('name', '')
        
        # --- VERIFICAÇÃO E ATRIBUIÇÃO SEGURA PARA ASSIGNEE ---
        assignee_display_name = 'Não Atribuído'
        if issue['fields'].get('assignee'): 
            assignee_display_name = issue['fields']['assignee'].get('displayName', 'Não Atribuído')

        # --- VERIFICAÇÃO E ATRIBUIÇÃO SEGURA PARA PROJECT NAME ---
        project_name_value = '' 
        if issue['fields'].get('project'):
            project_name_value = issue['fields']['project'].get('name', '')

        jira_data_for_df.append({
            'key': issue.get('key'),
            'summary': issue['fields'].get('summary', ''), 
            'status_jira': status_name,
            'assignee': assignee_display_name, # USA A VARIÁVEL VERIFICADA
            'project_name': project_name_value, # USA A VARIÁVEL VERIFICADA
            'resolutionDate': issue['fields'].get('resolutiondate', '') # Pega a data de conclusão
        })
    df_jira = pd.DataFrame(jira_data_for_df)
    
    # Mapear status do Jira para "Concluído"/"Não Concluído"
    df_jira['Status_Formatado_Conclusao'] = df_jira['status_jira'].apply(
        lambda s: "Concluído" if s.upper() in JIRA_STATUS_CONCLUIDO else "Não Concluído"
    )
    print(f"Total de {len(df_jira)} tarefas processadas do Jira para a comparação.")

    #Puxar Dados da Planilha Google Existente ---
    sheets_service = get_google_sheets_service()
    if not sheets_service:
        print("Não foi possível conectar ao serviço do Google Sheets. Encerrando.")
        return

    range_to_read = f'{GOOGLE_SHEETS_ABA_NOME}!A:C' 
    sheet_values = read_google_sheet(sheets_service, GOOGLE_SHEETS_ID, range_to_read)

    if not sheet_values:
        print("Planilha Google vazia ou sem dados iniciais. Adicionando todas as tarefas como novas.")
        #Cabeçalho inicial da planilha Google
        header_for_new_sheet = [GOOGLE_SHEETS_COLUNA_JIRA_KEY, GOOGLE_SHEETS_COLUNA_STATUS, 'outros'] 

        initial_data_to_add = []
        for _, row in df_jira.iterrows():
            initial_data_to_add.append([
                row['key'],                      # Coluna 1: id key
                row['Status_Formatado_Conclusao'], # Coluna 2: status
                row['resolutionDate'] if row['resolutionDate'] else '' # Coluna 3: outros 
            ])
        
        append_google_sheet_rows(sheets_service, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_ABA_NOME, [header_for_new_sheet] + initial_data_to_add)
        print("Planilha Google preenchida com as tarefas iniciais. Encerrando por esta execução.")
        return

    sheet_header = sheet_values[0]
    #Pré-processa as linhas de dados para garantir que todas tenham o mesmo número de colunas que o cabeçalho.
    data_rows = []
    if len(sheet_values) > 1: # Verifica se há linhas de dados além do cabeçalho
        for row_data in sheet_values[1:]: # Itera sobre as linhas de dados
            # Garante que cada linha de dados tenha o mesmo número de elementos que o cabeçalho
            
            processed_row = [row_data[i] if i < len(row_data) else '' for i in range(len(sheet_header))]
            data_rows.append(processed_row)
    
    df_google_sheet = pd.DataFrame(data_rows, columns=sheet_header)
    print(f"Puxadas {len(df_google_sheet)} linhas da Planilha Google.")

    #Comparar e Preparar Atualizações/Novas Inserções ---
    updates_for_sheets_api = []
    new_rows_for_sheets_api = []

    try:
        col_index_jira_key = sheet_header.index(GOOGLE_SHEETS_COLUNA_JIRA_KEY)
        col_index_status = sheet_header.index(GOOGLE_SHEETS_COLUNA_STATUS)
        col_index_outros = sheet_header.index('outros') # Índice para a coluna 'outros'
        
        col_letter_status = chr(ord('A') + col_index_status)
        col_letter_outros = chr(ord('A') + col_index_outros)
    except ValueError as e:
        print(f"ERRO: Coluna '{e}' não encontrada no cabeçalho da Planilha Google. Verifique se os nomes (id key, status, outros) estão EXATOS!")
        return

    df_merged = pd.merge(
        df_google_sheet,
        df_jira,
        left_on=GOOGLE_SHEETS_COLUNA_JIRA_KEY,
        right_on='key',
        how='outer',
        suffixes=('_sheet', '_jira'),
        indicator=True
    )

    print("Iniciando comparação de dados...")
    for index_merged, row in df_merged.iterrows():
        # Tenta pegar a key da parte do Jira (com sufixo _jira)
        # Garante que o valor final seja uma string
        if pd.notna(row.get('key_jira')): # Verifica se 'key_jira' existe e não é NaN
            jira_key = str(row['key_jira'])
        elif pd.notna(row.get(GOOGLE_SHEETS_COLUNA_JIRA_KEY + '_sheet')): # Se não, verifica se a key da planilha existe
            jira_key = str(row[GOOGLE_SHEETS_COLUNA_JIRA_KEY + '_sheet'])
        else:
            
            print(f"Aviso: Não foi possível determinar a Jira Key para a linha {index_merged}. Pulando.")
            continue 

        if row['_merge'] == 'both': 
            status_atual_jira = row['Status_Formatado_Conclusao']
            status_na_planilha = row[GOOGLE_SHEETS_COLUNA_STATUS]
            
            data_conclusao_jira = row['resolutionDate'] if pd.notna(row['resolutionDate']) else ''
            data_conclusao_na_planilha = row['outros'] # Pega o valor atual da planilha na coluna 'outros'

            # Verifica se alguma atualização é necessária (status OU data)
            needs_update = False
            if status_atual_jira != status_na_planilha:
                needs_update = True
            if data_conclusao_jira != data_conclusao_na_planilha:
                needs_update = True

            if needs_update:
                
                original_sheet_row_index = df_google_sheet[df_google_sheet[GOOGLE_SHEETS_COLUNA_JIRA_KEY].astype(str) == str(jira_key)].index[0]
                row_number_in_sheet = original_sheet_row_index + 2 # +1 para 1-based, +1 para o cabeçalho

                
                range_update_start_col = col_letter_status
                range_update_end_col = col_letter_outros
                
                updates_for_sheets_api.append({
                    'range': f"{GOOGLE_SHEETS_ABA_NOME}!{range_update_start_col}{row_number_in_sheet}:{range_update_end_col}{row_number_in_sheet}",
                    'values': [[status_atual_jira, data_conclusao_jira]] # Array com os valores para as colunas B e C
                })
                print(f"    -> UPDATE: ID {jira_key} (Status: '{status_na_planilha}'->'{status_atual_jira}', Outros (Data): '{data_conclusao_na_planilha}'->'{data_conclusao_jira}')")

        elif row['_merge'] == 'right_only': 
            # Preparar nova linha para ser adicionada
            new_rows_for_sheets_api.append([
                str(row['key_jira']),                            # Coluna 1: id key
                row['Status_Formatado_Conclusao'],          # Coluna 2: status
                row['resolutionDate_jira'] if pd.notna(row['resolutionDate_jira']) else '' # Coluna 3: outros (data de conclusão)
            ])
            print(f"    -> NOVO: ID {row['key_jira']} será adicionado com status '{row['Status_Formatado_Conclusao']}' e data '{row['resolutionDate_jira'] if pd.notna(row['resolutionDate_jira']) else ''}'")

    #Executar Atualizações e Inserções na Planilha Google ---
    print("\nExecutando ações na Planilha Google...")
    if updates_for_sheets_api:
        print(f"Enviando {len(updates_for_sheets_api)} atualizações de status e data...")
        update_google_sheet_batch(sheets_service, GOOGLE_SHEETS_ID, updates_for_sheets_api)
        print("Atualizações concluídas.")
    else:
        print("Nenhuma atualização de status ou data necessária.")

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