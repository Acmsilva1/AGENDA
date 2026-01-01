import os
from datetime import datetime, timedelta

# Importa as bibliotecas necessárias
import gspread
import pandas as pd
from telegram import Bot
import asyncio

# --- CONFIGURAÇÃO E AUTENTICAÇÃO DO SISTEMA ---

# 🛑 VARIÁVEIS DE AMBIENTE (SECRETS DO GITHUB)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ID da Planilha no seu Google Drive
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- CONSTANTE DE GOVERNANÇA (NOVO REQUISITO) ---
# Alerta sempre 5 dias antes de qualquer evento (a partir de hoje)
DIAS_DE_ALERTA = 5

# --- FUNÇÕES CORE (Sem Alterações) ---

def conectar_sheets():
    """Conecta ao Google Sheets usando Secrets armazenadas no ambiente."""
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
    """Lê todos os registros e retorna como DataFrame."""
    if sheet is None:
         return pd.DataFrame()
    try:
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        # Garante que a coluna exista, mas não usaremos seu valor para o filtro.
        if 'data_evento' in df.columns:
            df['data_evento'] = pd.to_datetime(df['data_evento'], errors='coerce')
        return df
    except Exception as e:
        print(f"Erro ao carregar eventos: {e}")
        return pd.DataFrame()

async def enviar_alerta(mensagem):
    """Envia a mensagem para o Telegram de forma assíncrona."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERRO: Token ou Chat ID do Telegram não configurados.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text=mensagem, 
            parse_mode='Markdown' # Usa Markdown para negrito, etc.
        )
        print("🎉 Alerta enviado com sucesso para o Telegram!")
    except Exception as e:
        print(f"🚨 Erro ao enviar mensagem para o Telegram: {e}")

# --- LÓGICA DO AGENTE DE ALERTA (MODIFICADA) ---

def main_alerta():
    """Função principal que executa a lógica de alerta e notificação."""
    print("Iniciando Agente de Alerta...")
    
    sheet = conectar_sheets()
    if sheet is None:
        return

    df_eventos = carregar_eventos(sheet)
    
    # 📌 NOVO ALERTA 1: SEM REGISTRO DE EVENTOS (Planilha vazia)
    if df_eventos.empty or 'data_evento' not in df_eventos.columns:
        print("Nenhum evento ou coluna de data encontrado na planilha.")
        # Frase solicitada: "OLÁ! NÃO HÁ EVENTOS REGISTRADOS!"
        mensagem_vazia = "OLÁ! NÃO HÁ EVENTOS REGISTRADOS!"
        asyncio.run(enviar_alerta(mensagem_vazia))
        return

    # 1. DEFINIÇÃO DO NOVO FILTRO DE ALERTA (GOVERNANÇA SIMPLIFICADA)
    
    hoje = datetime.now().date()
    # Limite superior: 5 dias à frente (qualquer evento em até 5 dias)
    limite_alerta = hoje + timedelta(days=DIAS_DE_ALERTA)
    
    # Filtro Simples: Pendente E data do evento de HOJE até o limite de 5 dias
    df_alerta_5_dias = df_eventos[
        (df_eventos['status'] == 'Pendente') &
        (df_eventos['data_evento'].dt.date >= hoje) & # Não lista eventos passados
        (df_eventos['data_evento'].dt.date <= limite_alerta) # Dentro da janela de 5 dias
    ].sort_values(by='data_evento', ascending=True)

    # --- CONSTRUÇÃO DA MENSAGEM ---
    
    mensagens = []
    
    # ALERTA ÚNICO: EVENTOS PENDENTES NOS PRÓXIMOS 5 DIAS
    if not df_alerta_5_dias.empty:
        # ⚠️ MUDANÇA NO TÍTULO PARA REFLETIR A NOVA REGRA
        msg_alerta = f"🗓️ *ALERTA DE AGENDA ({DIAS_DE_ALERTA} DIAS)* 🗓️\n"
        
        # Lista os 5 primeiros eventos mais próximos
        for index, row in df_alerta_5_dias.head(5).iterrows():
             data_formatada = row['data_evento'].strftime('%d/%m/%Y')
             # Calcula quantos dias faltam para maior clareza na notificação
             dias_restantes = (row['data_evento'].dt.date - hoje).days
             
             if dias_restantes == 0:
                 dias_info = "HOJE"
             elif dias_restantes == 1:
                 dias_info = "AMANHÃ"
             else:
                 dias_info = f"em {dias_restantes} dias"

             msg_alerta += f"  - **{row['titulo']}** ({dias_info})\n    _Data: {data_formatada} | Local: {row.get('local', 'N/A')}_\n"
        
        if len(df_alerta_5_dias) > 5:
             msg_alerta += f"  ... e mais {len(df_alerta_5_dias) - 5} eventos pendentes em breve.\n"
             
        mensagens.append(msg_alerta)

    # ALERTA FINAL: SE HOUVE MENSAGEM (AGENDA) OU SE NÃO HOUVE (NADA CONSTA)
    if mensagens:
        # Se encontrou alertas, envia a lista completa
        mensagem_final = "🤖 *Relatório da Sua Agenda Simplificada*\n\n" + "\n---\n".join(mensagens)
        asyncio.run(enviar_alerta(mensagem_final))
    else:
        # 📌 NOVO ALERTA 2: SEM EVENTOS URGENTES (Planilha com dados, mas filtros vazios)
        print("Nenhum evento pendente nos próximos 5 dias. Paz de espírito.")
        # Frase solicitada: "OLÁ! NÃO HÁ EVENTOS URGENTES!"
        mensagem_nada_consta = "OLÁ! NÃO HÁ EVENTOS URGENTES!"
        asyncio.run(enviar_alerta(mensagem_nada_consta))


if __name__ == "__main__":
    main_alerta()
