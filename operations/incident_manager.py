import streamlit as st
import pandas as pd
import logging
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID # <-- Importa o ID da planilha principal

logger = logging.getLogger('abrangencia_app.incident_manager')

class IncidentManager:
    """
    Gerencia todas as operações relacionadas a incidentes e planos de ação
    para a arquitetura single-tenant.
    """
    def __init__(self):
        """
        Inicializa o gerenciador para a planilha principal definida no config.
        """
        if not SPREADSHEET_ID:
            st.error("ID da Planilha Principal não configurado em gdrive/config.py. A aplicação não pode funcionar.")
            # Define DFs vazios para evitar erros de atributo
            self._incidents_df = pd.DataFrame()
            self._blocking_actions_df = pd.DataFrame()
            self._action_plan_df = pd.DataFrame()
            return

        self.sheet_ops = SheetOperations() # Não precisa mais de argumento
        self._incidents_df = None
        self._blocking_actions_df = None
        self._action_plan_df = None

    @property
    def incidents_df(self) -> pd.DataFrame:
        """Carrega o DataFrame de incidentes sob demanda."""
        if self._incidents_df is None:
            self._load_incidents_data()
        return self._incidents_df

    @property
    def blocking_actions_df(self) -> pd.DataFrame:
        """Carrega o DataFrame de ações de bloqueio sob demanda."""
        if self._blocking_actions_df is None:
            self._load_blocking_actions_data()
        return self._blocking_actions_df

    def _load_incidents_data(self):
        """Carrega e cacheia os dados da aba 'incidentes'."""
        logger.info("Carregando dados de incidentes...")
        self._incidents_df = self.sheet_ops.get_df_from_worksheet("incidentes")

    def _load_blocking_actions_data(self):
        """Carrega e cacheia os dados da aba 'acoes_bloqueio'."""
        logger.info("Carregando dados de ações de bloqueio...")
        self._blocking_actions_df = self.sheet_ops.get_df_from_worksheet("acoes_bloqueio")

    def get_all_incidents(self) -> pd.DataFrame:
        """Retorna todos os incidentes como um DataFrame."""
        return self.incidents_df

    def get_incident_by_id(self, incident_id: str) -> pd.Series | None:
        """Busca um incidente específico pelo seu ID."""
        if self.incidents_df.empty:
            return None
        
        incident = self.incidents_df[self.incidents_df['id'] == str(incident_id)]
        return incident.iloc[0] if not incident.empty else None

    def add_incident(self, numero_alerta: str, evento_resumo: str, data_evento, o_que_aconteceu: str, por_que_aconteceu: str, foto_url: str, anexos_url: str) -> int | None:
        """
        Adiciona um novo registro de incidente na aba 'incidentes'.
        """
        logger.info(f"Adicionando novo incidente: {numero_alerta}")
        data_evento_str = data_evento.strftime('%d/%m/%Y') if hasattr(data_evento, 'strftime') else str(data_evento)

        new_incident_data = [
            numero_alerta, evento_resumo, data_evento_str,
            o_que_aconteceu, por_que_aconteceu, foto_url, anexos_url
        ]
        
        new_id = self.sheet_ops.adc_dados_aba("incidentes", new_incident_data)
        if new_id:
            self._incidents_df = None # Invalida o cache
            logger.info(f"Incidente {new_id} adicionado com sucesso.")
        else:
            logger.error("Falha ao adicionar incidente na planilha.")
        return new_id

    def get_blocking_actions_by_incident(self, incident_id: str) -> pd.DataFrame:
        """Retorna as ações de bloqueio para um ID de incidente específico."""
        if self.blocking_actions_df.empty:
            return pd.DataFrame()
        
        return self.blocking_actions_df[self.blocking_actions_df['id_incidente'] == str(incident_id)]

    def add_abrangencia_action(self, id_acao_bloqueio: str, unidade_operacional: str, responsavel_email: str, prazo_inicial, status: str) -> int | None:
        """
        Adiciona um novo registro de plano de ação de abrangência.
        """
        logger.info(f"Adicionando ação de abrangência para a ação de bloqueio {id_acao_bloqueio} na unidade {unidade_operacional}.")
        prazo_str = prazo_inicial.strftime('%d/%m/%Y') if hasattr(prazo_inicial, 'strftime') else str(prazo_inicial)

        new_action_data = [
            id_acao_bloqueio, unidade_operacional, responsavel_email, prazo_str, status
        ]

        new_id = self.sheet_ops.adc_dados_aba("plano_de_acao_abrangencia", new_action_data)
        if new_id:
            logger.info(f"Ação de abrangência {new_id} adicionada com sucesso.")
        else:
            logger.error("Falha ao adicionar ação de abrangência na planilha.")
        return new_id

    def update_abrangencia_action(self, action_id: str, updates: dict) -> bool:
        """
        Atualiza uma linha específica na aba 'plano_de_acao_abrangencia'.
        """
        logger.info(f"Atualizando ação de abrangência ID {action_id} com os dados: {updates}")
        success = self.sheet_ops.update_row_by_id("plano_de_acao_abrangencia", action_id, updates)
        if success:
            logger.info(f"Ação {action_id} atualizada com sucesso.")
        else:
            logger.error(f"Falha ao atualizar a ação {action_id}.")
        return success

    def add_blocking_actions_batch(self, incident_id: str, descriptions: list[str]) -> bool:
        """
        Adiciona múltiplas ações de bloqueio (recomendações) em lote para um incidente.
        """
        if not descriptions:
            return True

        logger.info(f"Adicionando {len(descriptions)} ações de bloqueio em lote para o incidente ID {incident_id}.")
        rows_to_add = [[str(incident_id), desc] for desc in descriptions]
        
        success = self.sheet_ops.adc_dados_aba_em_lote("acoes_bloqueio", rows_to_add)
        if success:
            self._blocking_actions_df = None # Invalida o cache
            logger.info("Ações de bloqueio em lote adicionadas com sucesso.")
        else:
            logger.error(f"Falha ao adicionar ações de bloqueio para o incidente {incident_id}.")
        return success
