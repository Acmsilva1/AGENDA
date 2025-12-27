import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time
import time as t 

# --- CONFIGURAÇÕES DO PROJETO ---

# ID da Planilha no seu Google Drive
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- CONFIGURAÇÃO DA GOVERNANÇA (Conexão Segura e Resiliente) ---

@st.cache_resource
def conectar_sheets():
    """Tenta conectar ao Google Sheets usando Streamlit Secrets com lógica de Retentativa."""
    MAX_RETRIES = 3
    
    # Inicia a lógica de retry
    for attempt in range(MAX_RETRIES):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gspread"])
            
            spreadsheet = gc.open_by_key(PLANILHA_ID)
            sheet = spreadsheet.worksheet(ABA_NOME)
            
            st.sidebar.success("✅ Conexão com Google Sheets estabelecida.")
            return sheet
        
        except Exception as e:
            # Se não for a última tentativa, espera e tenta novamente
            if attempt < MAX_RETRIES - 1:
                # Exponential Backoff
                wait_time = 2 ** attempt
                st.sidebar.warning(f"⚠️ Falha de conexão momentânea (Tentativa {attempt + 1}/{MAX_RETRIES}). Retentando em {wait_time}s...")
                t.sleep(wait_time) 
            else:
                # Última tentativa falhou, registra o erro fatal
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Verifique as permissões. Erro: {e}")
                return None
    return None


# --- FUNÇÕES CORE DO CRUD (Mantidas as mensagens de sucesso) ---

def carregar_eventos(sheet):
    """Lê todos os registros (ignorando o cabeçalho) e retorna como DataFrame."""
    if sheet is None: return pd.DataFrame()
    try:
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        return pd.DataFrame()

def adicionar_evento(sheet, dados_do_form):
    nova_linha = [dados_do_form.get('id_evento'), dados_do_form.get('titulo'), dados_do_form.get('descricao'), dados_do_form.get('data_evento'), dados_do_form.get('hora_evento'), dados_do_form.get('local'), dados_do_form.get('prioridade'), dados_do_form.get('status')]
    sheet.append_row(nova_linha)
    st.success("🎉 Evento criado. Mais um compromisso para a sua vida. **TROQUE DE ABA ou atualize a página para ver a lista.**")

def atualizar_evento(sheet, id_evento, novos_dados):
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row 
        valores_atualizados = [novos_dados['id_evento'], novos_dados['titulo'], novos_dados['descricao'], novos_dados['data_evento'], novos_dados['hora_evento'], novos_dados['local'], novos_dados['prioridade'], novos_dados['status']]
        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Evento {id_evento[:8]}... atualizado com sucesso. Foco nos detalhes. **TROQUE DE ABA ou atualize a página para ver a lista.**")
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Algum erro na matriz.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

def deletar_evento(sheet, id_evento):
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row
        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento[:8]}... deletado. Férias merecidas para esse compromisso. **TROQUE DE ABA ou atualize a página para ver a lista.**")
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Impossível apagar algo que não existe.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) ---

# Configuração de estado para controlar qual evento está sendo editado
if 'evento_em_edicao' not in st.session_state:
    st.session_state.evento_em_edicao = None

st.set_page_config(layout="wide")
st.title("🗓️ AGENDA DE EVENTOS")

sheet = conectar_sheets()

if sheet is None:
    st.stop()


tab_criar, tab_visualizar_editar = st.tabs(["➕ Criar Evento", "👁️ Visualizar e Gerenciar"])


# === ABA CRIAR ===
with tab_criar:
    st.header("REGISTRAR NOVO EVENTO")
    
    with st.form("form_novo_evento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            titulo = st.text_input("TÍTULO DO EVENTO", max_chars=100)
            local = st.text_input("Local ou Link da Reunião:")
            data = st.date_input("Data:", date.today(), format="DD/MM/YYYY") 
        
        with col2:
            prioridade = st.selectbox("Prioridade:", ["Média", "Alta", "Baixa"])
            hora = st.time_input("Hora:", time(9, 0)) 
            status_inicial = st.selectbox("Status Inicial:", ['Pendente', 'Rascunho'])
        
        descricao = st.text_area("Descrição Detalhada:")
        
        submit_button = st.form_submit_button("Salvar Novo Evento")

        if submit_button:
            if titulo and data: 
                dados_para_sheet = {
                    'id_evento': str(uuid.uuid4()),
                    'titulo': titulo,
                    'descricao': descricao,
                    'data_evento': data.strftime('%Y-%m-%d'), 
                    'hora_evento': hora.strftime('%H:%M'),
                    'local': local,
                    'prioridade': prioridade,
                    'status': status_inicial
                }
                adicionar_evento(sheet, dados_para_sheet)
                conectar_sheets.clear() 
            else:
                st.warning("O Título e a Data são obrigatórios. Não complique.")


# === ABA VISUALIZAR E GERENCIAR (R, U, D) - REVISADA ===
with tab_visualizar_editar:
    
    st.info("Para atualizar a lista após uma alteração, mude para a aba 'Criar Evento' e volte para cá (ou use F5).")
    st.header("MEUS EVENTOS")
    
    df_eventos = carregar_eventos(sheet) 
    
    if df_eventos.empty:
        st.info("SEM REGISTROS")
    else:
        
        # 1. Configurar o layout da tabela e botões
        df_display = df_eventos.copy()
        
        # Converte e formata as colunas para exibição
        df_display['Data'] = pd.to_datetime(df_display['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_display['Hora'] = df_display['hora_evento']

        df_display.rename(columns={
            'titulo': 'Título', 
            'local': 'Local',
            'prioridade': 'Prioridade',
            'status': 'Status'
        }, inplace=True)
        
        # Seleciona as colunas a serem exibidas na tabela principal
        cols_para_exibir = ['Título', 'Data', 'Hora', 'Local', 'Prioridade', 'Status', 'id_evento']
        df_tabela = df_display[cols_para_exibir].sort_values(by='Data', ascending=False)
        
        # Remove a coluna 'id_evento' da exibição, mas mantém ela no DF para uso
        df_tabela_sem_id = df_tabela.drop(columns=['id_evento'])

        # 2. Criar a tabela interativa (botões por linha)
        
        st.subheader("Registros e Ações")
        
        # Criar a grade para exibição
        df_registros = df_eventos.copy()
        df_registros['Data'] = pd.to_datetime(df_registros['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_registros = df_registros.sort_values(by='data_evento', ascending=False).reset_index(drop=True)

        for index, row in df_registros.iterrows():
            col_data, col_titulo, col_status, col_edit, col_delete = st.columns([1, 3, 1.5, 0.7, 0.7])
            
            with col_data: st.caption(f"**{row['Data']}**")
            with col_titulo: st.markdown(f"**{row['titulo']}**")
            with col_status: st.markdown(f"*{row['status']}*")
            
            # Botão EDITAR
            with col_edit:
                if st.button("📝 Editar", key=f"edit_{row['id_evento']}", type="secondary", use_container_width=True):
                    st.session_state.evento_em_edicao = row['id_evento']
                    # Rerun para que o formulário de edição apareça abaixo (Streamlit precisa de rerun para state changes)
                    st.experimental_rerun()
            
            # Botão EXCLUIR (com lógica de confirmação)
            with col_delete:
                if st.button("🗑️ Excluir", key=f"delete_{row['id_evento']}", type="primary", use_container_width=True):
                    # Define o ID para confirmação e abre o diálogo (usando state)
                    st.session_state.confirmar_exclusao_id = row['id_evento']
                    st.session_state.confirmar_exclusao_titulo = row['titulo']
                    st.session_state.confirmar_exclusao = True

            st.divider()

        # 3. Popup de Confirmação de Exclusão (Dialogo modal)
        if 'confirmar_exclusao' in st.session_state and st.session_state.confirmar_exclusao:
            
            # Cria um contêiner flutuante (não é um modal real, mas funciona como tal)
            with st.container(border=True):
                st.error(f"⚠️ **CONFIRMAR EXCLUSÃO PERMANENTE**")
                st.warning(f"Você tem certeza que deseja deletar o evento: **{st.session_state.confirmar_exclusao_titulo}**?")
                
                col_sim, col_nao = st.columns(2)
                
                with col_sim:
                    if st.button("✅ Sim, Excluir", key="final_delete_button", type="primary"):
                        if deletar_evento(sheet, st.session_state.confirmar_exclusao_id):
                            conectar_sheets.clear()
                            # Limpa os estados de confirmação e força um rerun para atualizar a lista
                            st.session_state.confirmar_exclusao = False
                            st.session_state.confirmar_exclusao_id = None
                            st.experimental_rerun()
                
                with col_nao:
                    if st.button("❌ Cancelar", key="cancel_delete_button"):
                        st.session_state.confirmar_exclusao = False
                        st.session_state.confirmar_exclusao_id = None
                        st.experimental_rerun()
        
        # 4. Formulário de Edição (Aparece se um evento foi clicado para edição)
        if st.session_state.evento_em_edicao:
            evento_dados = df_eventos[df_eventos['id_evento'] == st.session_state.evento_em_edicao].iloc[0]

            st.divider()
            st.subheader(f"🛠️ EDITAR: {evento_dados['titulo']}")
            
            with st.form("form_update_evento_direto"):
                
                col_t, col_l = st.columns(2)
                with col_t: novo_titulo = st.text_input("TÍTULO DO EVENTO", value=evento_dados['titulo'])
                with col_l: novo_local = st.text_input("Local ou Link da Reunião", value=evento_dados['local'])

                nova_descricao = st.text_area("Descrição Detalhada", value=evento_dados['descricao'])

                col_data_hora, col_prio_status = st.columns(2)

                with col_data_hora:
                    novo_data = st.date_input(
                        "Data", 
                        value=pd.to_datetime(evento_dados['data_evento']).date(),
                        format="DD/MM/YYYY"
                    )
                    novo_hora_str = evento_dados['hora_evento']
                    novo_hora = st.time_input("Hora", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:])))
                
                with col_prio_status:
                    opcoes_prioridade = ["Alta", "Média", "Baixa"]
                    novo_prioridade = st.selectbox("Prioridade", opcoes_prioridade, index=opcoes_prioridade.index(evento_dados['prioridade']))
                    
                    opcoes_status = ['Pendente', 'Concluído', 'Cancelado']
                    novo_status = st.selectbox("Status", opcoes_status, index=opcoes_status.index(evento_dados['status']))

                update_button = st.form_submit_button("✅ Salvar Alterações")
                cancel_button = st.form_submit_button("❌ Cancelar Edição")

                if update_button:
                    dados_atualizados = {
                        'id_evento': st.session_state.evento_em_edicao, 
                        'titulo': novo_titulo,
                        'descricao': nova_descricao,
                        'data_evento': novo_data.strftime('%Y-%m-%d'),
                        'hora_evento': novo_hora.strftime('%H:%M'),
                        'local': novo_local,
                        'prioridade': novo_prioridade,
                        'status': novo_status
                    }
                    if atualizar_evento(sheet, st.session_state.evento_em_edicao, dados_atualizados):
                        conectar_sheets.clear()
                        # Limpa o estado de edição e força a atualização
                        st.session_state.evento_em_edicao = None
                        st.experimental_rerun()
                
                if cancel_button:
                    st.session_state.evento_em_edicao = None
                    st.experimental_rerun()
