import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd

# Adiciona o diretório raiz ao path para encontrar os módulos do projeto
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.incident_manager import IncidentManager

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    config = {
        "smtp_server": "smtp.gmail.com", 
        "smtp_port": 465, 
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_email": os.getenv("RECEIVER_EMAIL")
    }
    if not all([config["sender_email"], config["sender_password"], config["receiver_email"]]):
        missing = [key for key, value in config.items() if not value and ("email" in key or "password" in key)]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique os Secrets do GitHub.")
    return config

def format_overdue_items_email(overdue_df: pd.DataFrame) -> str:
    """Formata um DataFrame de itens atrasados em um corpo de e-mail HTML."""
    html_style = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; }
        .container { max-width: 950px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; }
        h1 { font-size: 24px; text-align: center; color: #c0392b; }
        h2 { font-size: 18px; color: #34495e; margin-top: 35px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 25px; font-size: 13px; }
        th, td { border: 1px solid #dddddd; padding: 8px 12px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
    """
    html_body = f"""
    <html><head>{html_style}</head><body><div class="container">
    <h1>Alerta de Ações de Abrangência Atrasadas</h1>
    <p style="text-align:center;">Relatório automático gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    """
    
    # Agrupa por unidade para criar uma seção para cada uma
    for unit_name, group in overdue_df.groupby('unidade_operacional'):
        html_body += f'<h2>Unidade: {unit_name} ({len(group)} iten(s) atrasado(s))</h2>'
        
        # Formata a data para exibição
        group_display = group.copy()
        group_display['prazo_inicial'] = pd.to_datetime(group_display['prazo_inicial']).dt.strftime('%d/%m/%Y')
        
        cols_to_show = {
            'descricao_acao': 'Ação de Abrangência',
            'responsavel_email': 'Responsável',
            'prazo_inicial': 'Prazo'
        }
        group_display = group_display[cols_to_show.keys()].rename(columns=cols_to_show)
        
        html_body += group_display.to_html(index=False, border=0, na_rep='N/A')
            
    html_body += "</div></body></html>"
    return html_body

def send_smtp_email(html_body: str, config: dict):
    """Envia o e-mail usando as configurações fornecidas."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Alerta: Ações de Abrangência Atrasadas - {datetime.now().strftime('%d/%m/%Y')}"
    message["From"] = config["sender_email"]
    message["To"] = config["receiver_email"]
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        print(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            print("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            print(f"Enviando e-mail para {config['receiver_email']}...")
            server.sendmail(config["sender_email"], config["receiver_email"].split(','), message.as_string())
            print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """Função principal que busca itens atrasados em todas as unidades e envia um e-mail consolidado."""
    print("Iniciando script de notificação de ações de abrangência...")
    try:
        config = get_smtp_config_from_env()
        
        global_manager = GlobalMatrixManager()
        all_units = global_manager.get_all_units()
        matrix_spreadsheet_id = global_manager.spreadsheet.id
        
        # Carrega as descrições das ações da planilha central uma única vez
        central_incident_manager = IncidentManager(matrix_spreadsheet_id)
        blocking_actions_df = central_incident_manager.sheet_ops.get_df_from_worksheet("acoes_bloqueio")
        if blocking_actions_df.empty:
            print("AVISO: Não foi possível carregar as descrições das ações de bloqueio. As descrições estarão ausentes no e-mail.")

        all_overdue_items = []
        
        for unit in all_units:
            unit_name, spreadsheet_id = unit.get('nome_unidade'), unit.get('spreadsheet_id')
            if not spreadsheet_id:
                print(f"AVISO: Unidade '{unit_name}' sem spreadsheet_id. Pulando.")
                continue
            
            print(f"--- Processando unidade: {unit_name} ---")
            unit_incident_manager = IncidentManager(spreadsheet_id)
            action_plan_df = unit_incident_manager.sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")

            if action_plan_df.empty or 'status' not in action_plan_df.columns or 'prazo_inicial' not in action_plan_df.columns:
                continue

            # Filtra por status pendente/em andamento
            pending_items = action_plan_df[action_plan_df['status'].str.lower().isin(['pendente', 'em andamento'])].copy()
            if pending_items.empty:
                continue

            # Verifica o prazo
            pending_items['prazo_dt'] = pd.to_datetime(pending_items['prazo_inicial'], errors='coerce').dt.date
            today = datetime.now().date()
            overdue_items = pending_items[pending_items['prazo_dt'] < today]

            if not overdue_items.empty:
                all_overdue_items.append(overdue_items)

        if not all_overdue_items:
            print("Nenhum item de ação de abrangência atrasado encontrado em todas as unidades. E-mail não será enviado.")
            return

        print(f"Encontrados {sum(len(df) for df in all_overdue_items)} itens atrasados. Gerando relatório...")
        consolidated_df = pd.concat(all_overdue_items, ignore_index=True)

        # Adiciona a descrição da ação ao relatório
        if not blocking_actions_df.empty:
            final_df = pd.merge(
                consolidated_df,
                blocking_actions_df[['id', 'descricao_acao']],
                left_on='id_acao_bloqueio',
                right_on='id',
                how='left'
            )
        else:
            final_df = consolidated_df
            final_df['descricao_acao'] = "Descrição não encontrada"

        email_body = format_overdue_items_email(final_df)
        send_smtp_email(email_body, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"Erro fatal no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()