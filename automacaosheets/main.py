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
JIRA_EMAIL = os.getenv('JIRA_EMAIL')  # Corrigido para bater com o .env
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

# Configurações do Google Sheets (puxadas do arquivo .env)
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
GOOGLE_SHEETS_ABA_NOME = os.getenv('GOOGLE_SHEETS_ABA_NOME')


# Nomes das colunas da sua planilha, padronizados para evitar confusão
GOOGLE_SHEETS_COLUNA_CHAVE = os.getenv('GOOGLE_SHEETS_COLUNA_JIRA_KEY')           # Nº card do Jira
GOOGLE_SHEETS_COLUNA_ESTADO = os.getenv('GOOGLE_SHEETS_COLUNA_STATUS')            # Status da atividade
GOOGLE_SHEETS_COLUNA_NOME_TAREFA = os.getenv('GOOGLE_SHEETS_COLUNA_NOME_TAREFA')  # Descrição da atividade

GOOGLE_CREDENTIALS_FILE = 'credentials.json'

# Status do Jira que significam "Concluído" (puxados do arquivo .env, divididos por vírgula)
# Converte para maiúsculas para comparação case-insensitive
JIRA_STATUS_CONCLUIDO = [s.strip().upper() for s in os.getenv('JIRA_STATUS_CONCLUIDO_LIST', 'Done').split(',')]


# Parâmetros para a JQL (mantidos para referência, mas não usados na função simulada)
JIRA_PROJETOS_PARA_MONITORAR = ["KAN"] 
JIRA_LABEL_PARA_MONITORAR = "automacao-status-sheets" 


#Funções de Conexão e API ---

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
            # AJUSTADO: Campos puxados do Jira. Removidos os que não serão usados na planilha.
            # Mantidos 'key', 'summary', 'status', 'resolutiondate'
            "fields": "key,summary,status,resolutiondate", 
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

    # --- A. Puxar Dados do Jira ---
    # JQL: Puxa todas as tarefas do projeto KAN que estão nos status especificados e foram atualizadas desde o início do mês.
    jql_query_jira = 'project = "KAN" AND status IN ("Em andamento", "IDEIA", "A FAZER", "TESTES", "CONCLUÍDO") AND updated >= startOfMonth() ORDER BY updated DESC'
    
    jira_issues_raw = get_jira_issues(jql_query_jira)

    if not jira_issues_raw:
        print("Nenhuma tarefa relevante encontrada no Jira com a JQL especificada. Encerrando.")
        return

    # Processar dados do Jira em um DataFrame
    jira_data_for_df = []
    for issue in jira_issues_raw:
        status_name = issue['fields'].get('status', {}).get('name', '')
        
        # Removidas variáveis de assignee, project_name, reporter, priority pois não serão usadas na planilha
        # assignee_display_name = 'Não Atribuído'
        # if issue['fields'].get('assignee'): assignee_display_name = issue['fields']['assignee'].get('displayName', 'Não Atribuído')
        # project_name_value = '' 
        # if issue['fields'].get('project'): project_name_value = issue['fields']['project'].get('name', '')

        jira_data_for_df.append({
            'key': issue.get('key'),
            'summary': issue['fields'].get('summary', ''), 
            'status_jira': status_name,
            'resolutionDate': issue['fields'].get('resolutiondate', '') 
        })
    df_jira = pd.DataFrame(jira_data_for_df)
    
    # Mapear status do Jira para "Concluído"/"Não Concluído"
    df_jira['Status_Formatado_Conclusao'] = df_jira['status_jira'].apply(
        lambda s: "Concluído" if s.upper() in JIRA_STATUS_CONCLUIDO else "Não Concluído"
    )
    print(f"Total de {len(df_jira)} tarefas processadas do Jira para a comparação.")

    # --- B. Puxar Dados da Planilha Google Existente ---
    sheets_service = get_google_sheets_service()
    if not sheets_service:
        print("Não foi possível conectar ao serviço do Google Sheets. Encerrando.")
        return

    # AJUSTADO: O range para leitura agora é A:B (Chave, Estado)

    range_to_read = f'{GOOGLE_SHEETS_ABA_NOME}!A:B' 
    sheet_values = read_google_sheet(sheets_service, GOOGLE_SHEETS_ID, range_to_read)

    if not sheet_values:
        print("Planilha Google vazia ou sem dados iniciais. Adicionando todas as tarefas como novas.")
        # AJUSTADO: Cabeçalho inicial da sua planilha com apenas 'Chave' e 'Estado'
        header_for_new_sheet = [
            GOOGLE_SHEETS_COLUNA_CHAVE, 
            GOOGLE_SHEETS_COLUNA_ESTADO
        ] 

        initial_data_to_add = []
        for _, row in df_jira.iterrows():
            initial_data_to_add.append([
                row['key'],                      # Coluna 1: Chave
                row['Status_Formatado_Conclusao'] # Coluna 2: Estado
            ])
        
        append_google_sheet_rows(sheets_service, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_ABA_NOME, [header_for_new_sheet] + initial_data_to_add)
        print("Planilha Google preenchida com as tarefas iniciais. Encerrando por esta execução.")
        return

    sheet_header = sheet_values[0]
    print("Cabeçalho da planilha:", sheet_header)  # Ajuda a depurar problemas de KeyError
    data_rows = []
    if len(sheet_values) > 1: 
        for row_data in sheet_values[1:]: 
            processed_row = [row_data[i] if i < len(row_data) else '' for i in range(len(sheet_header))]
            data_rows.append(processed_row)
    
    df_google_sheet = pd.DataFrame(data_rows, columns=sheet_header)
    print(f"Puxadas {len(df_google_sheet)} linhas da Planilha Google.")

    # --- C. Comparar e Preparar Atualizações/Novas Inserções ---
    updates_for_sheets_api = []
    new_rows_for_sheets_api = []

    try:
        col_index_chave = sheet_header.index(GOOGLE_SHEETS_COLUNA_CHAVE)
        col_index_estado = sheet_header.index(GOOGLE_SHEETS_COLUNA_ESTADO)
        
        col_letter_chave = chr(ord('A') + col_index_chave) 
        col_letter_estado = chr(ord('A') + col_index_estado)
    except ValueError as e:
        print(f"ERRO: Coluna '{e}' não encontrada no cabeçalho da Planilha Google. Verifique se os nomes (Chave, Estado) estão EXATOS!")
        return

    df_merged = pd.merge(
        df_google_sheet,
        df_jira,
        left_on=GOOGLE_SHEETS_COLUNA_CHAVE, 
        right_on='key',
        how='outer',
        suffixes=('_sheet', '_jira'),
        indicator=True
    )

    print("Iniciando comparação de dados...")
    for index_merged, row in df_merged.iterrows():
        # --- INÍCIO DO BLOCO DE DETERMINAÇÃO ROBUSTA DA JIRA_KEY E DADOS DA TAREFA JIRA ---
        # Garante que estas variáveis sempre tenham um valor (mesmo que vazio)
        jira_key = None
        jira_task_summary = '' # Mantido para a lógica de deduplicação pelo nome, se necessário
        jira_task_status_formatted = ''
        jira_task_resolution_date = '' # Mantido para a lógica, se necessário
        
        # Tenta extrair os dados do lado do Jira (se existirem)
        if 'key_jira' in row and pd.notna(row['key_jira']):
            jira_key = str(row['key_jira'])
            jira_task_summary = row.get('summary_jira', '') 
            jira_task_status_formatted = row.get('Status_Formatado_Conclusao', '')
            jira_task_resolution_date = row.get('resolutionDate_jira', '') if pd.notna(row.get('resolutionDate_jira')) else ''
        # Se não, tenta pegar a key do lado da Planilha (para linhas left_only)
        elif GOOGLE_SHEETS_COLUNA_CHAVE in row and pd.notna(row[GOOGLE_SHEETS_COLUNA_CHAVE]):
            jira_key = str(row[GOOGLE_SHEETS_COLUNA_CHAVE])
            jira_task_summary = row.get(GOOGLE_SHEETS_COLUNA_NOME_TAREFA, '')
            jira_task_status_formatted = row.get(GOOGLE_SHEETS_COLUNA_ESTADO, '')
            jira_task_resolution_date = row.get('outros', '')


        # Se, após todas as tentativas, a jira_key ainda for None, é um erro ou linha irrelevante
        if jira_key is None:
            print(f"Aviso: Não foi possível determinar a Chave Jira para a linha {index_merged} (Tipo Merge: {row.get('_merge')}). Pulando.")
            continue 

        if row['_merge'] == 'both': # Tarefa existe em ambos (Jira e Planilha)
            # Dados da Planilha (estado atual)
            estado_na_planilha = row[GOOGLE_SHEETS_COLUNA_ESTADO]

            # Verifica se alguma atualização é necessária
            needs_update = False
            if jira_task_status_formatted != estado_na_planilha:
                needs_update = True

            if needs_update:
                # Prepara os valores para as colunas 'Estado'
                values_to_update_row = [jira_task_status_formatted]
                # O range de atualização é apenas a coluna 'Estado'
                original_sheet_row_index = df_google_sheet[df_google_sheet[GOOGLE_SHEETS_COLUNA_CHAVE].astype(str) == str(jira_key)].index[0]
                range_update_start_col = col_letter_estado
                range_update_end_col = col_letter_estado 
                updates_for_sheets_api.append({
                    'range': f"{GOOGLE_SHEETS_ABA_NOME}!{range_update_start_col}{original_sheet_row_index + 2}:{range_update_end_col}{original_sheet_row_index + 2}",
                    'values': [values_to_update_row] 
                })
                print(f"    -> UPDATE: Chave {jira_key} (Estado: '{estado_na_planilha}'->'{jira_task_status_formatted}')")

        elif row['_merge'] == 'right_only': # Tarefa é nova (existe no Jira, mas não na Planilha pela Chave)
            # Os dados da tarefa já foram extraídos no início do loop (jira_key, jira_task_summary, etc.)

            # --- LÓGICA DE VERIFICAÇÃO EM 2 ETAPAS: Tentar encontrar pelo NOME (Resumo) ---
            found_by_name_in_sheet = False
            row_index_to_update_by_name = -1 

            for sheet_idx, sheet_row_data in df_google_sheet.iterrows():
                sheet_summary_value = sheet_row_data.get(GOOGLE_SHEETS_COLUNA_NOME_TAREFA, '')
                sheet_chave_value = sheet_row_data.get(GOOGLE_SHEETS_COLUNA_CHAVE, '')

                if (sheet_summary_value.strip().upper() == jira_task_summary.strip().upper()) and \
                   (pd.isna(sheet_chave_value) or sheet_chave_value == '' or (jira_key is not None and str(sheet_chave_value) != jira_key)):
                    found_by_name_in_sheet = True
                    row_index_to_update_by_name = sheet_idx 
                    log_message = f"    -> DEDUPLICAÇÃO: Chave {jira_key} (Jira) encontrada pelo Resumo '{jira_task_summary}' na linha {row_index_to_update_by_name + 2} da planilha. Atualizando."
                    print(log_message)
                    # Prepara a atualização para esta linha existente na planilha
                    original_sheet_row_index = row_index_to_update_by_name
                    row_number_in_sheet = original_sheet_row_index + 2 
                    # O range de atualização é apenas para Chave e Estado
                    range_update_start_col = col_letter_chave # Coluna 'Chave'
                    range_update_end_col = col_letter_estado # Coluna 'Estado'
                    updates_for_sheets_api.append({
                        'range': f"{GOOGLE_SHEETS_ABA_NOME}!{range_update_start_col}{row_number_in_sheet}:{range_update_end_col}{row_number_in_sheet}",
                        'values': [[
                            jira_key,        # Chave
                            jira_task_status_formatted # Estado
                        ]] 
                    })
                    break 
            
            if not found_by_name_in_sheet:
                # Se não encontrou pelo nome, então é uma nova tarefa de verdade
                new_rows_for_sheets_api.append([
                    jira_key,        # Chave
                    jira_task_status_formatted # Estado
                ])
                log_message = f"    -> NOVO: Chave {jira_key} será adicionada (Estado: '{jira_task_status_formatted}')"
                print(log_message)

        # Se for 'left_only', significa que a tarefa está na planilha mas não foi encontrada no Jira.
        # Por padrão, este script ignora.

    # --- D. Executar Atualizações e Inserções na Planilha Google ---
    print("\nExecutando ações na Planilha Google...")
    if updates_for_sheets_api:
        print(f"Enviando {len(updates_for_sheets_api)} atualizações de dados...")
        update_google_sheet_batch(sheets_service, GOOGLE_SHEETS_ID, updates_for_sheets_api)
        print("Atualizações concluídas.")
    else:
        print("Nenhuma atualização de dados necessária.")

    if new_rows_for_sheets_api:
        print(f"Adicionando {len(new_rows_for_sheets_api)} novas tarefas...")
        append_google_sheet_rows(sheets_service, GOOGLE_SHEETS_ID, GOOGLE_SHEETS_ABA_NOME, new_rows_for_sheets_api)
        print("Novas tarefas adicionadas.")
    else:
        print("Nenhuma nova tarefa para adicionar.")

    print("--- Automação concluída com sucesso! ---")

if __name__ == "__main__":
    run_automation()
