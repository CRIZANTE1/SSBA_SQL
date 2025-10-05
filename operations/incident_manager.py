import streamlit as st
import pandas as pd
import logging
from datetime import date
from operations.sheet import SheetOperations
from gdrive.matrix_manager import get_matrix_manager

logger = logging.getLogger('abrangencia_app.incident_manager')

@st.cache_resource
def get_incident_manager():
    """
    Retorna uma instância única (singleton) do IncidentManager para a sessão do usuário.
    Esta é a forma recomendada de acessar o gerenciador a partir das páginas de front-end.
    """
    return IncidentManager()

class IncidentManager:
    """
    Gerencia todas as operações de dados relacionadas a incidentes, ações de bloqueio
    e planos de ação, operando exclusivamente na Planilha Matriz (arquitetura single-tenant).
    """
    def __init__(self):
        """
        Inicializa o gerenciador. A conexão com a planilha é estabelecida
        automaticamente pela classe SheetOperations (Singleton).
        """
        self.sheet_ops = SheetOperations()
        if not self.sheet_ops.spreadsheet:
            # Erro crítico: se não há conexão, a aplicação não pode funcionar.
            raise ConnectionError("Falha na conexão com a Planilha Principal. Verifique as configurações e permissões.")

    def get_all_incidents(self) -> pd.DataFrame:
        """Retorna todos os incidentes da aba 'incidentes' como um DataFrame."""
        return self.sheet_ops.get_df_from_worksheet("incidentes")

    def get_incident_by_id(self, incident_id: str) -> pd.Series | None:
        """Busca um incidente específico pelo seu ID."""
        incidents_df = self.get_all_incidents()
        if incidents_df.empty:
            return None
        
        incident = incidents_df[incidents_df['id'] == str(incident_id)]
        return incident.iloc[0] if not incident.empty else None

    def add_incident(self, numero_alerta: str, evento_resumo: str, data_evento: date, o_que_aconteceu: str, por_que_aconteceu: str, foto_url: str, anexos_url: str) -> int | None:
        """
        Adiciona um novo registro de incidente na aba central 'incidentes'.
        """
        logger.info(f"Adicionando novo incidente: {numero_alerta}")
        data_evento_str = data_evento.strftime('%d/%m/%Y')

        new_incident_data = [
            numero_alerta, evento_resumo, data_evento_str,
            o_que_aconteceu, por_que_aconteceu, foto_url, anexos_url
        ]
        
        new_id = self.sheet_ops.adc_dados_aba("incidentes", new_incident_data)
        if new_id:
            logger.info(f"Incidente {new_id} adicionado com sucesso.")
            st.cache_data.clear()
        else:
            logger.error("Falha ao adicionar incidente na planilha.")
        return new_id

    def get_all_blocking_actions(self) -> pd.DataFrame:
        """Retorna todas as ações de bloqueio da aba 'acoes_bloqueio'."""
        return self.sheet_ops.get_df_from_worksheet("acoes_bloqueio")

    def get_blocking_actions_by_incident(self, incident_id: str) -> pd.DataFrame:
        """Retorna as ações de bloqueio para um ID de incidente específico."""
        actions_df = self.get_all_blocking_actions()
        if actions_df.empty:
            return pd.DataFrame()
        
        return actions_df[actions_df['id_incidente'] == str(incident_id)]

    def add_blocking_actions_batch(self, incident_id: str, descriptions: list[str]) -> bool:
        """
        Adiciona múltiplas ações de bloqueio em lote para um incidente.
        """
        if not descriptions:
            return True

        logger.info(f"Adicionando {len(descriptions)} ações de bloqueio para o incidente {incident_id}.")
        rows_to_add = [[str(incident_id), desc] for desc in descriptions]
        
        success = self.sheet_ops.adc_dados_aba_em_lote("acoes_bloqueio", rows_to_add)
        if success:
            logger.info("Ações de bloqueio em lote adicionadas com sucesso.")
            st.cache_data.clear()
        else:
            logger.error(f"Falha ao adicionar ações de bloqueio para o incidente {incident_id}.")
        return success

    def get_all_action_plans(self) -> pd.DataFrame:
        """Retorna todos os itens do plano de ação de abrangência da aba central."""
        return self.sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")

   def add_abrangencia_action(self, id_acao_bloqueio: str, unidade_operacional: str, responsavel_email: str, co_responsavel_email: str, prazo_inicial: date, status: str) -> int | None:
        """
        Adiciona um novo registro na aba central 'plano_de_acao_abrangencia',
        incluindo todas as colunas conforme definido em sheets_config.yaml
        """
        logger.info(f"Adicionando ação de abrangência para a ação {id_acao_bloqueio} na unidade {unidade_operacional}.")
        prazo_str = prazo_inicial.strftime('%d/%m/%Y')
        co_resp_email_str = co_responsavel_email if co_responsavel_email else ""
    
        # Ordem DEVE corresponder exatamente ao sheets_config.yaml
        new_action_data = [
            id_acao_bloqueio,          # id_acao_bloqueio
            unidade_operacional,       # unidade_operacional
            responsavel_email,         # responsavel_email
            co_resp_email_str,         # co_responsavel_email
            prazo_str,                 # prazo_inicial
            status,                    # status
            "",                        # data_conclusao (inicialmente vazia)
            "",                        # url_evidencia (inicialmente vazia)
            ""                         # detalhes_conclusao (inicialmente vazia)
        ]
    
        new_id = self.sheet_ops.adc_dados_aba("plano_de_acao_abrangencia", new_action_data)
        if new_id:
            logger.info(f"Ação de abrangência {new_id} adicionada com sucesso.")
            st.cache_data.clear()
        else:
            logger.error("Falha ao adicionar ação de abrangência na planilha.")
        return new_id

    def update_abrangencia_action(self, action_id: str, updates: dict) -> bool:
        """
        Atualiza uma linha específica na aba central 'plano_de_acao_abrangencia'.
        """
        logger.info(f"Atualizando ação de abrangência ID {action_id} com: {updates}")
        success = self.sheet_ops.update_row_by_id("plano_de_acao_abrangencia", action_id, updates)
        if success:
            logger.info(f"Ação {action_id} atualizada com sucesso.")
            st.cache_data.clear()
        else:
            logger.error(f"Falha ao atualizar a ação {action_id}.")
        return success

    def get_covered_incident_ids_for_unit(self, unit_name: str) -> set:
        """
        Retorna um conjunto de IDs de incidentes que já possuem pelo menos uma ação 
        de abrangência registrada para uma unidade operacional específica.
        """
        action_plan_df = self.get_all_action_plans()
        if action_plan_df.empty or 'unidade_operacional' not in action_plan_df.columns:
            return set()
    
        # Filtra as ações da unidade específica
        unit_actions_df = action_plan_df[action_plan_df['unidade_operacional'] == unit_name]
        if unit_actions_df.empty:
            return set()
    
        all_blocking_actions_df = self.get_all_blocking_actions()
        if all_blocking_actions_df.empty:
            return set()
    
        # Faz o merge para obter os IDs dos incidentes
        merged_df = pd.merge(
            unit_actions_df,
            all_blocking_actions_df[['id', 'id_incidente']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        )
        
        # Remove valores nulos e garante que estamos trabalhando com strings
        merged_df = merged_df.dropna(subset=['id_incidente'])
        merged_df['id_incidente'] = merged_df['id_incidente'].astype(str)
        
        # Retorna o conjunto de IDs únicos de incidentes cobertos
        covered_ids = set(merged_df['id_incidente'].unique())
        
        return covered_ids

    def get_globally_pending_incidents(self, all_active_units: list[str], all_incidents_df: pd.DataFrame) -> pd.DataFrame:
        """
        Retorna um DataFrame de incidentes que ainda não foram abrangidos por TODAS
        as unidades operacionais ativas.
        """
        action_plan_df = self.get_all_action_plans()
        blocking_actions_df = self.get_all_blocking_actions()

        if all_incidents_df.empty or not all_active_units or action_plan_df.empty:
            return all_incidents_df

        if 'id_acao_bloqueio' not in action_plan_df.columns or 'id' not in blocking_actions_df.columns:
            logger.error("Colunas essenciais para merge não encontradas.")
            return all_incidents_df

        merged_df = pd.merge(
            action_plan_df,
            blocking_actions_df[['id', 'id_incidente']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        )
        
        merged_df.dropna(subset=['id_incidente'], inplace=True)

        coverage_by_incident = merged_df.groupby(merged_df['id_incidente'].astype(str))['unidade_operacional'].unique().apply(set)
        required_units_set = set(all_active_units)

        fully_covered_ids = {
            incident_id for incident_id, covered_units in coverage_by_incident.items()
            if required_units_set.issubset(covered_units)
        }
        
        pending_incidents_df = all_incidents_df[~all_incidents_df['id'].astype(str).isin(fully_covered_ids)]
        
        return pending_incidents_df
