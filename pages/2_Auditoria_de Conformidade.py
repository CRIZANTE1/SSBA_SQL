import streamlit as st
import pandas as pd
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from analysis.nr_analyzer import NRAnalyzer

# Funções de inicialização para garantir que os managers estejam disponíveis
def init_managers():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    if 'nr_analyzer' not in st.session_state:
        st.session_state.nr_analyzer = NRAnalyzer()

st.set_page_config(
    page_title="Auditoria de Conformidade",
    page_icon="🔍",
    layout="wide"
)

init_managers()

employee_manager = st.session_state.employee_manager
docs_manager = st.session_state.docs_manager
nr_analyzer = st.session_state.nr_analyzer

st.title("🔍 Auditoria de Conformidade de Documentos")
st.markdown("Selecione um documento existente para realizar uma análise profunda contra a base de conhecimento de uma NR.")

# --- 1. Seleção da Empresa ---
if not employee_manager.companies_df.empty:
    df_companies = employee_manager.companies_df.astype({'id': 'str'})
    selected_company_id = st.selectbox(
        "Selecione a empresa para auditar",
        df_companies['id'].tolist(),
        format_func=lambda x: f"{df_companies[df_companies['id'] == x]['nome'].iloc[0]}",
        index=None,
        placeholder="Escolha uma empresa..."
    )

    if selected_company_id:
        # --- 2. Juntar todos os documentos disponíveis para seleção ---
        asos = employee_manager.aso_df[employee_manager.aso_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
        trainings = employee_manager.training_df[employee_manager.training_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
        company_docs = docs_manager.get_docs_by_company(selected_company_id)
        
        docs_list = []
        # Formata os documentos para o selectbox, incluindo a norma e o tipo
        if not trainings.empty:
            for _, row in trainings.iterrows():
                employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Funcionário Desconhecido"
                norma = employee_manager._padronizar_norma(row['norma'])
                docs_list.append({
                    "label": f"Treinamento: {norma} - {employee_name}",
                    "url": row['arquivo_id'],
                    "norma": norma,
                    "type": "Treinamento"
                })
        if not company_docs.empty:
             for _, row in company_docs.iterrows():
                doc_type = row['tipo_documento']
                norma_associada = "NR-01" if doc_type == "PGR" else ("NR-07" if doc_type == "PCMSO" else "NR-01") # Regra de associação
                docs_list.append({
                    "label": f"Doc. Empresa: {doc_type}",
                    "url": row['arquivo_id'],
                    "norma": norma_associada,
                    "type": doc_type
                })
        if not asos.empty:
            for _, row in asos.iterrows():
                employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Funcionário Desconhecido"
                docs_list.append({
                    "label": f"ASO: {row.get('tipo_aso', 'N/A')} - {employee_name}",
                    "url": row['arquivo_id'],
                    "norma": "NR-07", # ASO sempre se refere à NR-07
                    "type": "ASO"
                })

        # --- 3. Seleção do Documento ---
        selected_doc = st.selectbox(
            "Selecione o documento para análise",
            options=docs_list,
            format_func=lambda x: x['label'],
            index=None,
            placeholder="Escolha um documento..."
        )

        if selected_doc:
            norma_para_analise = selected_doc.get("norma")
            # --- 4. Botão de Análise (norma é deduzida) ---
            st.info(f"Documento selecionado: **{selected_doc['label']}**. Será analisado contra a **{norma_para_analise}**.")
            
            # Verifica se a norma selecionada tem uma planilha de RAG configurada
            if norma_para_analise in nr_analyzer.nr_sheets_map:
                if st.button(f"Analisar Conformidade com a {norma_para_analise}", type="primary"):
                    # Passa o dicionário completo do documento para a função de análise
                    resultado = nr_analyzer.analyze_document_compliance(selected_doc['url'], selected_doc)
                    st.session_state.audit_result = resultado
            else:
                st.warning(f"A análise para a {norma_para_analise} não está disponível. Nenhuma planilha de RAG foi configurada para esta norma em `analysis/nr_analyzer.py`.")

            if 'audit_result' in st.session_state:
                st.markdown("---")
                st.subheader("Resultado da Análise")
                st.markdown(st.session_state.audit_result)
                if st.button("Limpar Análise"):
                    del st.session_state.audit_result
                    st.rerun()

else:
    st.warning("Nenhuma empresa cadastrada. Adicione uma empresa na página principal primeiro.")
