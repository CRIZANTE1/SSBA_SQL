import streamlit as st
import time
from AI.api_load import load_models
import json # Importar para tratar o JSON

class PDFQA:
    def __init__(self):
        """
        Inicializa a classe carregando os dois modelos de IA (extração e auditoria)
        usando a função load_models().
        """
        self.extraction_model, self.audit_model = load_models()

    def answer_question(self, files, question, task_type='extraction'): # <<< MUDANÇA AQUI
        """
        Função principal para responder a uma pergunta, selecionando o modelo apropriado.
        Atua como um "roteador" para o modelo de IA correto.
        
        Args:
            files (list): Lista de caminhos ou objetos de arquivo (PDFs, imagens, etc.).
            question (str): A pergunta ou prompt.
            task_type (str): 'extraction' (padrão) ou 'audit'.
        
        Returns:
            tuple: (response_dict, duration) ou (None, 0) em caso de erro.
        """
        start_time = time.time()
        
        model_to_use = self.extraction_model
        if task_type == 'audit':
            model_to_use = self.audit_model
        
        if not model_to_use:
            st.error(f"O modelo de IA para a tarefa '{task_type}' não está disponível. Verifique as chaves da API nos secrets.")
            return None, 0

        try:
            # O método _generate_response agora retorna o texto bruto
            raw_answer_text = self._generate_response(model_to_use, files, question) # <<< MUDANÇA AQUI
            
            if raw_answer_text:
                # Limpa o texto da resposta para extrair apenas o JSON
                json_text = raw_answer_text.strip().replace('```json', '').replace('```', '').strip()
                # Converte o texto JSON em um dicionário Python
                answer_dict = json.loads(json_text)
                return answer_dict, time.time() - start_time
            else:
                st.warning("Não foi possível obter uma resposta do modelo de IA.")
                return None, 0
        except json.JSONDecodeError:
            st.error("Erro Crítico: A IA retornou um formato que não é um JSON válido.")
            st.code(raw_answer_text) # Mostra ao usuário o que a IA retornou
            return None, 0
        except Exception as e:
            st.error(f"Erro inesperado ao processar a pergunta: {e}")
            return None, 0

    def _generate_response(self, model, files, question): # <<< MUDANÇA AQUI
        """
        Função interna que prepara e envia a requisição para um modelo Gemini específico.
        """
        try:
            inputs = []
            
            for file_obj in files: # <<< MUDANÇA AQUI
                mime_type = file_obj.type
                file_bytes = file_obj.getvalue()
                
                part = {"mime_type": mime_type, "data": file_bytes}
                inputs.append(part)
            
            # Adiciona a pergunta como texto
            inputs.append({"text": question})
            
            # Gera a resposta
            response = model.generate_content(inputs)
            
            return response.text
            
        except Exception as e:
            st.error(f"Erro na comunicação com a API Gemini: {str(e)}")
            return None
   






   





   




   




