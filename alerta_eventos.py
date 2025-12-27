import os
from datetime import datetime, timedelta

# Importa as bibliotecas necessárias
import gspread
import pandas as pd
from telegram import Bot
import asyncio

# --- CONFIGURAÇÃO E AUTENTICAÇÃO DO SISTEMA (SEM ALTERAÇÕES) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- FUNÇÕES CORE (SEM ALTERAÇÕES) ---
def conectar_sheets():
    # ... (Função conectar_sheets() permanece a mesma) ...
    try:
        GSPREAD_CREDENTIALS_JSON = os.getenv("GSPREAD_CREDENTIALS_JSON")
        if not GSPREAD_CREDENTIALS_JSON:
            print("🚨 ERRO: Credenciais do Google Sheets não encontradas. Verifique a Secret 'GSPREAD_CREDENTIALS_JSON'.")
            return None
        import json
        creds_dict = json.loads(GSPREAD_CREDENTIALS_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        spreadsheet = gc.open_by_key(PLANILHA_ID)
        sheet = spreadsheet.worksheet(ABA_NOME)
        print("✅ Conexão com Google Sheets estabelecida.")
        return sheet
    except Exception as e:
        print(f"🚨 Erro fatal ao conectar ao Sheets: {e}")
        return None

def carregar_eventos(sheet):
    # ... (Função carregar_eventos() permanece a mesma) ...
    if sheet is None:
         return pd.DataFrame()
    try:
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        df['data_evento'] = pd.to_datetime(df['data_evento'], errors='coerce')
        return df
    except Exception as e:
        print(f"Erro ao carregar eventos: {e}")
        return pd.DataFrame()

async def enviar_alerta(mensagem):
    # ... (Função enviar_alerta() permanece a mesma) ...
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERRO: Token ou Chat ID do Telegram não configurados.")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text=mensagem, 
            parse_mode='Markdown'
        )
        print("🎉 Alerta enviado com sucesso para o Telegram!")
    except Exception as e:
        print(f"🚨 Erro ao enviar mensagem para o Telegram: {e}")

# --- LÓGICA DO AGENTE DE ALERTA (COMPLETAMENTE REVISADA) ---

def main_alerta():
    """Função principal que executa a lógica de alerta e notificação."""
    print("Iniciando Agente de Alerta...")
    
    sheet = conectar_sheets()
    if sheet is None:
        return

    df_eventos = carregar_eventos(sheet)
    
    # Alerta se não houver dados
    if df_eventos.empty:
        print("Nenhum evento encontrado na planilha.")
        mensagem_vazia = "OLÁ! NÃO HÁ EVENTOS REGISTRADOS!"
        asyncio.run(enviar_alerta(mensagem_vazia))
        return

    # --- DEFINIÇÃO DE FILTROS DE GOVERNANÇA (APENAS STATUS PENDENTE) ---
    
    hoje = datetime.now().date()
    amanha = hoje + timedelta(days=1)
    
    # Filtro Base: Apenas eventos PENDENTES com data válida
    df_pendentes = df_eventos[
        (df_eventos['status'] == 'Pendente') & 
        (df_eventos['data_evento'].notna())
    ]
    
    # 1. EVENTOS VENCIDOS (NOVO FILTRO)
    df_vencidos = df_pendentes[
        (df_pendentes['data_evento'].dt.date < hoje)
    ]
    
    # 2. EVENTOS DE ALTA PRIORIDADE PARA HOJE OU FUTURO
    df_alta_pendente = df_pendentes[
        (df_pendentes['prioridade'] == 'Alta')
        # Não precisa verificar a data aqui, pois Vencidos já filtra os antigos
    ]
    
    # 3. EVENTOS AGENDADOS PARA AMANHÃ
    df_amanha = df_pendentes[
        (df_pendentes['data_evento'].dt.date == amanha)
    ]
    
    # --- CONSTRUÇÃO DA MENSAGEM ---
    mensagens = []

    # ALERTA 1: EVENTOS VENCIDOS (Prioridade máxima por estarem atrasados)
    if not df_vencidos.empty:
        msg_vencidos = "🔴 *ATRASO CRÍTICO* 🔴\nItens PENDENTES com prazo VENCIDO:\n"
        for index, row in df_vencidos.head(5).iterrows():
            msg_vencidos += f"  - {row['titulo']} (Vencimento: {row['data_evento'].strftime('%d/%m/%Y')})\n"
        if len(df_vencidos) > 5:
             msg_vencidos += f"  ... e mais {len(df_vencidos) - 5} itens vencidos.\n"
        mensagens.append(msg_vencidos)
        
    # ALERTA 2: ALTA PRIORIDADE (Se não estiverem vencidos, lista aqui)
    # Filtra apenas Alta Prioridade que AINDA NÃO ESTÃO VENCIDOS
    df_alta_nao_vencida = df_alta_pendente[
        (df_alta_pendente['data_evento'].dt.date >= hoje)
    ]
    
    if not df_alta_nao_vencida.empty:
        msg_alta = "🚨 *PRIORIDADE ALTA* 🚨\n"
        for index, row in df_alta_nao_vencida.head(3).iterrows():
            msg_alta += f"  - {row['titulo']} (Data: {row['data_evento'].strftime('%d/%m/%Y')})\n"
        if len(df_alta_nao_vencida) > 3:
             msg_alta += f"  ... e mais {len(df_alta_nao_vencida) - 3} itens de Alta Prioridade.\n"
        mensagens.append(msg_alta)


    # ALERTA 3: EVENTOS DE AMANHÃ
    if not df_amanha.empty:
        msg_amanha = "🗓️ *AGENDA DE AMANHÃ* 🗓️\n"
        for index, row in df_amanha.iterrows():
            msg_amanha += f"  - {row['titulo']} ({row['hora_evento']}) - Local: {row['local']}\n"
        mensagens.append(msg_amanha)

    # ALERTA FINAL: ENVIO
    if mensagens:
        mensagem_final = "🤖 *Relatório de Governança da Agenda*\n\n" + "\n---\n".join(mensagens)
        asyncio.run(enviar_alerta(mensagem_final))
    else:
        # SEM EVENTOS URGENTES
        print("Nenhum alerta de alta prioridade, vencido ou evento para amanhã.")
        mensagem_nada_consta = "OLÁ! NÃO HÁ EVENTOS URGENTES!"
        asyncio.run(enviar_alerta(mensagem_nada_consta))


if __name__ == "__main__":
    main_alerta()
