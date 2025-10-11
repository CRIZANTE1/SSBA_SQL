"""
Configurações centralizadas de cache para otimizar uso de recursos.
Ajuste estes valores baseado no uso real do sistema.
"""

# Tempos de cache em segundos
CACHE_TTL = {
    # Dados que mudam raramente
    'usuarios': 1800,  # 30 minutos
    'utilities': 1800,  # 30 minutos
    'unidades': 3600,  # 1 hora
    
    # Dados que mudam ocasionalmente
    'incidentes': 600,  # 10 minutos
    'acoes_bloqueio': 600,  # 10 minutos
    
    # Dados que mudam frequentemente
    'plano_acao': 300,  # 5 minutos
    'logs': 120,  # 2 minutos
    
    # Dados em tempo real
    'solicitacoes': 60,  # 1 minuto
}

# Configurações de imagens
IMAGE_COMPRESSION = {
    'max_size_kb': 300,  # Tamanho máximo em KB
    'max_dimension': 1920,  # Dimensão máxima em pixels
    'quality': 85,  # Qualidade JPEG inicial
}

# Configurações de paginação
PAGINATION = {
    'incidents_per_page': 20,
    'actions_per_page': 50,
    'logs_per_page': 100,
}