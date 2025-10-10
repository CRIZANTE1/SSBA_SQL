# .github/scripts/email_notifier.py
import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# --- Configuração de Path ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    
    from database.supabase_operations import SupabaseOperations
    from email_templates import EMPLATES
except ImportError as e:
    print(f"Erro de importação: {e}")
    sys.exit(1)

load_dotenv(os.path.join(root_dir, '.env'))

# URL do aplicativo (ajuste conforme sua URL real)
APP_URL = os.getenv("APP_URL", "https://seu-app.streamlit.app")

# --- Funções Auxiliares ---
def get_smtp_config_from_env():
    receiver_emails_str = os.getenv("RECEIVER_EMAIL", "")
    admin_emails = [email.strip() for email in receiver_emails_str.split(',') if email.strip()]
    config = {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 465)),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_emails_admin": admin_emails 
    }
    if not all([config["sender_email"], config["sender_password"]]):
        missing = [key for key, value in config.items() if key != "receiver_emails_admin" and not value]
        raise ValueError(f"Variáveis de ambiente ausentes: {', '.join(missing)}.")
    return config

def render_template(template_str: str, context: dict) -> str:
    for key, value in context.items():
        template_str = template_str.replace(f"{{{{{key}}}}}", str(value))
    return template_str

def send_smtp_email(subject: str, html_body: str, recipients: list, config: dict):
    if not recipients:
        print("Nenhum destinatário válido fornecido. Pulando envio.")
        return
    valid_recipients = sorted(list(set([email for email in recipients if email and '@' in email])))
    if not valid_recipients:
        print("Nenhum destinatário válido após a limpeza. Pulando envio.")
        return
    
    recipient_str = ", ".join(valid_recipients)
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"Sistema de Abrangência <{config['sender_email']}>"
    message["To"] = recipient_str
    message.attach(MIMEText(html_body, "html", "utf-8"))
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            server.login(config["sender_email"], config["sender_password"])
            server.sendmail(config["sender_email"], valid_recipients, message.as_string())
            print(f"E-mail enviado com sucesso para: {recipient_str}")
    except Exception as e:
        print(f"ERRO ao enviar e-mail para {recipient_str}: {e}")

# --- Funções de Formatação de E-mail ---

def format_user_email_content(group_df: pd.DataFrame) -> str:
    """Formata o bloco HTML para o e-mail do usuário, com as tabelas de suas pendências."""
    html_block = ""
    for unit_name, group in group_df.groupby('unidade_operacional'):
        html_block += f'<h2>Unidade: {unit_name} ({len(group)} item(s) atrasado(s))</h2>'
        group_display = group.copy()
        group_display['prazo_inicial'] = pd.to_datetime(group_display['prazo_inicial'], dayfirst=True).dt.strftime('%d/%m/%Y')
        cols_to_show = {'descricao_acao': 'Ação de Abrangência', 'prazo_inicial': 'Prazo Vencido'}
        group_display = group_display[list(cols_to_show.keys())].rename(columns=cols_to_show)
        html_block += group_display.to_html(index=False, border=0, na_rep='N/A')
    return html_block

def format_admin_summary_table(overdue_df: pd.DataFrame) -> str:
    """Formata a tabela HTML consolidada para o relatório do administrador."""
    summary_df = overdue_df.copy()
    summary_df['prazo_inicial'] = pd.to_datetime(summary_df['prazo_inicial'], dayfirst=True).dt.strftime('%d/%m/%Y')
    cols_to_show = {
        'unidade_operacional': 'Unidade',
        'descricao_acao': 'Ação de Abrangência',
        'responsavel_email': 'Responsável',
        'prazo_inicial': 'Prazo Vencido'
    }
    summary_df = summary_df[list(cols_to_show.keys())].rename(columns=cols_to_show)
    return summary_df.to_html(index=False, na_rep='N/A')

# --- Funções de Lógica de Envio ---

def send_user_notifications(grouped_by_responsible, config: dict):
    """Envia e-mails individuais para cada responsável com suas pendências."""
    print("\n--- Iniciando envio de notificações para usuários ---")
    email_tpl = EMPLATES['overdue_actions']
    
    for (resp_email, co_resp_email), group_df in grouped_by_responsible:
        recipients = [resp_email]
        if co_resp_email:
            recipients.append(co_resp_email)
        
        units_html = format_user_email_content(group_df)
        context = {
            "current_date": datetime.now().strftime('%d/%m/%Y'),
            "units_html_block": units_html,
            "app_url": APP_URL
        }
        
        email_body = render_template(email_tpl['template'], context)
        email_subject = render_template(email_tpl['subject'], context)
        
        send_smtp_email(email_subject, email_body, recipients, config)

def send_admin_summary(overdue_df: pd.DataFrame, config: dict):
    """Envia um único relatório gerencial consolidado para os administradores."""
    print("\n--- Iniciando envio de relatório gerencial para administradores ---")
    
    # Verifica se há administradores configurados
    admin_recipients = config.get('receiver_emails_admin', [])
    if not admin_recipients:
        print("AVISO: Nenhum e-mail de administrador configurado. Pulando envio do relatório gerencial.")
        return
    
    email_tpl = EMPLATES['admin_summary_report']

    summary_table_html = format_admin_summary_table(overdue_df)
    context = {
        "current_date": datetime.now().strftime('%d/%m/%Y'),
        "total_overdue": len(overdue_df),
        "total_units": overdue_df['unidade_operacional'].nunique(),
        "summary_table_html": summary_table_html,
        "app_url": APP_URL
    }

    email_body = render_template(email_tpl['template'], context)
    email_subject = render_template(email_tpl['subject'], context)
    
    print(f"Enviando relatório para administradores: {', '.join(admin_recipients)}")
    send_smtp_email(email_subject, email_body, admin_recipients, config)

# --- Função Principal ---

def main():
    print("Iniciando script de notificação...")
    try:
        config = get_smtp_config_from_env()
        ops = SupabaseOperations()
        print("Carregando dados das tabelas no banco de dados...")
        action_plan_df = ops.get_table_data("plano_de_acao_abrangencia")
        blocking_actions_df = ops.get_table_data("acoes_bloqueio")

        if action_plan_df.empty:
            print("Plano de ação vazio. Encerrando.")
            return

        pending_items = action_plan_df[action_plan_df['status'].str.lower().isin(['pendente', 'em andamento'])].copy()
        pending_items['prazo_dt'] = pd.to_datetime(pending_items['prazo_inicial'], errors='coerce', dayfirst=True).dt.date
        today = datetime.now().date()
        overdue_items = pending_items[pending_items['prazo_dt'] < today]

        if overdue_items.empty:
            print("Nenhum item de ação de abrangência atrasado encontrado. Encerrando.")
            return

        print(f"Encontrados {len(overdue_items)} itens atrasados. Preparando e-mails...")
        
        if not blocking_actions_df.empty:
            final_df = pd.merge(overdue_items, blocking_actions_df[['id', 'descricao_acao']], left_on='id_acao_bloqueio', right_on='id', how='left')
        else:
            final_df = overdue_items
            final_df['descricao_acao'] = "Descrição da ação não encontrada"

        if 'co_responsavel_email' not in final_df.columns:
            final_df['co_responsavel_email'] = ''
        # Corrigido o warning do pandas
        final_df['co_responsavel_email'] = final_df['co_responsavel_email'].fillna('')
        
        # Agrupa os itens para notificar os responsáveis
        grouped_by_responsible = final_df.groupby(['responsavel_email', 'co_responsavel_email'])
        
        # ETAPA 1: Enviar notificações para os usuários
        send_user_notifications(grouped_by_responsible, config)

        # ETAPA 2: Enviar o relatório consolidado para os administradores
        send_admin_summary(final_df, config)
        
        print("\nScript finalizado com sucesso.")

    except Exception as e:
        print(f"ERRO FATAL no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
