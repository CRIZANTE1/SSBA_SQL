
TEMPLATES = {
    'overdue_actions': {
        'subject': '⚠️ Lembrete: Ações de Abrangência Atrasadas sob sua responsabilidade - {{current_date}}',
        'template': '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Alerta de Ações Atrasadas</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; color: #333; background-color: #f4f7f6; margin: 0; padding: 20px;}
        .container { max-width: 950px; margin: 20px auto; padding: 20px; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { font-size: 24px; text-align: center; color: #c0392b; border-bottom: 2px solid #c0392b; padding-bottom: 10px; margin-top: 0; }
        h2 { font-size: 18px; color: #34495e; margin-top: 35px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
        p { line-height: 1.6; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 25px; font-size: 13px; background-color: #ffffff; }
        th, td { border: 1px solid #dddddd; padding: 10px 14px; text-align: left; }
        th { background-color: #f2f2f2; font-weight: bold; }
        .footer { font-size: 12px; text-align: center; color: #888; margin-top: 30px; }
        .alert-summary { text-align: center; font-style: italic; color: #555; margin-bottom: 30px; }
        .btn-access { display: inline-block; margin: 25px auto; padding: 12px 30px; background-color: #0068C9; color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; text-align: center; }
        .btn-access:hover { background-color: #0056a3; }
        .access-container { text-align: center; margin: 25px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Lembrete: Ações Atrasadas</h1>
        <p class="alert-summary">
            Este é um lembrete automático sobre as seguintes ações com prazo vencido sob sua responsabilidade.<br>
            Por favor, acesse o sistema para atualizar o status.
        </p>
        {{units_html_block}}
        <div class="access-container">
            <a href="{{app_url}}" class="btn-access">🔗 Acessar o Sistema de Abrangência</a>
        </div>
        <p class="footer">Este é um e-mail automático. Por favor, não responda.</p>
    </div>
</body>
</html>
'''
    },

    # --- TEMPLATE PARA O ADMIN ---
    'admin_summary_report': {
        'subject': '📊 Relatório Gerencial: Ações de Abrangência Atrasadas - {{current_date}}',
        'template': '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório Gerencial de Ações Atrasadas</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; color: #333; background-color: #f4f7f6; margin: 0; padding: 20px;}
        .container { max-width: 950px; margin: 20px auto; padding: 20px; background-color: #ffffff; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { font-size: 24px; text-align: center; color: #2980b9; border-bottom: 2px solid #2980b9; padding-bottom: 10px; margin-top: 0; }
        .summary-metrics { display: flex; justify-content: space-around; text-align: center; padding: 20px; background-color: #ecf0f1; border-radius: 5px; margin-bottom: 30px; }
        .metric { flex: 1; }
        .metric h3 { margin: 0 0 5px 0; font-size: 16px; color: #34495e; }
        .metric p { margin: 0; font-size: 28px; font-weight: bold; color: #c0392b; }
        h2 { font-size: 20px; color: #34495e; margin-top: 30px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin-top: 15px; font-size: 13px; }
        th, td { border: 1px solid #dddddd; padding: 10px 14px; text-align: left; }
        th { background-color: #34495e; color: white; font-weight: bold; }
        .footer { font-size: 12px; text-align: center; color: #888; margin-top: 30px; }
        .btn-access { display: inline-block; margin: 25px auto; padding: 12px 30px; background-color: #2980b9; color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; text-align: center; }
        .btn-access:hover { background-color: #1c5a85; }
        .access-container { text-align: center; margin: 25px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Relatório Gerencial de Ações Atrasadas</h1>
        <div class="summary-metrics">
            <div class="metric">
                <h3>Total de Ações Atrasadas</h3>
                <p>{{total_overdue}}</p>
            </div>
            <div class="metric">
                <h3>Unidades com Pendências</h3>
                <p>{{total_units}}</p>
            </div>
        </div>
        <h2>Lista Completa de Pendências</h2>
        <p>A tabela abaixo detalha todas as ações de abrangência com prazo vencido em todas as unidades.</p>
        {{summary_table_html}}
        <div class="access-container">
            <a href="{{app_url}}" class="btn-access">🔗 Acessar o Dashboard Administrativo</a>
        </div>
        <p class="footer">Este é um relatório automático gerado pelo Sistema de Abrangência.</p>
    </div>
</body>
</html>
'''
    }
}
