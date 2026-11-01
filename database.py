import os
import json
import secrets
import re
from datetime import datetime
import pytz
import streamlit as st
from dotenv import load_dotenv
from utils.formatadores import extrair_data

load_dotenv()

# ==========================================
# 1. INICIALIZAÇÃO DO SUPABASE
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Credenciais de conexão com o Supabase não foram encontradas no arquivo .env ou nos Secrets.")
        st.stop()
    from supabase import create_client, Client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro ao conectar com o Supabase: {e}")
    st.stop()


# ==========================================
# 2. FEEDBACK VISUAL E CONFIGURAÇÕES BÁSICAS
# ==========================================
def notificar_sucesso(mensagem: str, icone: str = "✅"):
    st.session_state["toast_msg"] = mensagem
    st.session_state["toast_icon"] = icone

def notificar_erro(mensagem: str):
    st.toast(mensagem, icon="❌")

def obter_logo():
    try:
        res = supabase.table("configuracoes").select("valor").eq("chave", "logo_base64").execute()
        if res.data and len(res.data) > 0 and res.data[0].get("valor"):
            return res.data[0]["valor"]
    except Exception:
        pass
    if os.path.exists("logo.png"):
        return "logo.png"
    return None

def obter_precos_padrao():
    try:
        res = supabase.table("configuracoes").select("valor").eq("chave", "precos_padrao").execute()
        if res.data and len(res.data) > 0 and res.data[0].get("valor"):
            return json.loads(res.data[0]["valor"])
    except Exception:
        pass
    return {"diaria": 80.0, "cafe": 25.0, "toalha": 10.0}


# ==========================================
# 3. QUARTOS, CAMAS E RESERVAS
# ==========================================
def buscar_camas_com_quartos(status_filtro=None):
    res_q = supabase.table("quartos").select("*").execute()
    quartos_map = {q["id"]: q for q in (res_q.data or [])}

    query_c = supabase.table("camas").select("*")
    if status_filtro:
        query_c = query_c.eq("status", status_filtro)
    res_c = query_c.execute()
    camas = res_c.data or []

    for c in camas:
        q_obj = quartos_map.get(c.get("quarto_id"))
        c["quartos"] = q_obj if q_obj else {"nome": "?", "ala": "Geral", "ar_condicionado": False, "preco_base": 80.0}
    return camas

def buscar_reservas_completas(status_filtro=None, incluir_foto=False, ordem_desc=False):
    query_r = supabase.table("reservas").select("*")
    if status_filtro:
        query_r = query_r.eq("status", status_filtro)
    if ordem_desc:
        query_r = query_r.order("data_inicio", desc=True)
    res_r = query_r.execute()
    reservas = res_r.data or []

    if not reservas:
        return []

    colunas_hosp = "*" if incluir_foto else "id, nome, email, telefone, nacionalidade, cpf, passaporte_rne, documento"
    res_h = supabase.table("hospedes").select(colunas_hosp).execute()
    hosp_map = {h["id"]: h for h in (res_h.data or [])}

    camas_lista = buscar_camas_com_quartos()
    camas_map = {c["id"]: c for c in camas_lista}

    res_e = supabase.table("empresas").select("*").execute()
    emp_map = {e["id"]: e for e in (res_e.data or [])}

    for r in reservas:
        r["hospedes"] = hosp_map.get(r.get("hospede_id"))
        r["camas"] = camas_map.get(r.get("cama_id"))
        r["empresas"] = emp_map.get(r.get("empresa_id"))
    return reservas


# ==========================================
# 4. VENDAS, EVENTOS E MANUTENÇÃO
# ==========================================
def buscar_vendas_completas(hospede_id_filtro=None, apenas_pendentes=False, ordem_desc=False):
    query_v = supabase.table("vendas").select("*")
    if hospede_id_filtro is not None:
        query_v = query_v.eq("hospede_id", hospede_id_filtro)
    if apenas_pendentes:
        query_v = query_v.neq("status_pagamento", "Pago")
    if ordem_desc:
        query_v = query_v.order("data_venda", desc=True)
    res_v = query_v.execute()
    vendas = res_v.data or []

    if not vendas:
        return []

    res_p = supabase.table("produtos").select("*").execute()
    prod_map = {p["id"]: p for p in (res_p.data or [])}

    res_h = supabase.table("hospedes").select("id, nome, telefone").execute()
    hosp_map = {h["id"]: h for h in (res_h.data or [])}

    for v in vendas:
        v["produtos"] = prod_map.get(v.get("produto_id"))
        v["hospedes"] = hosp_map.get(v.get("hospede_id"))
    return vendas

def buscar_participantes_eventos_completos(evento_id_filtro=None, hospede_id_filtro=None, apenas_pendentes=False):
    query_ep = supabase.table("eventos_participantes").select("*")
    if evento_id_filtro is not None:
        query_ep = query_ep.eq("evento_id", evento_id_filtro)
    if hospede_id_filtro is not None:
        query_ep = query_ep.eq("hospede_id", hospede_id_filtro)
    if apenas_pendentes:
        query_ep = query_ep.neq("status_pagamento", "Pago")
    res_ep = query_ep.execute()
    participantes = res_ep.data or []

    if not participantes:
        return []

    res_ev = supabase.table("eventos").select("*").execute()
    ev_map = {e["id"]: e for e in (res_ev.data or [])}

    res_h = supabase.table("hospedes").select("id, nome, telefone").execute()
    hosp_map = {h["id"]: h for h in (res_h.data or [])}

    for ep in participantes:
        ep["eventos"] = ev_map.get(ep.get("evento_id"))
        ep["hospedes"] = hosp_map.get(ep.get("hospede_id"))
    return participantes

def buscar_manutencoes(status_filtro=None, ordem_data=True):
    try:
        q = supabase.table("manutencoes").select("*")
        if status_filtro:
            q = q.eq("status", status_filtro)
        if ordem_data:
            q = q.order("data_agendada", desc=False)
        res = q.execute()
        manutencoes = res.data or []

        if not manutencoes:
            return []

        res_q = supabase.table("quartos").select("id, nome, ala").execute()
        quartos_map = {q["id"]: q for q in (res_q.data or [])}

        res_c = supabase.table("camas").select("id, numero, quarto_id").execute()
        camas_map = {c["id"]: c for c in (res_c.data or [])}

        res_p = supabase.table("prestadores").select("id, nome_razao, telefone, categoria_servico").execute()
        prest_map = {p["id"]: p for p in (res_p.data or [])}

        for m in manutencoes:
            m["quartos"] = quartos_map.get(m.get("quarto_id"))
            m["camas"] = camas_map.get(m.get("cama_id"))
            m["prestadores"] = prest_map.get(m.get("prestador_id"))
        return manutencoes
    except Exception:
        return []

def busca_rapida_global(termo: str):
    if not termo or len(termo.strip()) < 2:
        return {"hospedes": [], "reservas": [], "quartos": [], "manutencoes": []}
    
    t = termo.strip().lower()
    resultados = {"hospedes": [], "reservas": [], "quartos": [], "manutencoes": []}

    try:
        res_h = supabase.table("hospedes").select("id, nome, telefone, email, documento, cpf").execute()
        for h in res_h.data or []:
            if t in str(h.get("nome", "")).lower() or t in str(h.get("telefone", "")) or t in str(h.get("documento", "")).lower():
                resultados["hospedes"].append(h)

        reservas = buscar_reservas_completas(status_filtro="Ativa")
        for r in reservas:
            cod = str(r.get("codigo_localizador", "")).lower()
            h_nome = str(r.get("hospedes", {}).get("nome", "")).lower() if r.get("hospedes") else ""
            if t in cod or t in h_nome:
                resultados["reservas"].append(r)

        res_q = supabase.table("quartos").select("*").execute()
        for q in res_q.data or []:
            if t in str(q.get("nome", "")).lower() or t in str(q.get("ala", "")).lower():
                resultados["quartos"].append(q)

        manut = buscar_manutencoes()
        for m in manut:
            if t in str(m.get("titulo", "")).lower() or t in str(m.get("local_detalhe", "")).lower():
                resultados["manutencoes"].append(m)
    except Exception:
        pass

    return resultados


# ==========================================
# 5. ALERTAS DO HOSTEL
# ==========================================
def obter_resumo_alertas():
    hoje = datetime.today().date()
    alertas = {
        "overstay": [],
        "checkout_hoje": [],
        "inadimplencia_vendas": [],
        "inadimplencia_eventos": [],
        "limpeza_pendente": [],
        "manutencoes_urgentes": []
    }
    try:
        ativas = buscar_reservas_completas(status_filtro="Ativa", incluir_foto=False)
        for r in ativas:
            dt_fim = extrair_data(r.get("data_fim"))
            if dt_fim:
                if dt_fim < hoje:
                    alertas["overstay"].append(r)
                elif dt_fim == hoje:
                    alertas["checkout_hoje"].append(r)

        alertas["inadimplencia_vendas"] = buscar_vendas_completas(apenas_pendentes=True)
        alertas["inadimplencia_eventos"] = buscar_participantes_eventos_completos(apenas_pendentes=True)
        alertas["limpeza_pendente"] = buscar_camas_com_quartos(status_filtro="Limpeza Pendente")

        todas_manut = buscar_manutencoes()
        for m in todas_manut:
            if m.get("status") in ["Pendente", "Em Andamento"]:
                dt_ag = extrair_data(m.get("data_agendada"))
                is_vencida = bool(dt_ag and dt_ag < hoje)
                is_alta_critica = m.get("prioridade") in ["Alta", "Crítica"]
                if is_vencida or is_alta_critica:
                    m["vencida"] = is_vencida
                    alertas["manutencoes_urgentes"].append(m)
    except Exception:
        pass
    return alertas


# ==========================================
# 6. AUTENTICAÇÃO, PERFIS E SESSÃO
# ==========================================
def solicitar_recuperacao_senha(email: str):
    try:
        supabase.auth.reset_password_for_email(email.strip())
        return True, "E-mail de recuperação enviado com sucesso! Verifique sua caixa de entrada."
    except Exception as e:
        return False, f"Falha ao enviar recuperação: {e}"

def salvar_perfil_usuario(email: str, nome: str, perfil: str, ativo: bool = True):
    email = email.lower().strip()
    status_str = "Ativo" if ativo else "Suspenso"
    try:
        res = supabase.table("usuarios_sistema").select("id").eq("email", email).execute()
        if res.data and len(res.data) > 0:
            supabase.table("usuarios_sistema").update({"nome": nome, "perfil": perfil, "status": status_str}).eq("email", email).execute()
        else:
            supabase.table("usuarios_sistema").insert({"email": email, "nome": nome, "perfil": perfil, "status": status_str}).execute()
        return True
    except Exception:
        try:
            chave_usuario = f"usr_perfil_{email}"
            dados_str = json.dumps({"nome": nome, "perfil": perfil, "status": status_str})
            res_c = supabase.table("configuracoes").select("chave").eq("chave", chave_usuario).execute()
            if res_c.data and len(res_c.data) > 0:
                supabase.table("configuracoes").update({"valor": dados_str}).eq("chave", chave_usuario).execute()
            else:
                supabase.table("configuracoes").insert({"chave": chave_usuario, "valor": dados_str}).execute()
            return True
        except Exception:
            return False

def obter_perfil_usuario(email: str, auth_user=None):
    email = email.lower().strip()
    
    try:
        res = supabase.table("usuarios_sistema").select("*").eq("email", email).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            if row.get("status") == "Suspenso":
                return "Suspenso", row.get("nome", email)
            return row.get("perfil", "Administrador"), row.get("nome", email)
    except Exception:
        pass
    
    try:
        chave_usuario = f"usr_perfil_{email}"
        res_c = supabase.table("configuracoes").select("valor").eq("chave", chave_usuario).execute()
        if res_c.data and len(res_c.data) > 0:
            dados = json.loads(res_c.data[0]["valor"])
            if dados.get("status") == "Suspenso":
                return "Suspenso", dados.get("nome", email)
            return dados.get("perfil", "Administrador"), dados.get("nome", email)
    except Exception:
        pass

    try:
        res_col = supabase.table("colaboradores").select("*").eq("email", email).execute()
        if res_col.data and len(res_col.data) > 0:
            col = res_col.data[0]
            if col.get("status") in ["Suspenso", "Inativo"]:
                return "Suspenso", col.get("nome", email)
            cargo = col.get("cargo", "Administrador")
            if cargo in ["Gerente", "Administrador"]:
                return "Administrador", col.get("nome", email)
            return cargo, col.get("nome", email)
    except Exception:
        pass

    return "Administrador", email

def listar_todos_usuarios():
    try:
        res = supabase.table("usuarios_sistema").select("*").order("email").execute()
        if res.data:
            return res.data
    except Exception:
        pass
    
    lista = []
    try:
        res_c = supabase.table("configuracoes").select("*").like("chave", "usr_perfil_%").execute()
        for item in res_c.data or []:
            email = item["chave"].replace("usr_perfil_", "")
            dados = json.loads(item["valor"])
            lista.append({
                "email": email, 
                "nome": dados.get("nome", email), 
                "perfil": dados.get("perfil", "Administrador"),
                "status": dados.get("status", "Ativo")
            })
    except Exception:
        pass
    return lista

def excluir_usuario_sistema(email: str):
    email = email.lower().strip()
    sucesso = False
    try:
        supabase.table("usuarios_sistema").delete().eq("email", email).execute()
        sucesso = True
    except Exception:
        pass
    try:
        chave_usuario = f"usr_perfil_{email}"
        supabase.table("configuracoes").delete().eq("chave", chave_usuario).execute()
        sucesso = True
    except Exception:
        pass
    try:
        supabase.table("colaboradores").delete().eq("email", email).execute()
        sucesso = True
    except Exception:
        pass
    return sucesso


# ==========================================
# 7. HORÁRIOS DE TURNO E SESSÃO PERSISTENTE
# ==========================================
def obter_horario_brasilia():
    fuso = pytz.timezone("America/Sao_Paulo")
    return datetime.now(fuso)

def validar_horario_acesso(email_usuario, perfil_usuario):
    # Administradores e Gerentes não têm restrição de horário nem de dia
    if perfil_usuario in ["Administrador", "Gerente"]:
        return True, ""

    try:
        res = supabase.table("colaboradores").select("horario_inicio, horario_fim, restringir_horario, dias_permitidos").eq("email", email_usuario).execute()
        if not res.data:
            return True, ""

        dados = res.data[0]
        if not dados.get("restringir_horario"):
            return True, ""

        # Obter data/hora atual no fuso correto
        agora_dt = obter_horario_brasilia()
        agora = agora_dt.time()

        # 1. Validação dos Dias da Semana
        dias_semana_pt = {
            0: "Segunda-feira",
            1: "Terça-feira",
            2: "Quarta-feira",
            3: "Quinta-feira",
            4: "Sexta-feira",
            5: "Sábado",
            6: "Domingo"
        }
        hoje_str = dias_semana_pt[agora_dt.weekday()]
        
        # Pega a lista do banco. Se por acaso for None, libera como fallback de segurança
        dias_permitidos = dados.get("dias_permitidos")
        
        if dias_permitidos and hoje_str not in dias_permitidos:
            return False, f"Acesso negado: Seu expediente não inclui {hoje_str}."

        # 2. Validação de Horário (Hora início e Hora fim)
        h_inicio_str = dados.get("horario_inicio") or "00:00:00"
        h_fim_str = dados.get("horario_fim") or "23:59:59"

        h_inicio = datetime.strptime(str(h_inicio_str)[:8], "%H:%M:%S").time()
        h_fim = datetime.strptime(str(h_fim_str)[:8], "%H:%M:%S").time()

        if h_inicio <= h_fim:
            permitido = h_inicio <= agora <= h_fim
        else:
            # Turno da madrugada (ex: 22:00 as 06:00)
            permitido = agora >= h_inicio or agora <= h_fim

        if not permitido:
            return False, f"Acesso permitido apenas entre {h_inicio.strftime('%H:%M')} e {h_fim.strftime('%H:%M')}."

        return True, ""
    except Exception:
        return True, ""

def gerar_token_sessao(email_usuario):
    token = secrets.token_urlsafe(32)
    email = email_usuario.lower().strip()
    try:
        chave_tok = f"sess_tok_{token}"
        dados_tok = json.dumps({"email": email, "criado_em": str(datetime.now())})
        supabase.table("configuracoes").insert({"chave": chave_tok, "valor": dados_tok}).execute()
        return token
    except Exception:
        try:
            supabase.table("colaboradores").update({"session_token": token}).eq("email", email).execute()
            return token
        except Exception:
            return None

def validar_token_sessao(token):
    if not token:
        return None
    try:
        chave_tok = f"sess_tok_{token}"
        res_c = supabase.table("configuracoes").select("valor").eq("chave", chave_tok).execute()
        if res_c.data and len(res_c.data) > 0:
            dados_tok = json.loads(res_c.data[0]["valor"])
            email = dados_tok.get("email")
            if email:
                perfil, nome = obter_perfil_usuario(email)
                if perfil != "Suspenso":
                    return {"email": email, "nome": nome, "perfil": perfil}
    except Exception:
        pass

    try:
        res = supabase.table("colaboradores").select("email, nome, cargo, status").eq("session_token", token).execute()
        if res.data and len(res.data) > 0:
            u = res.data[0]
            if u.get("status") not in ["Suspenso", "Inativo"]:
                perfil, nome = obter_perfil_usuario(u["email"])
                return {"email": u["email"], "nome": nome, "perfil": perfil}
    except Exception:
        pass
    return None

def revogar_token_sessao(email_usuario, token=None):
    if token:
        try:
            supabase.table("configuracoes").delete().eq("chave", f"sess_tok_{token}").execute()
        except Exception:
            pass
    try:
        supabase.table("colaboradores").update({"session_token": None}).eq("email", email_usuario).execute()
    except Exception:
        pass