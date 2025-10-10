# Guia de Row Level Security (RLS)

## Visão Geral

O sistema implementa RLS (Row Level Security) do PostgreSQL para controlar o acesso aos dados em nível de linha, baseado no usuário autenticado.

## Funções de Contexto

### auth.user_email()
Retorna o email do usuário autenticado via JWT.

### auth.user_role()
Retorna a role do usuário: 'admin', 'editor' ou 'viewer'.

### auth.user_unit()
Retorna a unidade operacional do usuário ou '*' para admins.

### auth.is_admin()
Verifica se o usuário é administrador.

### auth.can_edit()
Verifica se o usuário pode editar (admin ou editor).

### auth.belongs_to_unit(target_unit)
Verifica se o usuário pertence à unidade especificada.

## Matriz de Permissões

### Tabela: usuarios

| Operação | Admin | Editor | Viewer |
|----------|-------|--------|--------|
| SELECT   | Todos | Sua unidade | Sua unidade |
| INSERT   | ✅ | ❌ | ❌ |
| UPDATE   | Todos | Si mesmo | Si mesmo |
| DELETE   | ✅ | ❌ | ❌ |

### Tabela: incidentes

| Operação | Admin | Editor | Viewer |
|----------|-------|--------|--------|
| SELECT   | ✅ | ✅ | ✅ |
| INSERT   | ✅ | ❌ | ❌ |
| UPDATE   | ✅ | ❌ | ❌ |
| DELETE   | ✅ | ❌ | ❌ |

### Tabela: plano_de_acao_abrangencia

| Operação | Admin | Editor | Viewer |
|----------|-------|--------|--------|
| SELECT   | Todos | Sua unidade | Sua unidade |
| INSERT   | ✅ | Sua unidade | ❌ |
| UPDATE   | Todos | Sua unidade | ❌ |
| DELETE   | ✅ | ❌ | ❌ |

### Tabela: log_auditoria

| Operação | Admin | Editor | Viewer |
|----------|-------|--------|--------|
| SELECT   | Todos | Seus logs | Seus logs |
| INSERT   | ✅ | ✅ | ✅ |
| UPDATE   | ❌ | ❌ | ❌ |
| DELETE   | ✅ | ❌ | ❌ |

## Storage (Buckets)

### public-images
- **SELECT**: Público
- **INSERT**: Admins e Editores
- **DELETE**: Apenas Admins

### restricted-attachments
- **SELECT**: Apenas Autenticados
- **INSERT**: Apenas Admins
- **DELETE**: Apenas Admins

### action-evidence
- **SELECT**: Apenas Autenticados
- **INSERT**: Admins e Editores
- **DELETE**: Admins e Editores

## Testando RLS

### Via Script Python
```bash
python scripts/test_rls.py