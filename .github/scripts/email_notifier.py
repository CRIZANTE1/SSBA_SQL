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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Subimos dois níveis para chegar à raiz do projeto (de .github/scripts para a raiz)
    root_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    
    from operations.sheet import SheetOperations
    from email_templates import EMPLATES # Importa os templates do arquivo local
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Verifique se o script está sendo executado a partir do diretório correto e se a estrutura de pastas está correta.")
    sys.exit(1)

# Carrega variáveis de ambiente de um arquivo .env (para desenvolvimento local)
load_dotenv(os.path.join(root_dir, '.env'))

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    receiver_emails_str = os.getenv("RECEIVER_EMAIL", "")
    admin_emails = [email.strip() for email in receiver_emails_str.split(',') if email.strip()]

    config = {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 465)),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_emails_admin": admin_emails 
    }
    if not all([config["sender_email"], config["sender_password"], config["receiver_emails_admin"]]):
        missing = [key for key, value in config.items() if not value]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique os Secrets.")
    return config

def render_template(template_str: str, context: dict) -> str:
    """Substitui placeholders em uma string de template com valores de um dicionário."""
    for key, value in context.items():
        template_str = template_str.replace(f"{{{{{key}}}}}", str(value))
    return template_str

def format_units_html_block(overdue_df: pd.DataFrame) -> str:
    """Formata um DataFrame de itens atrasados em um bloco HTML com tabelas por unidade."""
    html_block = ""
    
    # Agrupa por unidade para melhor organização no corpo do e-mail
    for unit_name, group in overdue_df.groupby('unidade_operacional'):
        html_block += f'<h2>Unidade: {unit_name} ({len(group)} item(s) atrasado(s))</h2>'
        
        group_display = group.copy()
        group_display['prazo_inicial'] = pd.to_datetime(group_display['prazo_inicial'], dayfirst=True).dt.strftime('%d/%m/%Y')
        
        cols_to_show = {
            'descricao_acao': 'Ação de Abrangência',
            'responsavel_email': 'Responsável',
            'co_responsavel_email': 'Co-responsável',
            'prazo_inicial': 'Prazo Vencido'
        }
        if 'co_responsavel_email' not in group_display.columns:
            group_display['co_responsavel_email'] = ""

        group_display = group_display[list(cols_to_show.keys())].rename(columns=cols_to_show)
        html_block += group_display.to_html(index=False, border=0, na_rep='N/A')
            
    return html_block

def send_smtp_email(subject: str, html_body: str, recipients: list, config: dict):
    """Envia um e-mail para uma lista de destinatários."""
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
            print(f"E-mail de lembrete enviado com sucesso para: {recipient_str}")
    except Exception as e:
        print(f"ERRO ao enviar e-mail para {recipient_str}: {e}")

def main():
    """Função principal que busca itens atrasados e envia e-mails consolidados."""
    print("Iniciando script de notificação...")
    try:
        config = get_smtp_config_from_env()
        sheet_ops = SheetOperations()

        print("Carregando dados da Planilha Matriz...")
        action_plan_df = sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")
        blocking_actions_df = sheet_ops.get_df_from_worksheet("acoes_bloqueio")

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
        final_df['co_responsavel_email'].fillna('', inplace=True)

        grouped_by_responsible = final_df.groupby(['responsavel_email', 'co_responsavel_email'])
        
        for (resp_email, co_resp_email), group_df in grouped_by_responsible:
            recipients = [resp_email]
            if co_resp_email:
                recipients.append(co_resp_email)
            recipients.extend(config['receiver_emails_admin'])
            
            # Pega o template do e-mail
            email_tpl = EMPLATES['overdue_actions']
            
            # Gera o bloco HTML dinâmico com as tabelas das unidades
            units_html = format_units_html_block(group_df)

            # Prepara o contexto para renderizar o template
            context = {
                "current_date": datetime.now().strftime('%d/%m/%Y'),
                "units_html_block": units_html
            }

            # Renderiza o corpo e o assunto final
            email_body = render_template(email_tpl['template'], context)
            email_subject = render_template(email_tpl['subject'], context)
            
            send_smtp_email(email_subject, email_body, recipients, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"ERRO FATAL no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
