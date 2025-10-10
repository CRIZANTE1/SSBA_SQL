import streamlit as st
import pandas as pd
import logging
from datetime import date
from database.supabase_operations import SupabaseOperations

logger = logging.getLogger('abrangencia_app.incident_manager')

@st.cache_resource
def get_incident_manager():
    return IncidentManager()


class IncidentManager:
    def __init__(self):
        self.db = SupabaseOperations()
        if not self.db.client:
            raise ConnectionError("Falha na conexão com o Supabase.")

    def get_all_incidents(self) -> pd.DataFrame:
        """Retorna todos os incidentes"""
        return self.db.get_table_data("incidentes")

    def add_incident(self, numero_alerta: str, evento_resumo: str, data_evento: date, 
                     o_que_aconteceu: str, por_que_aconteceu: str, foto_url: str, 
                     anexos_url: str) -> int | None:
        """Adiciona um novo incidente com validação"""
        
        # Validar inputs
        if not all([numero_alerta, evento_resumo, data_evento]):
            logger.error("Campos obrigatórios ausentes")
            return None
        
        logger.info(f"Adicionando novo incidente: {numero_alerta}")
        
        incident_data = {
            "numero_alerta": str(numero_alerta).strip(),
            "evento_resumo": str(evento_resumo).strip(),
            "data_evento": data_evento,
            "o_que_aconteceu": str(o_que_aconteceu).strip(),
            "por_que_aconteceu": str(por_que_aconteceu).strip(),
            "foto_url": str(foto_url).strip() if foto_url else "",
            "anexos_url": str(anexos_url).strip() if anexos_url else ""
        }
        
        result = self.db.insert_row("incidentes", incident_data)
        return result['id'] if result else None

    def get_all_blocking_actions(self) -> pd.DataFrame:
        """Retorna todas as ações de bloqueio"""
        return self.db.get_table_data("acoes_bloqueio")

    def get_blocking_actions_by_incident(self, incident_id: str) -> pd.DataFrame:
        """Retorna ações de bloqueio de um incidente específico"""
        return self.db.get_by_field("acoes_bloqueio", "id_incidente", incident_id)

    def add_blocking_actions_batch(self, incident_id: int, descriptions: list[str]) -> bool:
        """Adiciona múltiplas ações de bloqueio"""
        if not descriptions:
            return True
        
        actions_data = [
            {"id_incidente": incident_id, "descricao_acao": desc}
            for desc in descriptions
        ]
        
        return self.db.insert_batch("acoes_bloqueio", actions_data)

    def get_all_action_plans(self) -> pd.DataFrame:
        """Retorna todos os planos de ação"""
        return self.db.get_table_data("plano_de_acao_abrangencia")

    def add_abrangencia_action(self, id_acao_bloqueio: int, unidade_operacional: str, 
                              responsavel_email: str, co_responsavel_email: str, 
                              prazo_inicial: date, status: str) -> int | None:
        """Adiciona uma ação de abrangência"""
        action_data = {
            "id_acao_bloqueio": id_acao_bloqueio,
            "unidade_operacional": unidade_operacional,
            "responsavel_email": responsavel_email,
            "co_responsavel_email": co_responsavel_email or "",
            # Envia objeto date diretamente; driver cuida da conversão para DATE
            "prazo_inicial": prazo_inicial,
            "status": status,
            "data_conclusao": None,
            "url_evidencia": "",
            "detalhes_conclusao": ""
        }
        
        result = self.db.insert_row("plano_de_acao_abrangencia", action_data)
        return result['id'] if result else None

    def update_abrangencia_action(self, action_id: int, updates: dict) -> bool:
        """Atualiza uma ação de abrangência"""
        logger.info(f"Atualizando ação {action_id}")
        
        # Converte datas para formato ISO se necessário
        if 'prazo_inicial' in updates and isinstance(updates['prazo_inicial'], str):
            try:
                from datetime import datetime
                dt = datetime.strptime(updates['prazo_inicial'], "%d/%m/%Y")
                updates['prazo_inicial'] = dt.strftime('%Y-%m-%d')
            except:
                pass
        
        return self.db.update_row("plano_de_acao_abrangencia", action_id, updates)

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
