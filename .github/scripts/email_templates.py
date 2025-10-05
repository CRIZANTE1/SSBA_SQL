
"""
Este arquivo centraliza os templates de e-mail em HTML para as notificações do sistema.
Utiliza uma sintaxe de template simples (ex: {{ variavel }}) que pode ser processada
por uma função de renderização.
"""

TEMPLATES = {
    'overdue_actions': {
        'subject': '⚠️ Alerta: Ações de Abrangência Atrasadas - {{current_date}}',
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
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ Alerta: Ações de Abrangência Atrasadas</h1>
        <p class="alert-summary">
            Este é um lembrete automático sobre as seguintes ações com prazo vencido.<br>
            Por favor, acesse o sistema para atualizar o status.
        </p>

        <!-- Início do loop de unidades -->
        {{units_html_block}}
        <!-- Fim do loop de unidades -->

        <p class="footer">Este é um e-mail automático. Por favor, não responda.</p>
    </div>
</body>
</html>
'''
    },

    'equipment_expiring': {
        'subject': '⏰ Equipamentos vencendo em {{days_notice}} dias - ISF IA',
        'template': '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Equipamentos Vencendo - ISF IA</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background-color: #f4f4f4; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #ff6b35, #f7931e); color: white; padding: 20px; text-align: center; }
        .content { padding: 30px; }
        .alert-box { background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 20px 0; }
        .equipment-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .equipment-table th, .equipment-table td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        .equipment-table th { background-color: #f8f9fa; font-weight: bold; color: #495057; }
        .equipment-table tbody tr:nth-child(even) { background-color: #f8f9fa; }
        .equipment-table tbody tr:hover { background-color: #e9ecef; }
        .priority-high { color: #dc3545; font-weight: bold; }
        .priority-medium { color: #fd7e14; font-weight: bold; }
        .priority-low { color: #28a745; font-weight: bold; }
        .action-button { display: inline-block; background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }
        .action-button:hover { background-color: #0056b3; }
        .footer { background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; }
        .icon { font-size: 18px; margin-right: 8px; }
        .summary-box { background-color: #d1ecf1; border: 1px solid #bee5eb; border-radius: 5px; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏰ Alerta de Vencimentos - ISF IA</h1>
            <p>Equipamentos necessitando atenção nos próximos {{days_notice}} dias</p>
        </div>
        <div class="content">
            <p>Olá <strong>{{recipient_name}}</strong>,</p>
            <div class="alert-box">
                <h3>📋 Resumo do Alerta</h3>
                <p><strong>{{total_items}} equipamento(s)</strong> necessitam de atenção nos próximos <strong>{{days_notice}} dias</strong>.</p>
            </div>
            <h3>🔧 Equipamentos Vencendo</h3>
            <table class="equipment-table">
                <thead>
                    <tr>
                        <th>🏷️ Tipo</th>
                        <th>🔢 Identificação</th>
                        <th>⚙️ Serviço</th>
                        <th>📅 Data Vencimento</th>
                        <th>⏱️ Dias Restantes</th>
                        <th>📊 Prioridade</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Exemplo de como usar um loop em um template real (requer Jinja2 ou similar) -->
                    {% for equipment in expiring_equipment %}
                    <tr>
                        <td><strong>{{equipment.tipo}}</strong></td>
                        <td>{{equipment.identificacao}}</td>
                        <td>{{equipment.servico}}</td>
                        <td>{{equipment.data_vencimento}}</td>
                        <td>...</td>
                        <td>...</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <div class="summary-box">
                <h4>🎯 Ação Necessária</h4>
                <p>Acesse o sistema para agendar os serviços e manter a conformidade:</p>
                <a href="{{login_url}}" class="action-button">🚀 Acessar Sistema ISF IA</a>
            </div>
            <p>Atenciosamente,<br>
            <strong>Equipe ISF IA</strong></p>
        </div>
        <div class="footer">
            <p>Esta é uma notificação automática do sistema de gestão ISF IA.</p>
        </div>
    </div>
</body>
</html>
'''
    },
    
    'pending_issues': {
        'subject': '🚨 Pendências críticas encontradas - ISF IA',
        'template': '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pendências Críticas - ISF IA</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background-color: #f4f4f4; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; text-align: center; }
        .content { padding: 30px; }
        .alert-box { background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 15px; margin: 20px 0; }
        .issues-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .issues-table th, .issues-table td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        .issues-table th { background-color: #dc3545; color: white; font-weight: bold; }
        .action-button { display: inline-block; background-color: #dc3545; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }
        .footer { background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 Alerta de Pendências Críticas</h1>
            <p>Ações imediatas necessárias para conformidade</p>
        </div>
        <div class="content">
            <p>Olá <strong>{{recipient_name}}</strong>,</p>
            <div class="alert-box">
                <h3>🚨 Atenção: Pendências Críticas Identificadas!</h3>
                <p>Encontramos <strong>{{total_pending}} pendência(s)</strong> que necessitam de ação imediata.</p>
            </div>
            <h3>🔴 Pendências Críticas</h3>
            <table class="issues-table">
                <thead>
                    <tr>
                        <th>🏷️ Tipo</th>
                        <th>🔢 Identificação</th>
                        <th>⚠️ Problema</th>
                        <th>📅 Data Identificação</th>
                        <th>📊 Prioridade</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Exemplo de como usar um loop em um template real (requer Jinja2 ou similar) -->
                    {% for issue in pending_issues %}
                    <tr>
                        <td><strong>{{issue.tipo}}</strong></td>
                        <td>{{issue.identificacao}}</td>
                        <td>{{issue.problema}}</td>
                        <td>{{issue.data_identificacao}}</td>
                        <td>...</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <a href="{{login_url}}" class="action-button">🚀 Resolver Pendências</a>
            <p>Atenciosamente,<br>
            <strong>Equipe ISF IA</strong></p>
        </div>
        <div class="footer">
            <p>Esta é uma notificação automática do sistema de gestão ISF IA.</p>
        </div>
    </div>
</body>
</html>
'''
    }
}
