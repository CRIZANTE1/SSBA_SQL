import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv


try:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    from operations.sheet import SheetOperations
    from gdrive.config import SPREADSHEET_ID
except ImportError:
    # Fallback para execução local onde a estrutura de pastas pode ser diferente
    sys.path.append(os.path.abspath(os.path.join(root_dir, '..')))
    from operations.sheet import SheetOperations
    from gdrive.config import SPREADSHEET_ID

# Carrega variáveis de ambiente de um arquivo .env se ele existir (para desenvolvimento local)
load_dotenv()

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    config = {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 465)),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_email": os.getenv("RECEIVER_EMAIL")
    }
    if not all([config["sender_email"], config["sender_password"], config["receiver_email"]]):
        missing = [key for key, value in config.items() if not value and key.endswith(("_EMAIL", "_PASSWORD"))]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique o arquivo .env ou os Secrets do repositório.")
    return config

def format_overdue_items_email(overdue_df: pd.DataFrame) -> str:
    """Formata um DataFrame de itens atrasados em um corpo de e-mail HTML bem estruturado."""
    html_style = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; color: #333; }
        .container { max-width: 950px; margin: 20px auto; padding: 20px; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 8px; }
        h1 { font-size: 24px; text-align: center; color: #c0392b; border-bottom: 2px solid #c0392b; padding-bottom: 10px; }
        h2 { font-size: 18px; color: #34495e; margin-top: 35px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 25px; font-size: 13px; background-color: #ffffff; }
        th, td { border: 1px solid #dddddd; padding: 10px 14px; text-align: left; }
        th { background-color: #f2f2f2; font-weight: bold; }
        .footer { font-size: 12px; text-align: center; color: #888; margin-top: 30px; }
    </style>
    """
    html_body = f"""
    <html><head>{html_style}</head><body><div class="container">
    <h1>⚠️ Alerta: Ações de Abrangência Atrasadas</h1>
    <p style="text-align:center;">Relatório automático gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    """
    
    # Agrupa por unidade para criar uma seção para cada uma
    for unit_name, group in overdue_df.groupby('unidade_operacional'):
        html_body += f'<h2>Unidade: {unit_name} ({len(group)} item(s) atrasado(s))</h2>'
        
        # Formata a data para exibição
        group_display = group.copy()
        group_display['prazo_inicial'] = pd.to_datetime(group_display['prazo_inicial'], dayfirst=True).dt.strftime('%d/%m/%Y')
        
        cols_to_show = {
            'descricao_acao': 'Ação de Abrangência',
            'responsavel_email': 'Responsável',
            'prazo_inicial': 'Prazo Vencido'
        }
        group_display = group_display[list(cols_to_show.keys())].rename(columns=cols_to_show)
        
        html_body += group_display.to_html(index=False, border=0, na_rep='N/A')
            
    html_body += "<p class='footer'>Este é um e-mail automático. Por favor, não responda.</p></div></body></html>"
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
        print(f"ERRO: Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """
    Função principal que busca itens atrasados na Planilha Matriz e envia um e-mail consolidado.
    """
    print("Iniciando script de notificação de ações de abrangência...")
    try:
        config = get_smtp_config_from_env()
        sheet_ops = SheetOperations()

        print("Carregando dados da Planilha Matriz...")
        action_plan_df = sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")
        blocking_actions_df = sheet_ops.get_df_from_worksheet("acoes_bloqueio")

        if action_plan_df.empty or 'status' not in action_plan_df.columns or 'prazo_inicial' not in action_plan_df.columns:
            print("Plano de ação está vazio ou com colunas faltando. Encerrando.")
            return

        # 1. Filtra por status pendente/em andamento
        pending_items = action_plan_df[action_plan_df['status'].str.lower().isin(['pendente', 'em andamento'])].copy()
        if pending_items.empty:
            print("Nenhum item com status 'Pendente' ou 'Em Andamento'. Encerrando.")
            return

        # 2. Verifica o prazo
        # `dayfirst=True` é crucial para interpretar corretamente 'dd/mm/yyyy'
        pending_items['prazo_dt'] = pd.to_datetime(pending_items['prazo_inicial'], errors='coerce', dayfirst=True).dt.date
        today = datetime.now().date()
        overdue_items = pending_items[pending_items['prazo_dt'] < today]

        if overdue_items.empty:
            print("Nenhum item de ação de abrangência atrasado encontrado. E-mail não será enviado.")
            return

        print(f"Encontrados {len(overdue_items)} itens atrasados. Gerando relatório...")

        # 3. Adiciona a descrição da ação ao relatório
        if not blocking_actions_df.empty:
            final_df = pd.merge(
                overdue_items,
                blocking_actions_df[['id', 'descricao_acao']],
                left_on='id_acao_bloqueio',
                right_on='id',
                how='left'
            )
        else:
            print("AVISO: Não foi possível carregar as descrições das ações. Descrições estarão ausentes no e-mail.")
            final_df = overdue_items
            final_df['descricao_acao'] = "Descrição não encontrada"

        # 4. Formata e envia o e-mail
        email_body = format_overdue_items_email(final_df)
        send_smtp_email(email_body, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"ERRO FATAL no script: {e}")
        # Retorna um código de saída diferente de zero para indicar falha no GitHub Actions
        sys.exit(1)

if __name__ == "__main__":
    main()
