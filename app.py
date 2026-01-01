import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time
import time as t 
from streamlit_autorefresh import st_autorefresh 

# --- CONFIGURAÇÕES DO PROJETO ---

# ID da Planilha no seu Google Drive (Mantenha o mesmo)
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


# --- FUNÇÕES CORE DO CRUD ---

# R (Read) - Lê todos os eventos
def carregar_eventos(sheet):
    """Lê todos os registros (ignorando o cabeçalho) e retorna como DataFrame."""
    
    # Defende contra sheet=None
    if sheet is None:
         return pd.DataFrame()
         
    try:
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        return pd.DataFrame()

# C (Create) - Adiciona um novo evento
def adicionar_evento(sheet, dados_do_form):
    """Insere uma nova linha de evento no Sheets."""
    
    # ⚠️ REMOVIDA A COLUNA 'PRIORIDADE'
    nova_linha = [
        dados_do_form.get('id_evento'),
        dados_do_form.get('titulo'),
        dados_do_form.get('descricao'),
        dados_do_form.get('data_evento'),
        dados_do_form.get('hora_evento'),
        dados_do_form.get('local'),
        # O campo 'prioridade' deve ser removido da sua planilha ou mantido como um valor fixo.
        # POR GOVERNANÇA E PADRONIZAÇÃO DA PLANILHA, VOU INSERIR UM VALOR VAZIO ('') AQUI.
        '', # <--- Espaço reservado para a coluna 'prioridade' que deve ser ignorada
        dados_do_form.get('status')
    ]
    
    sheet.append_row(nova_linha)
    st.success("🎉 Evento criado. Mais um compromisso para a sua vida. **A lista abaixo será atualizada automaticamente em 20 segundos.**") # Ajuste na mensagem
    conectar_sheets.clear()

# U (Update) - Atualiza um evento existente
def atualizar_evento(sheet, id_evento, novos_dados):
    """Busca a linha pelo ID e atualiza os dados da linha."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row 

        # ⚠️ REMOVIDA A COLUNA 'PRIORIDADE'
        valores_atualizados = [
            novos_dados['id_evento'],
            novos_dados['titulo'],
            novos_dados['descricao'],
            novos_dados['data_evento'],
            novos_dados['hora_evento'],
            novos_dados['local'],
            '', # <--- Espaço reservado para a coluna 'prioridade'
            novos_dados['status']
        ]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Evento {id_evento[:8]}... atualizado com sucesso. Foco nos detalhes. **A lista abaixo será atualizada automaticamente em 20 segundos.**") # Ajuste na mensagem
        conectar_sheets.clear()
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Algum erro na matriz.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

# D (Delete) - Remove um evento
def deletar_evento(sheet, id_evento):
    """Busca a linha pelo ID e a deleta."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento[:8]}... deletado. Férias merecidas para esse compromisso. **A lista abaixo será atualizada automaticamente em 20 segundos.**") # Ajuste na mensagem
        conectar_sheets.clear()
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Impossível apagar algo que não existe.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) - TELA ÚNICA ---

st.set_page_config(layout="wide")
st.title("🗓️ AGENDA DE EVENTOS")

sheet = conectar_sheets()

if sheet is None:
    st.stop()


# === SEÇÃO 1: CRIAR NOVO EVENTO ===
st.header("REGISTRAR NOVO EVENTO")

with st.form("form_novo_evento", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        titulo = st.text_input("TÍTULO DO EVENTO", max_chars=100)
        local = st.text_input("Local ou Link da Reunião:")
        data = st.date_input("Data:", date.today(), format="DD/MM/YYYY") 
    
    with col2:
        # ❌ REMOÇÃO DA PRIORIDADE
        # prioridade = st.selectbox("Prioridade:", ["Média", "Alta", "Baixa"])
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
                # 'prioridade': prioridade, # ❌ REMOVIDO DA CAPTURA
                'status': status_inicial
            }
            adicionar_evento(sheet, dados_para_sheet)
            
        else:
            st.warning("O Título e a Data são obrigatórios. Não complique.")
            

st.divider() # Adicionado para separar visualmente o formulário da tabela

# === SEÇÃO 2: VISUALIZAR E GERENCIAR (R, U, D) ===

# MODIFICAÇÃO: AUMENTAR REFRESH PARA 20000ms (20 segundos)
st_autorefresh(interval=20000, key="data_refresh_key")
st.info("🔄 **ATUALIZAÇÃO AUTOMÁTICA** (A cada 20 segundos)")

st.header("MEUS EVENTOS")

df_eventos = carregar_eventos(sheet) 

if df_eventos.empty:
    st.info("SEM REGISTROS")
else:
    
    df_display = df_eventos.copy()
    
    if 'data_evento' in df_display.columns:
        df_display['data_evento'] = pd.to_datetime(df_display['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    # ⚠️ MANTIVE A COLUNA 'Prioridade' na renomeação caso a planilha ainda a tenha, mas ela será ignorada na visualização.
    df_display.rename(columns={
        'id_evento': 'ID', 
        'titulo': 'Título', 
        'data_evento': 'Data',
        'hora_evento': 'Hora',
        'descricao': 'Descrição',
        'local': 'Local',
        'prioridade': 'Prioridade (Ignorada)', # 🔄 RENOMEADA PARA CLAREZA
        'status': 'Status'
    }, inplace=True)
    
    st.dataframe(df_display.sort_values(by='Data', ascending=False), use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("🛠️ Edição e Exclusão")

    if not df_eventos.empty:
        
        eventos_atuais = df_eventos['id_evento'].tolist()
        
        def formatar_selecao(id_val):
            # Adiciona uma checagem para 'titulo' existir, pois a planilha pode estar inconsistente
            titulo = df_eventos[df_eventos['id_evento'] == id_val]['titulo'].iloc[0] if 'titulo' in df_eventos.columns else "Evento Sem Título"
            return f"{titulo} ({id_val[:4]}...)"

        evento_selecionado_id = st.selectbox(
            "Selecione o Evento para Ação (Edição/Exclusão):",
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

                col_data_hora, col_local_status = st.columns(2) # 🔄 RENOMEADO PARA REFLETIR MUDANÇA

                with col_data_hora:
                    novo_data = st.date_input(
                        "Data", 
                        value=pd.to_datetime(evento_dados['data_evento']).date(),
                        format="DD/MM/YYYY"
                    )
                    # Tratamento de segurança para hora
                    novo_hora_str = evento_dados['hora_evento']
                    try:
                        novo_hora = st.time_input("Hora", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:])))
                    except:
                        # Fallback seguro para hora inválida
                        novo_hora = st.time_input("Hora (Valor Padrão)", value=time(9, 0)) 
                
                with col_local_status: # 🔄 MUDANÇA NA COLUNA
                    novo_local = st.text_input("Local", value=evento_dados['local'])
                    # ❌ REMOÇÃO DO CAMPO DE PRIORIDADE
                    # opcoes_prioridade = ["Alta", "Média", "Baixa"]
                    # novo_prioridade = st.selectbox("Prioridade", opcoes_prioridade, index=opcoes_prioridade.index(evento_dados['prioridade']))
                    opcoes_status = ['Pendente', 'Concluído', 'Cancelado']
                    novo_status = st.selectbox("Status", opcoes_status, index=opcoes_status.index(evento_dados['status']))

                update_button = st.form_submit_button("Salvar Atualizações (Update)")

                if update_button:
                    dados_atualizados = {
                        'id_evento': evento_selecionado_id, 
                        'titulo': novo_titulo,
                        'descricao': nova_descricao,
                        'data_evento': novo_data.strftime('%Y-%m-%d'),
                        'hora_evento': novo_hora.strftime('%H:%M'),
                        'local': novo_local,
                        # 'prioridade': evento_dados['prioridade'], # ❌ REMOVIDO DO DICIONÁRIO
                        'status': novo_status
                    }
                    atualizar_evento(sheet, evento_selecionado_id, dados_atualizados)
                        
        
        with col_d:
            st.markdown("##### Excluir Evento")
            st.warning(f"Excluindo: **{evento_dados['titulo']}**")
            
            if st.button("🔴 EXCLUIR EVENTO (Delete)", type="primary"):
                deletar_evento(sheet, evento_selecionado_id)
