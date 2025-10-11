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

    def answer_question(self, files, question, task_type='extraction'):
        start_time = time.time()
        
        model_to_use = self.extraction_model if task_type == 'extraction' else self.audit_model
        
        if not model_to_use:
            st.error(f"O modelo de IA para a tarefa '{task_type}' não está disponível.")
            return None, 0

        try:
            raw_answer_text = self._generate_response(model_to_use, files, question)
            
            if not raw_answer_text:
                st.warning("A IA não retornou resposta.")
                return None, 0
            
            # <<< MELHORAR PARSING >>>
            json_text = raw_answer_text.strip()
            
            # Remove markdown code blocks
            if json_text.startswith('```'):
                json_text = '\n'.join(json_text.split('\n')[1:-1])
            
            # Tenta encontrar JSON válido dentro do texto
            import re
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
            
            answer_dict = json.loads(json_text)
            
            # <<< VALIDAÇÃO DE SCHEMA >>>
            required_keys = ['evento_resumo', 'data_evento', 'o_que_aconteceu', 
                            'por_que_aconteceu', 'recomendacoes']
            missing_keys = [k for k in required_keys if k not in answer_dict]
            
            if missing_keys:
                st.error(f"⚠️ IA retornou JSON incompleto. Faltam: {', '.join(missing_keys)}")
                st.code(raw_answer_text)
                return None, 0
            
            return answer_dict, time.time() - start_time
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Erro ao processar resposta da IA: {e}")
            with st.expander("🔍 Ver resposta bruta da IA"):
                st.code(raw_answer_text)
            return None, 0
        except Exception as e:
            st.error(f"❌ Erro inesperado: {e}")
            logger.exception("Erro no answer_question")
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
   






   





   




   




