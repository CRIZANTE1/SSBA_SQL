
import streamlit as st
import pandas as pd
from datetime import datetime, date
import random
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from analysis.nr_analyzer import NRAnalyzer
from auth.auth_utils import check_admin_permission
from gdrive.config import AUDIT_RESULTS_SHEET_NAME

def init_managers():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    if 'nr_analyzer' not in st.session_state:
        st.session_state.nr_analyzer = NRAnalyzer()

def style_status_table(df: pd.DataFrame):
    def highlight_status(val):
        color = ''
        val_lower = str(val).lower()
        if 'não conforme' in val_lower:
            color = 'background-color: #FFCDD2'
        elif 'conforme' in val_lower:
            color = 'background-color: #C8E6C9'
        return color
    
    if 'status' in df.columns:
        return df.style.map(highlight_status, subset=['status'])
    return df.style

def setup_audit_sheet():
    sheet_ops = st.session_state.employee_manager.sheet_ops
    data = sheet_ops.carregar_dados_aba(AUDIT_RESULTS_SHEET_NAME)
    
    columns = [
        "id_auditoria", "data_auditoria", "id_empresa", "id_documento_original", 
        "id_funcionario", "tipo_documento", "norma_auditada", 
        "item_verificacao", "status", "observacao"
    ]
    if not data:
        sheet_ops.criar_aba(AUDIT_RESULTS_SHEET_NAME, ["id"] + columns)
    elif data and 'id_auditoria' not in data[0]:
        st.warning(f"A coluna 'id_auditoria' não foi encontrada na aba {AUDIT_RESULTS_SHEET_NAME}.")

st.set_page_config(page_title="Auditoria de Conformidade", page_icon="🔍", layout="wide")

if check_admin_permission():
    init_managers()
    setup_audit_sheet()

    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    nr_analyzer = st.session_state.nr_analyzer

    st.title("🔍 Auditoria de Conformidade de Documentos")
    st.markdown("Selecione um documento para realizar uma análise profunda.")

    if not employee_manager.companies_df.empty:
        df_companies = employee_manager.companies_df.astype({'id': 'str'})
        selected_company_id = st.selectbox(
            "Selecione a empresa para auditar",
            df_companies['id'].tolist(),
            format_func=lambda x: f"{df_companies[df_companies['id'] == x]['nome'].iloc[0]}",
            index=None, placeholder="Escolha uma empresa..."
        )

        if selected_company_id:
            asos = employee_manager.aso_df[employee_manager.aso_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
            trainings = employee_manager.training_df[employee_manager.training_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
            company_docs = docs_manager.get_docs_by_company(selected_company_id)
            
            docs_list = []
            if not trainings.empty:
                for _, row in trainings.iterrows():
                    employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Func. Desconhecido"
                    norma = employee_manager._padronizar_norma(row['norma'])
                    docs_list.append({"label": f"Treinamento: {norma} - {employee_name}", "url": row['arquivo_id'], "norma": norma, "type": "Treinamento", "doc_id": row['id'], "employee_id": row['funcionario_id']})
            if not company_docs.empty:
                 for _, row in company_docs.iterrows():
                    doc_type = row['tipo_documento']; norma_associada = "NR-01" if doc_type == "PGR" else ("NR-07" if doc_type == "PCMSO" else "NR-01")
                    docs_list.append({"label": f"Doc. Empresa: {doc_type}", "url": row['arquivo_id'], "norma": norma_associada, "type": doc_type, "doc_id": row['id'], "employee_id": None})
            if not asos.empty:
                for _, row in asos.iterrows():
                    employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Func. Desconhecido"
                    docs_list.append({"label": f"ASO: {row.get('tipo_aso', 'N/A')} - {employee_name}", "url": row['arquivo_id'], "norma": "NR-07", "type": "ASO", "doc_id": row['id'], "employee_id": row['funcionario_id']})

            selected_doc = st.selectbox(
                "Selecione o documento para análise",
                options=docs_list, format_func=lambda x: x.get('label', 'Documento Inválido'),
                index=None, placeholder="Escolha um documento..."
            )

            if selected_doc:
                norma_para_analise = selected_doc.get("norma")
                st.info(f"Documento selecionado: **{selected_doc.get('label')}**. Será analisado contra a **{norma_para_analise}**.")
                
                if norma_para_analise in nr_analyzer.nr_sheets_map:
                    if st.button(f"Analisar Conformidade com a {norma_para_analise}", type="primary"):
                        with st.spinner("Realizando análise... Isso pode levar alguns instantes."):
                            resultado_df = nr_analyzer.analyze_document_compliance(selected_doc['url'], selected_doc)
                        st.session_state.audit_result_df = resultado_df
                        if 'saved_audit' in st.session_state:
                            del st.session_state.saved_audit
                else:
                    st.warning(f"A análise para a {norma_para_analise} não está disponível.")

                if 'audit_result_df' in st.session_state and isinstance(st.session_state.audit_result_df, pd.DataFrame):
                    st.markdown("---")
                    st.subheader("Resultado da Análise de Conformidade")
                    
                    audit_df = st.session_state.audit_result_df
                    
                    st.dataframe(
                        style_status_table(audit_df),
                        column_config={
                            "item_verificacao": "Item de Verificação",
                            "status": "Status",
                            "observacao": "Observação da IA",
                        },
                        use_container_width=True, 
                        hide_index=True
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Salvar Resultado da Auditoria", disabled=st.session_state.get('saved_audit', False)):
                            with st.spinner("Salvando auditoria na planilha..."):
                                saved_count = 0
                                data_auditoria_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                audit_run_id = random.randint(10000, 99999)

                                for _, row in audit_df.iterrows():
                                    new_audit_row = [
                                        audit_run_id,
                                        data_auditoria_atual,
                                        selected_company_id,
                                        selected_doc.get('doc_id', 'N/A'),
                                        selected_doc.get('employee_id', 'N/A'),
                                        selected_doc.get('type', 'N/A'),
                                        norma_para_analise,
                                        row.get('item_verificacao', ''),
                                        row.get('status', ''),
                                        row.get('observacao', '')
                                    ]
                                    save_id = employee_manager.sheet_ops.adc_dados_aba(AUDIT_RESULTS_SHEET_NAME, new_audit_row)
                                    if save_id:
                                        saved_count += 1
                                
                                if saved_count == len(audit_df):
                                    st.success(f"{saved_count} linha(s) de auditoria foram salvas com sucesso sob o ID de análise: {audit_run_id}!")
                                    st.session_state.saved_audit = True
                                    st.rerun()
                                else:
                                    st.error("Ocorreu um erro ao tentar salvar todos os itens da auditoria.")
                    
                    with col2:
                        if st.button("Limpar Análise da Tela"):
                            del st.session_state.audit_result_df
                            if 'saved_audit' in st.session_state:
                                del st.session_state.saved_audit
                            st.rerun()
    else:
        st.warning("Nenhuma empresa cadastrada.")