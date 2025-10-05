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
# Adiciona o diretório raiz ao path para encontrar os módulos do projeto
try:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    from operations.sheet import SheetOperations
except ImportError:
    # Fallback para execução local
    sys.path.append(os.path.abspath(os.path.join(root_dir, '..')))
    from operations.sheet import SheetOperations

# Carrega variáveis de ambiente de um arquivo .env (para desenvolvimento local)
load_dotenv()

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    # --- INÍCIO DA CORREÇÃO 1 ---
    # Lê a string de e-mails do admin e a converte em uma lista limpa.
    receiver_emails_str = os.getenv("RECEIVER_EMAIL", "")
    admin_emails = [email.strip() for email in receiver_emails_str.split(',') if email.strip()]

    config = {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 465)),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        # RECEIVER_EMAIL agora é uma lista de e-mails do admin/gestor.
        "receiver_emails_admin": admin_emails 
    }
    # Validação para garantir que as credenciais essenciais estão presentes
    if not all([config["sender_email"], config["sender_password"], config["receiver_emails_admin"]]):
        # A validação funciona porque uma lista vazia ([]) é "Falsy" em Python.
        missing = [key for key, value in config.items() if not value]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique os Secrets do repositório.")
    # --- FIM DA CORREÇÃO 1 ---
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
    <p style="text-align:center;">Este é um lembrete automático sobre as seguintes ações com prazo vencido. Por favor, atualize o status no sistema.</p>
    """
    
    # Agrupa por unidade para melhor organização no corpo do e-mail
    for unit_name, group in overdue_df.groupby('unidade_operacional'):
        html_body += f'<h2>Unidade: {unit_name} ({len(group)} item(s) atrasado(s))</h2>'
        
        group_display = group.copy()
        group_display['prazo_inicial'] = pd.to_datetime(group_display['prazo_inicial'], dayfirst=True).dt.strftime('%d/%m/%Y')
        
        cols_to_show = {
            'descricao_acao': 'Ação de Abrangência',
            'responsavel_email': 'Responsável',
            'co_responsavel_email': 'Co-responsável',
            'prazo_inicial': 'Prazo Vencido'
        }
        # Garante que a coluna 'co_responsavel_email' exista
        if 'co_responsavel_email' not in group_display.columns:
            group_display['co_responsavel_email'] = ""

        group_display = group_display[list(cols_to_show.keys())].rename(columns=cols_to_show)
        html_body += group_display.to_html(index=False, border=0, na_rep='N/A')
            
    html_body += "<p class='footer'>Este é um e-mail automático. Por favor, não responda.</p></div></body></html>"
    return html_body

def send_smtp_email(html_body: str, recipients: list, config: dict):
    """Envia um e-mail para uma lista de destinatários."""
    if not recipients:
        print("Nenhum destinatário válido fornecido. Pulando envio.")
        return

    # Limpa a lista de destinatários: remove e-mails vazios, duplicados.
    valid_recipients = sorted(list(set([email for email in recipients if email and '@' in email])))
    if not valid_recipients:
        print("Nenhum destinatário válido após a limpeza. Pulando envio.")
        return
        
    recipient_str = ", ".join(valid_recipients)

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Alerta: Ações de Abrangência Atrasadas - {datetime.now().strftime('%d/%m/%Y')}"
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
    """Função principal que busca itens atrasados e envia e-mails consolidados por responsável."""
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

        # 1. Filtra por itens com status pendente/em andamento
        pending_items = action_plan_df[action_plan_df['status'].str.lower().isin(['pendente', 'em andamento'])].copy()
        
        # 2. Verifica o prazo
        pending_items['prazo_dt'] = pd.to_datetime(pending_items['prazo_inicial'], errors='coerce', dayfirst=True).dt.date
        today = datetime.now().date()
        overdue_items = pending_items[pending_items['prazo_dt'] < today]

        if overdue_items.empty:
            print("Nenhum item de ação de abrangência atrasado encontrado. Encerrando.")
            return

        print(f"Encontrados {len(overdue_items)} itens atrasados. Preparando e-mails...")
        
        # 3. Junta com as descrições das ações
        if not blocking_actions_df.empty:
            final_df = pd.merge(overdue_items, blocking_actions_df[['id', 'descricao_acao']], left_on='id_acao_bloqueio', right_on='id', how='left')
        else:
            final_df = overdue_items
            final_df['descricao_acao'] = "Descrição da ação não encontrada"

        # 4. Agrupa por responsáveis para enviar e-mails consolidados
        if 'co_responsavel_email' not in final_df.columns:
            final_df['co_responsavel_email'] = ''
        final_df['co_responsavel_email'].fillna('', inplace=True) # Garante que não haja valores nulos

        grouped_by_responsible = final_df.groupby(['responsavel_email', 'co_responsavel_email'])
        
        for (resp_email, co_resp_email), group_df in grouped_by_responsible:
            # Monta a lista de destinatários para este grupo
            recipients = [resp_email]
            if co_resp_email:
                recipients.append(co_resp_email)
            

            recipients.extend(config['receiver_emails_admin'])
            # --- FIM DA CORREÇÃO 2 ---
            
            # Formata o corpo do e-mail com os itens específicos deste grupo
            email_body = format_overdue_items_email(group_df)
            
            # Envia o e-mail
            send_smtp_email(email_body, recipients, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"ERRO FATAL no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
