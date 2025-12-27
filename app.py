import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time
import time as t 
from streamlit_autorefresh import st_autorefresh 

# --- CONFIGURAÇÕES DO PROJETO ---

# ID da Planilha no seu Google Drive
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_AGENDA = "AGENDA"
ABA_ALARMES = "ALARMES_RECORRENTES" # Nova aba

# --- CONFIGURAÇÃO DA GOVERNANÇA (Conexão Segura e Resiliente) ---

@st.cache_resource
def conectar_sheets():
    """Tenta conectar ao Google Sheets usando Streamlit Secrets com lógica de Retentativa."""
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gspread"])
            
            spreadsheet = gc.open_by_key(PLANILHA_ID)
            
            # Garante que ambas as sheets sejam acessíveis
            sheet_agenda = spreadsheet.worksheet(ABA_AGENDA)
            sheet_alarmes = spreadsheet.worksheet(ABA_ALARMES)

            st.sidebar.success("✅ Conexão com Google Sheets estabelecida.")
            return spreadsheet
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                st.sidebar.warning(f"⚠️ Falha de conexão momentânea (Tentativa {attempt + 1}/{MAX_RETRIES}). Retentando em {wait_time}s...")
                t.sleep(wait_time) 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Erro: {e}")
                return None
    return None

spreadsheet = conectar_sheets()

if spreadsheet is None:
    st.stop()
    
sheet_agenda = spreadsheet.worksheet(ABA_AGENDA)
sheet_alarmes = spreadsheet.worksheet(ABA_ALARMES)


# --- FUNÇÕES CORE DO CRUD (AGENDA) ---

def carregar_eventos(sheet):
    """Lê todos os registros da Agenda."""
    try:
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        return pd.DataFrame()

def adicionar_evento(sheet, dados_do_form):
    """Insere uma nova linha de evento na Agenda."""
    nova_linha = [dados_do_form.get(h, '') for h in sheet.row_values(1)]
    
    # Mapeia valores para a ordem correta da planilha
    colunas_agenda = ['id_evento', 'titulo', 'descricao', 'data_evento', 'hora_evento', 'local', 'prioridade', 'status']
    valores_para_sheet = [dados_do_form.get(col, '') for col in colunas_agenda]
    
    sheet.append_row(valores_para_sheet)
    st.success("🎉 Evento criado. **A lista será atualizada automaticamente em 10 segundos.**") 
    conectar_sheets.clear()

def atualizar_evento(sheet, id_evento, novos_dados):
    """Atualiza um evento existente na Agenda."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row 
        
        colunas_agenda = ['id_evento', 'titulo', 'descricao', 'data_evento', 'hora_evento', 'local', 'prioridade', 'status']
        valores_atualizados = [novos_dados.get(col, '') for col in colunas_agenda]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Evento {id_evento[:8]}... atualizado com sucesso. **A lista será atualizada automaticamente em 10 segundos.**") 
        conectar_sheets.clear()
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

def deletar_evento(sheet, id_evento):
    """Remove um evento da Agenda."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento[:8]}... deletado. **A lista será atualizada automaticamente em 10 segundos.**") 
        conectar_sheets.clear()
        return True
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# --- FUNÇÕES CORE DO CRUD (ALARMES RECORRENTES) ---

def carregar_alarmes(sheet):
    """Lê todos os registros de Alarmes Recorrentes."""
    try:
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        return pd.DataFrame()

def adicionar_alarme(sheet, dados_do_form):
    """Insere um novo alarme na planilha de Alarmes."""
    
    colunas_alarmes = ['id_alarme', 'TITULO', 'HORA_ALARME', 'DIAS_SEMANA', 'ATIVO']
    valores_para_sheet = [dados_do_form.get(col, '') for col in colunas_alarmes]
    
    sheet.append_row(valores_para_sheet)
    st.success("🔔 Novo Alarme Recorrente criado. ") 
    conectar_sheets.clear()

def atualizar_alarme(sheet, id_alarme, novos_dados):
    """Atualiza um alarme recorrente existente."""
    try:
        cell = sheet.find(id_alarme)
        linha_index = cell.row 
        
        colunas_alarmes = ['id_alarme', 'TITULO', 'HORA_ALARME', 'DIAS_SEMANA', 'ATIVO']
        valores_atualizados = [novos_dados.get(col, '') for col in colunas_alarmes]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Alarme {id_alarme[:8]}... atualizado com sucesso.") 
        conectar_sheets.clear()
        return True
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o alarme: {e}")
        return False

def deletar_alarme(sheet, id_alarme):
    """Remove um alarme recorrente."""
    try:
        cell = sheet.find(id_alarme)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Alarme {id_alarme[:8]}... deletado.") 
        conectar_sheets.clear()
        return True
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o alarme: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) ---

st.set_page_config(layout="wide")
st.title("🗓️ GESTÃO DE GOVERNANÇA E ROTINA")

# --- CONFIGURAÇÃO DE ABAS ---
tab_criar, tab_visualizar_agenda, tab_alarmes_recorrentes = st.tabs([
    "➕ Criar Evento (Agenda)", 
    "👁️ Visualizar Agenda (CRUD)",
    "⏰ Alarmes Recorrentes (CRUD)" # 📌 NOVA ABA
])

st_autorefresh(interval=10000, key="data_refresh_key")

# ==============================================================================
# === ABA 1: CRIAR EVENTO (AGENDA) ===
# ==============================================================================
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
            # 📌 STATUS AJUSTADO: Apenas PENDENTE e CONCLUÍDO
            status_inicial = st.selectbox("Status Inicial:", ['Pendente', 'Concluído'])
        
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
                adicionar_evento(sheet_agenda, dados_para_sheet)
                
            else:
                st.warning("O Título e a Data são obrigatórios. Não complique.")

# ==============================================================================
# === ABA 2: VISUALIZAR E GERENCIAR (AGENDA CRUD) ===
# ==============================================================================
with tab_visualizar_agenda:
    st.info("🔄 **ATUALIZAÇÃO AUTOMÁTICA** (A cada 10 segundos)")
    st.header("MINHA AGENDA DE GOVERNANÇA")
    
    df_eventos = carregar_eventos(sheet_agenda) 
    
    if df_eventos.empty:
        st.info("SEM REGISTROS NA AGENDA")
    else:
        
        df_display = df_eventos.copy()
        if 'data_evento' in df_display.columns:
            df_display['data_evento'] = pd.to_datetime(df_display['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
        
        df_display.rename(columns={
            'id_evento': 'ID', 'titulo': 'Título', 'data_evento': 'Data',
            'hora_evento': 'Hora', 'descricao': 'Descrição', 'local': 'Local', 
            'prioridade': 'Prioridade', 'status': 'Status'
        }, inplace=True)
        
        st.dataframe(df_display.sort_values(by='Data', ascending=False), use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🛠️ Edição e Exclusão")

        if not df_eventos.empty:
            eventos_atuais = df_eventos['id_evento'].tolist()
            
            def formatar_selecao(id_val):
                titulo = df_eventos[df_eventos['id_evento'] == id_val]['titulo'].iloc[0]
                return f"{titulo} ({id_val[:4]}...)"

            evento_selecionado_id = st.selectbox(
                "Selecione o Evento para Ação:",
                options=eventos_atuais,
                index=0 if eventos_atuais else None,
                format_func=formatar_selecao
            )
        
        if evento_selecionado_id:
            evento_dados = df_eventos[df_eventos['id_evento'] == evento_selecionado_id].iloc[0]

            col_u, col_d = st.columns([3, 1])

            with col_u:
                st.markdown("##### Atualizar Evento Selecionado")
                with st.form("form_update_evento"):
                    novo_titulo = st.text_input("TÍTULO DO EVENTO", value=evento_dados['titulo'])
                    nova_descricao = st.text_area("Descrição", value=evento_dados['descricao'])

                    col_data_hora, col_local_prioridade = st.columns(2)

                    with col_data_hora:
                        novo_data = st.date_input(
                            "Data", 
                            value=pd.to_datetime(evento_dados['data_evento']).date(),
                            format="DD/MM/YYYY"
                        )
                        novo_hora_str = evento_dados['hora_evento']
                        novo_hora = st.time_input("Hora", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:])))
                    
                    with col_local_prioridade:
                        novo_local = st.text_input("Local", value=evento_dados['local'])
                        opcoes_prioridade = ["Alta", "Média", "Baixa"]
                        novo_prioridade = st.selectbox("Prioridade", opcoes_prioridade, index=opcoes_prioridade.index(evento_dados['prioridade']))
                        
                        # 📌 STATUS AJUSTADO: Apenas PENDENTE e CONCLUÍDO
                        opcoes_status = ['Pendente', 'Concluído']
                        novo_status = st.selectbox("Status", opcoes_status, index=opcoes_status.index(evento_dados['status']) if evento_dados['status'] in opcoes_status else 0)

                    update_button = st.form_submit_button("Salvar Atualizações (Update)")

                    if update_button:
                        dados_atualizados = {
                            'id_evento': evento_selecionado_id, 'titulo': novo_titulo,
                            'descricao': nova_descricao, 'data_evento': novo_data.strftime('%Y-%m-%d'),
                            'hora_evento': novo_hora.strftime('%H:%M'), 'local': novo_local,
                            'prioridade': novo_prioridade, 'status': novo_status
                        }
                        atualizar_evento(sheet_agenda, evento_selecionado_id, dados_atualizados)
                            
            
            with col_d:
                st.markdown("##### Excluir Evento")
                st.warning(f"Excluindo: **{evento_dados['titulo']}**")
                
                if st.button("🔴 EXCLUIR EVENTO (Delete)", type="primary"):
                    deletar_evento(sheet_agenda, evento_selecionado_id)


# ==============================================================================
# === ABA 3: ALARMES RECORRENTES (CRUD) ===
# ==============================================================================

dias_semana_full = ['SEGUNDA', 'TERÇA', 'QUARTA', 'QUINTA', 'SEXTA', 'SÁBADO', 'DOMINGO']
dias_semana_map = {d: d[:2].upper() for d in dias_semana_full}


with tab_alarmes_recorrentes:
    st.header("ALARME DE ROTINA (Treino, Medicamento, etc.)")
    
    st.markdown("---")
    st.subheader("➕ Criar Novo Alarme")
    
    with st.form("form_novo_alarme", clear_on_submit=True):
        
        titulo_alarme = st.text_input("Título do Alarme (Ex: Tomar Vitamina)", max_chars=100)
        
        col_c1, col_c2 = st.columns([1, 2])
        
        with col_c1:
            hora_alarme = st.time_input("Hora do Alarme", value=time(10, 0))
            status_alarme = st.selectbox("Status", ['SIM', 'NÃO'], index=0)
            
        with col_c2:
            dias_selecionados = st.multiselect(
                "Dias da Semana para Recorrência (Deixe vazio para TODOS os dias):",
                options=dias_semana_full
            )
        
        submit_alarme = st.form_submit_button("Salvar Novo Alarme")
        
        if submit_alarme:
            if titulo_alarme:
                # Mapeia dias selecionados para abreviações (SE, TE, QA, etc.)
                dias_formatados = [dias_semana_map[d] for d in dias_selecionados]
                dias_string = "TODOS" if not dias_formatados else ", ".join(dias_formatados)
                
                novo_alarme = {
                    'id_alarme': str(uuid.uuid4()),
                    'TITULO': titulo_alarme,
                    'HORA_ALARME': hora_alarme.strftime('%H:%M'),
                    'DIAS_SEMANA': dias_string,
                    'ATIVO': status_alarme
                }
                adicionar_alarme(sheet_alarmes, novo_alarme)
            else:
                st.warning("O Título do Alarme é obrigatório.")

    
    st.markdown("---")
    st.subheader("👁️ Gerenciar Alarmes Existentes")
    
    df_alarmes = carregar_alarmes(sheet_alarmes)
    
    if df_alarmes.empty:
        st.info("NENHUM ALARME RECORRENTE REGISTRADO.")
    else:
        
        df_display_alarmes = df_alarmes.copy()
        df_display_alarmes.rename(columns={
            'id_alarme': 'ID', 'TITULO': 'Título', 
            'HORA_ALARME': 'Hora', 'DIAS_SEMANA': 'Recorrência', 
            'ATIVO': 'Ativo?'
        }, inplace=True)
        
        st.dataframe(df_display_alarmes.drop(columns='ID', errors='ignore'), use_container_width=True, hide_index=True)

        st.divider()

        alarmes_atuais = df_alarmes['id_alarme'].tolist()
            
        def formatar_selecao_alarme(id_val):
            titulo = df_alarmes[df_alarmes['id_alarme'] == id_val]['TITULO'].iloc[0]
            return f"{titulo} ({id_val[:4]}...)"

        alarme_selecionado_id = st.selectbox(
            "Selecione o Alarme para Edição/Exclusão:",
            options=alarmes_atuais,
            index=0 if alarmes_atuais else None,
            format_func=formatar_selecao_alarme
        )

        if alarme_selecionado_id:
            alarme_dados = df_alarmes[df_alarmes['id_alarme'] == alarme_selecionado_id].iloc[0]
            
            col_u_alarme, col_d_alarme = st.columns([3, 1])

            with col_u_alarme:
                st.markdown("##### Atualizar Alarme Selecionado")
                with st.form("form_update_alarme"):
                    novo_titulo_alarme = st.text_input("Título", value=alarme_dados['TITULO'])
                    
                    col_update_1, col_update_2 = st.columns([1, 2])
                    
                    with col_update_1:
                        # Hora
                        hora_str = alarme_dados['HORA_ALARME']
                        novo_hora_alarme = st.time_input("Hora", value=time(int(hora_str[:2]), int(hora_str[3:])))
                        # Status
                        novo_status_alarme = st.selectbox("Ativo?", ['SIM', 'NÃO'], index=0 if alarme_dados['ATIVO'].upper() == 'SIM' else 1)
                    
                    with col_update_2:
                        # Dias da Semana (Faz o mapeamento reverso para exibir no multiselect)
                        dias_atuais = alarme_dados['DIAS_SEMANA'].split(', ')
                        dias_reversos = {v: k for k, v in dias_semana_map.items()} # {'SE': 'SEGUNDA'}
                        
                        dias_default = []
                        if 'TODOS' in dias_atuais or len(dias_atuais) > 1:
                            # Se for 'TODOS' ou múltiplos, mapeia para as strings completas
                            dias_default = [dias_reversos[d.strip()] for d in dias_atuais if d.strip() in dias_reversos]
                        
                        novo_dias_selecionados = st.multiselect(
                            "Dias da Semana para Recorrência:",
                            options=dias_semana_full,
                            default=dias_default
                        )
                        
                    update_alarme_button = st.form_submit_button("Salvar Atualizações do Alarme")

                    if update_alarme_button:
                        dias_formatados = [dias_semana_map[d] for d in novo_dias_selecionados]
                        dias_string = "TODOS" if not dias_formatados else ", ".join(dias_formatados)
                        
                        dados_atualizados_alarme = {
                            'id_alarme': alarme_selecionado_id, 
                            'TITULO': novo_titulo_alarme,
                            'HORA_ALARME': novo_hora_alarme.strftime('%H:%M'),
                            'DIAS_SEMANA': dias_string,
                            'ATIVO': novo_status_alarme
                        }
                        atualizar_alarme(sheet_alarmes, alarme_selecionado_id, dados_atualizados_alarme)
                        
            with col_d_alarme:
                st.markdown("##### Excluir Alarme")
                st.warning(f"Excluindo: **{alarme_dados['TITULO']}**")
                
                if st.button("🔴 EXCLUIR ALARME (Delete)", type="primary"):
                    deletar_alarme(sheet_alarmes, alarme_selecionado_id)
