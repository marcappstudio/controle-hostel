import re
import urllib.parse
from datetime import datetime, date, time
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import (
    converter_para_base64, validar_cpf, validar_cnpj, ordenar_natural, formatar_data_br
)
from utils.exportadores import gerar_csv, gerar_pdf_tabela

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO", "Exterior"
]

def calcular_idade(data_nasc):
    if not data_nasc:
        return None
    hoje = date.today()
    return hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))

def renderizar_hospedes():
    aba_cad, aba_cons = st.tabs(["Cadastrar Hóspede", "Consultar / Editar / Excluir"])

    with aba_cad:
        st.subheader("Novo Cadastro de Hóspede")
        col_p1, col_p2, col_p3 = st.columns([2, 1.2, 1])
        with col_p1:
            nome = st.text_input("Nome Completo:", key="cad_h_nome")
        with col_p2:
            data_nasc = st.date_input("Data de Nascimento:", value=date(1995, 1, 1), min_value=date(1910, 1, 1), max_value=date.today(), format="DD/MM/YYYY", key="cad_h_nasc")
        with col_p3:
            genero = st.selectbox("Gênero:", ["Não informado", "Feminino", "Masculino", "Outro"], key="cad_h_gen")

        idade_calculada = calcular_idade(data_nasc)
        responsavel_menor = None
        is_menor = (idade_calculada is not None and idade_calculada < 18)

        if is_menor:
            st.warning(f"⚠️ Hóspede Menor de Idade ({idade_calculada} anos) — ECA Art. 82")
            responsavel_menor = st.text_input("Nome e Documento do Responsável / Autorização:", key="cad_h_resp_menor")
        else:
            st.caption(f"Idade apurada: **{idade_calculada} anos** (Maior de idade)")

        col_d1, col_d2, col_d3 = st.columns([1, 1.2, 1.2])
        with col_d1:
            nacionalidade = st.selectbox("Nacionalidade:", ["Brasileira", "Estrangeira"], key="cad_h_nac")
        with col_d2:
            if nacionalidade == "Brasileira":
                cpf = st.text_input("CPF:", key="cad_h_cpf")
                passaporte = ""
            else:
                cpf = ""
                passaporte = st.text_input("Passaporte / RNE:", key="cad_h_pass")
        with col_d3:
            telefone = st.text_input("Telefone / WhatsApp:", key="cad_h_tel")

        col_c1, col_c2 = st.columns([1.5, 1])
        with col_c1:
            email = st.text_input("E-mail:", key="cad_h_email")
        with col_c2:
            pais_origem = st.text_input("País de Residência:", value="Brasil" if nacionalidade == "Brasileira" else "", key="cad_h_pais")

        col_cid, col_uf = st.columns([2, 1])
        with col_cid:
            cidade_origem = st.text_input("Cidade de Origem:", key="cad_h_cid")
        with col_uf:
            if nacionalidade == "Brasileira":
                estado_origem = st.selectbox("Estado (UF):", UFS_BRASIL, index=UFS_BRASIL.index("RS") if "RS" in UFS_BRASIL else 0, key="cad_h_uf")
            else:
                estado_origem = st.text_input("Estado / Província:", key="cad_h_uf_estrang")

        observacoes = st.text_area("Observações:", key="cad_h_obs")
        origem_foto = st.radio("Origem da Imagem:", ["Nenhuma", "Carregar Arquivo", "Tirar Foto com a Câmera"], horizontal=True, key="cad_h_origem_foto")
        
        arquivo_foto_cad = None
        if origem_foto == "Carregar Arquivo":
            arquivo_foto_cad = st.file_uploader("Selecione a foto:", type=["png", "jpg", "jpeg"], key="cad_h_upload")
        elif origem_foto == "Tirar Foto com a Câmera":
            arquivo_foto_cad = st.camera_input("Capture a imagem", key="cad_h_camera")

        aceite_lgpd = st.checkbox("Declaro ciência quanto à LGPD e exigências do Ministério do Turismo.", value=True, key="cad_h_lgpd")

        if st.button("Salvar Cadastro do Hóspede", type="primary", use_container_width=True, key="btn_salvar_novo_hospede"):
            if not nome:
                st.error("O campo Nome Completo é obrigatório.")
            elif nacionalidade == "Brasileira" and cpf and not validar_cpf(cpf):
                st.error("CPF inválido.")
            else:
                cpf_limpo = re.sub(r'\D', '', cpf) if cpf else None
                doc_unificado = cpf_limpo if nacionalidade == "Brasileira" else passaporte
                foto_b64 = converter_para_base64(arquivo_foto_cad) if arquivo_foto_cad else None
                
                db.supabase.table("hospedes").insert({
                    "nome": nome,
                    "data_nascimento": data_nasc.isoformat(),
                    "genero": genero,
                    "documento": doc_unificado,
                    "email": email,
                    "telefone": telefone,
                    "nacionalidade": nacionalidade,
                    "cpf": cpf_limpo,
                    "passaporte_rne": passaporte if passaporte else None,
                    "cidade_origem": cidade_origem,
                    "estado_origem": estado_origem,
                    "pais_origem": pais_origem,
                    "responsavel_menor": responsavel_menor if is_menor else None,
                    "observacoes": observacoes,
                    "foto": foto_b64,
                    "lgpd_consentimento": True,
                    "lgpd_data_consentimento": datetime.now().isoformat(),
                    "anonimizado": False
                }).execute()
                db.notificar_sucesso(f"Hóspede {nome} cadastrado com sucesso!")
                st.rerun()

    with aba_cons:
        try:
            res_h = db.supabase.table("hospedes").select("*").execute()
            lista_h = res_h.data or []
            if not lista_h:
                st.info("Nenhum hóspede cadastrado.")
            else:
                h_labels = ["-- Selecione o Hóspede --"] + [f"{h['nome']} (Doc: {h.get('cpf') or h.get('documento') or 'S/N'})" for h in lista_h]
                h_escolhido = st.selectbox("Buscar Hóspede:", h_labels)

                if h_escolhido != "-- Selecione o Hóspede --":
                    idx = h_labels.index(h_escolhido) - 1
                    h_obj = lista_h[idx]
                    
                    with st.form(f"form_edit_hosp_{h_obj['id']}"):
                        e_nome = st.text_input("Nome", value=h_obj.get("nome", ""))
                        e_tel = st.text_input("Telefone", value=h_obj.get("telefone", ""))
                        e_email = st.text_input("E-mail", value=h_obj.get("email", ""))
                        e_obs = st.text_area("Observações", value=h_obj.get("observacoes", ""))

                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Atualizar Hóspede", type="primary"):
                            db.supabase.table("hospedes").update({
                                "nome": e_nome, "telefone": e_tel, "email": e_email, "observacoes": e_obs
                            }).eq("id", h_obj["id"]).execute()
                            db.notificar_sucesso("Hóspede atualizado!")
                            st.rerun()
                        if c2.form_submit_button("Excluir Hóspede"):
                            db.supabase.table("hospedes").delete().eq("id", h_obj["id"]).execute()
                            db.notificar_sucesso("Hóspede excluído!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

def renderizar_empresas():
    aba_cad_emp, aba_cons_emp = st.tabs(["Cadastrar Empresa", "Consultar / Editar / Excluir"])
    with aba_cad_emp:
        with st.form("form_cad_empresa"):
            emp_razao = st.text_input("Razão Social")
            emp_cnpj = st.text_input("CNPJ")
            emp_email = st.text_input("E-mail")
            emp_telefone = st.text_input("Telefone")
            if st.form_submit_button("Salvar Empresa"):
                if emp_razao:
                    db.supabase.table("empresas").insert({"razao_social": emp_razao, "cnpj": re.sub(r'\D', '', emp_cnpj), "email": emp_email, "telefone": emp_telefone}).execute()
                    db.notificar_sucesso("Empresa cadastrada!")
                    st.rerun()

    with aba_cons_emp:
        try:
            res_emp = db.supabase.table("empresas").select("*").execute()
            lista_emp = res_emp.data or []
            if lista_emp:
                emp_labels = ["-- Selecione --"] + [e['razao_social'] for e in lista_emp]
                sel = st.selectbox("Empresa:", emp_labels)
                if sel != "-- Selecione --":
                    obj = lista_emp[emp_labels.index(sel) - 1]
                    if st.button("Excluir Empresa"):
                        db.supabase.table("empresas").delete().eq("id", obj["id"]).execute()
                        db.notificar_sucesso("Empresa removida!")
                        st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

def renderizar_quartos():
    aba_qc, aba_qe = st.tabs(["Cadastrar Quarto", "Editar / Excluir Quarto"])
    with aba_qc:
        with st.form("form_cad_quarto"):
            q_nome = st.text_input("Nome do Quarto")
            q_preco = st.number_input("Preço Base", value=80.0)
            if st.form_submit_button("Salvar Quarto"):
                if q_nome:
                    db.supabase.table("quartos").insert({"nome": q_nome, "preco_base": q_preco}).execute()
                    db.notificar_sucesso("Quarto salvo!")
                    st.rerun()
    with aba_qe:
        try:
            res = db.supabase.table("quartos").select("*").execute()
            for q in (res.data or []):
                st.write(f"• Quarto **{q['nome']}** (R$ {q.get('preco_base', 0)})")
        except Exception:
            pass

def renderizar_camas():
    st.info("Gestão de Camas ativa.")

def renderizar_colaboradores():
    aba_cad_colab, aba_cons_colab = st.tabs(["➕ Cadastrar Colaborador", "📋 Consultar, Editar ou Excluir"])

    with aba_cad_colab:
        with st.form("form_cad_colab", clear_on_submit=True):
            c_nome = st.text_input("Nome Completo *")
            c_email = st.text_input("E-mail de Acesso ao Sistema *").strip().lower()
            c_cargo = st.selectbox("Função / Cargo", ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"])
            c_tel = st.text_input("Telefone de Contato")

            st.markdown("---")
            st.markdown("##### ⏰ Janela de Acesso Permitido")
            c_restringir = st.checkbox("Restringir horário de login deste colaborador?", value=False)
            
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                c_h_inicio = st.time_input("Entrada Permitida", value=time(8, 0), step=1800)
            with col_h2:
                c_h_fim = st.time_input("Saída Permitida", value=time(17, 0), step=1800)

            if st.form_submit_button("Salvar Colaborador", use_container_width=True):
                if not c_nome or not c_email:
                    st.error("Nome e E-mail são obrigatórios.")
                else:
                    try:
                        db.supabase.table("colaboradores").insert({
                            "nome": c_nome,
                            "email": c_email,
                            "cargo": c_cargo,
                            "telefone": c_tel,
                            "status": "Ativo",
                            "restringir_horario": c_restringir,
                            "horario_inicio": c_h_inicio.strftime("%H:%M:%S"),
                            "horario_fim": c_h_fim.strftime("%H:%M:%S")
                        }).execute()
                        db.notificar_sucesso("Colaborador cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar colaborador no banco: {e}")

    with aba_cons_colab:
        try:
            res_col = db.supabase.table("colaboradores").select("*").order("nome").execute()
            lista_col = res_col.data or []
        except Exception as e:
            st.error(f"Erro ao buscar colaboradores: {e}")
            lista_col = []

        if not lista_col:
            st.info("Nenhum colaborador cadastrado.")
        else:
            opcoes_dropdown = ["-- Selecione um Colaborador na Lista --"] + [
                f"{c['nome']} ({c.get('cargo', 'Geral')}) - {c.get('email') or 'sem e-mail'}" for c in lista_col
            ]
            
            escolha = st.selectbox("Escolha o colaborador para gerenciar:", opcoes_dropdown)

            if escolha != "-- Selecione um Colaborador na Lista --":
                idx = opcoes_dropdown.index(escolha) - 1
                colab = lista_col[idx]
                colab_id = colab["id"]

                st.markdown("---")
                with st.form(f"form_editar_colab_{colab_id}"):
                    st.markdown(f"#### ✏️ Editando: **{colab.get('nome')}**")
                    
                    e_nome = st.text_input("Nome", value=colab.get("nome", ""))
                    e_email = st.text_input("E-mail de Acesso", value=colab.get("email") or "").strip().lower()
                    
                    cargos_opcoes = ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"]
                    idx_cargo = cargos_opcoes.index(colab.get("cargo")) if colab.get("cargo") in cargos_opcoes else 0
                    e_cargo = st.selectbox("Função / Cargo", cargos_opcoes, index=idx_cargo)
                    
                    e_tel = st.text_input("Telefone", value=colab.get("telefone") or "")
                    
                    status_opcoes = ["Ativo", "Inativo"]
                    idx_status = 0 if colab.get("status") == "Ativo" else 1
                    e_status = st.selectbox("Situação", status_opcoes, index=idx_status)

                    st.markdown("##### ⏰ Janela de Acesso Permitido")
                    e_restringir = st.checkbox("Restringir horário de login?", value=bool(colab.get("restringir_horario", False)))

                    h_ini_val = time(8, 0)
                    if colab.get("horario_inicio"):
                        try:
                            h_ini_val = datetime.strptime(str(colab["horario_inicio"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    h_fim_val = time(17, 0)
                    if colab.get("horario_fim"):
                        try:
                            h_fim_val = datetime.strptime(str(colab["horario_fim"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    col_eh1, col_eh2 = st.columns(2)
                    with col_eh1:
                        e_h_inicio = st.time_input("Entrada Permitida", value=h_ini_val, step=1800, key=f"ini_{colab_id}")
                    with col_eh2:
                        e_h_fim = st.time_input("Saída Permitida", value=h_fim_val, step=1800, key=f"fim_{colab_id}")

                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        if not e_nome or not e_email:
                            st.error("Nome e E-mail são obrigatórios.")
                        else:
                            db.supabase.table("colaboradores").update({
                                "nome": e_nome,
                                "email": e_email,
                                "cargo": e_cargo,
                                "telefone": e_tel,
                                "status": e_status,
                                "restringir_horario": e_restringir,
                                "horario_inicio": e_h_inicio.strftime("%H:%M:%S"),
                                "horario_fim": e_h_fim.strftime("%H:%M:%S")
                            }).eq("id", colab_id).execute()
                            db.notificar_sucesso("Colaborador atualizado com sucesso!")
                            st.rerun()

                st.markdown("---")
                with st.expander("🗑️ Zona de Perigo: Excluir este Colaborador", expanded=False):
                    st.warning(f"Tem certeza de que deseja remover permanentemente **{colab.get('nome')}**?")
                    confirma_exclusao = st.checkbox("Sim, confirmo a exclusão definitiva", key=f"chk_del_{colab_id}")
                    
                    if st.button("Excluir Colaborador Permanentemente", type="primary", use_container_width=True, key=f"btn_del_{colab_id}"):
                        if not confirma_exclusao:
                            st.error("Marque a caixa de confirmação acima para autorizar a exclusão.")
                        else:
                            db.supabase.table("colaboradores").delete().eq("id", colab_id).execute()
                            db.notificar_sucesso(f"Colaborador {colab.get('nome')} excluído com sucesso!")
                            st.rerun()

def renderizar_prestadores():
    st.info("Módulo de prestadores ativo.")