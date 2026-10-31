import re
import urllib.parse
from datetime import datetime, date
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

    # =========================================================================
    # ABA 1: NOVO CADASTRO COM CONFORMIDADE ECA / FNRH
    # =========================================================================
    with aba_cad:
        st.subheader("Novo Cadastro de Hóspede")

        st.markdown("##### 1. Dados Pessoais & Faixa Etária")
        col_p1, col_p2, col_p3 = st.columns([2, 1.2, 1])
        with col_p1:
            nome = st.text_input("Nome Completo:", key="cad_h_nome")
        with col_p2:
            data_nasc = st.date_input(
                "Data de Nascimento:",
                value=date(1995, 1, 1),
                min_value=date(1910, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
                key="cad_h_nasc"
            )
        with col_p3:
            genero = st.selectbox("Gênero:", ["Não informado", "Feminino", "Masculino", "Outro"], key="cad_h_gen")

        # Trava legal para menores de 18 anos (Art. 82 do ECA)
        idade_calculada = calcular_idade(data_nasc)
        responsavel_menor = None
        is_menor = (idade_calculada is not None and idade_calculada < 18)

        if is_menor:
            st.markdown(
                f"""
                <div style='background-color:#fee2e2; border:2px solid #ef4444; border-radius:8px; padding:12px; margin-bottom:12px;'>
                    <b style='color:#b91c1c; font-size:1rem;'>🚨 ATENÇÃO: Hóspede Menor de Idade ({idade_calculada} anos)</b>
                    <p style='color:#7f1d1d; font-size:0.86rem; margin:4px 0 0 0;'>
                        De acordo com o <b>Artigo 82 do Estatuto da Criança e do Adolescente (Lei nº 8.069/1990)</b>, é proibida a hospedagem de menor desacompanhado dos pais ou sem autorização expressa escrita/judicial.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
            responsavel_menor = st.text_input(
                "Nome Completo e Documento do Responsável / Termo de Autorização (Obrigatório):",
                placeholder="Ex: Acompanhado pela mãe Maria Silva (CPF 000.000.000-00) ou Autorização com firma reconhecida anexada",
                key="cad_h_resp_menor"
            )
        else:
            st.caption(f"Idade apurada: **{idade_calculada} anos** (Maior de idade)")

        st.markdown("##### 2. Documentação e Contato")
        col_d1, col_d2, col_d3 = st.columns([1, 1.2, 1.2])
        with col_d1:
            nacionalidade = st.selectbox("Nacionalidade:", ["Brasileira", "Estrangeira"], key="cad_h_nac")
        with col_d2:
            if nacionalidade == "Brasileira":
                cpf = st.text_input("CPF (Obrigatório para brasileiros):", key="cad_h_cpf")
                passaporte = ""
            else:
                cpf = ""
                passaporte = st.text_input("Passaporte ou RNE (Estrangeiros):", key="cad_h_pass")
        with col_d3:
            telefone = st.text_input("Telefone / WhatsApp (com DDD):", key="cad_h_tel")

        col_c1, col_c2 = st.columns([1.5, 1])
        with col_c1:
            email = st.text_input("E-mail de Contato:", key="cad_h_email")
        with col_c2:
            pais_origem = st.text_input("País de Residência:", value="Brasil" if nacionalidade == "Brasileira" else "", key="cad_h_pais")

        st.markdown("##### 3. Residência Permanente (Origem - FNRH)")
        col_cid, col_uf = st.columns([2, 1])
        with col_cid:
            cidade_origem = st.text_input("Cidade de Origem:", placeholder="Ex: Porto Alegre", key="cad_h_cid")
        with col_uf:
            if nacionalidade == "Brasileira":
                estado_origem = st.selectbox("Estado (UF):", UFS_BRASIL, index=UFS_BRASIL.index("RS") if "RS" in UFS_BRASIL else 0, key="cad_h_uf")
            else:
                estado_origem = st.text_input("Estado / Província:", key="cad_h_uf_estrang")

        observacoes = st.text_area("Observações Adicionais / Preferências:", key="cad_h_obs")

        st.markdown("##### 📸 Foto do Hóspede")
        origem_foto = st.radio("Origem da Imagem:", ["Nenhuma", "Carregar Arquivo", "Tirar Foto com a Câmera"], horizontal=True, key="cad_h_origem_foto")
        
        arquivo_foto_cad = None
        if origem_foto == "Carregar Arquivo":
            arquivo_foto_cad = st.file_uploader("Selecione a foto (PNG ou JPG):", type=["png", "jpg", "jpeg"], key="cad_h_upload")
        elif origem_foto == "Tirar Foto com a Câmera":
            arquivo_foto_cad = st.camera_input("Capture a imagem", key="cad_h_camera")

        st.markdown("##### 🛡️ Conformidade LGPD")
        aceite_lgpd = st.checkbox(
            "Declaro ciência do titular quanto ao tratamento de dados pessoais para controle de segurança e exigências do Ministério do Turismo (Lei 13.709/2018).",
            value=True,
            key="cad_h_lgpd"
        )

        if st.button("Salvar Cadastro do Hóspede", type="primary", use_container_width=True, key="btn_salvar_novo_hospede"):
            if not nome:
                st.error("O campo Nome Completo é obrigatório.")
            elif nacionalidade == "Brasileira" and not validar_cpf(cpf):
                st.error("CPF inválido! Verifique a digitação.")
            elif nacionalidade == "Estrangeira" and not passaporte:
                st.error("Informe o Passaporte ou RNE para hóspedes estrangeiros.")
            elif is_menor and not (responsavel_menor and responsavel_menor.strip()):
                st.error("Para menores de 18 anos, é obrigatório registrar o nome e documento do responsável legal ou autorização legal.")
            elif not aceite_lgpd:
                st.error("O aceite do termo LGPD é obrigatório para cumprimento legal.")
            else:
                cpf_limpo = re.sub(r'\D', '', cpf) if cpf else None
                doc_unificado = cpf_limpo if nacionalidade == "Brasileira" else passaporte
                foto_b64 = converter_para_base64(arquivo_foto_cad) if arquivo_foto_cad else None
                
                dados_hosp = {
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
                }
                db.supabase.table("hospedes").insert(dados_hosp).execute()
                db.notificar_sucesso(f"Hóspede {nome} cadastrado com sucesso!")
                st.rerun()

    # =========================================================================
    # ABA 2: CONSULTA, EDIÇÃO E EXCLUSÃO
    # =========================================================================
    with aba_cons:
        try:
            res_h = db.supabase.table("hospedes").select("*").execute()
            lista_h = res_h.data or []
            if not lista_h:
                st.info("Nenhum hóspede cadastrado no sistema.")
            else:
                col_exp_t, col_exp_csv, col_exp_pdf = st.columns([2, 1, 1])
                with col_exp_t:
                    st.caption(f"👥 Total cadastrado: **{len(lista_h)} hóspede(s)**")
                with col_exp_csv:
                    df_h_exp = pd.DataFrame(lista_h).drop(columns=["id", "foto"], errors="ignore")
                    st.download_button(
                        label="📥 Baixar CSV (Excel)",
                        data=gerar_csv(df_h_exp),
                        file_name="hospedes.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_exp_pdf:
                    cols_pdf = ["nome", "telefone", "documento", "cidade_origem", "estado_origem"]
                    pdf_h_bytes = gerar_pdf_tabela("Cadastro Geral de Hóspedes", cols_pdf, lista_h, orientacao="L")
                    st.download_button(
                        label="📕 Baixar PDF",
                        data=pdf_h_bytes,
                        file_name="hospedes.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.markdown("---")

                h_labels = ["-- Selecione o Hóspede --"]
                for h in lista_h:
                    doc = h.get('cpf') or h.get('documento') if h.get('nacionalidade') == "Brasileira" else h.get('passaporte_rne') or h.get('documento') or 'Não informado'
                    tag_anon = " (ANONIMIZADO)" if h.get("anonimizado") else ""
                    h_labels.append(f"{h['nome']} (Doc: {doc}){tag_anon}")

                h_escolhido = st.selectbox("Buscar Hóspede para Consultar ou Editar:", h_labels)

                if h_escolhido != "-- Selecione o Hóspede --":
                    idx = h_labels.index(h_escolhido) - 1
                    h_obj = lista_h[idx]

                    # Atalho Direto WhatsApp
                    tel_limpo = re.sub(r'\D', '', str(h_obj.get("telefone", "")))
                    if tel_limpo:
                        msg_wpp = urllib.parse.quote(f"Olá {h_obj['nome']}! Entramos em contato a partir da recepção do hostel.")
                        link_wpp = f"https://wa.me/55{tel_limpo}?text={msg_wpp}"
                        st.link_button("📲 Chamar no WhatsApp Oficial", link_wpp, use_container_width=True)

                    col_dados, col_foto_view = st.columns([2, 1])
                    with col_foto_view:
                        foto_cad = h_obj.get("foto")
                        if foto_cad:
                            st.image(foto_cad, caption="Foto do Hóspede", width=180)
                        else:
                            st.info("Sem foto registrada.")

                    with col_dados:
                        e_nome = st.text_input("Nome Completo:", value=h_obj.get("nome", ""), key="edit_h_nome")
                        
                        col_en1, col_en2 = st.columns(2)
                        with col_en1:
                            dt_nasc_salva = None
                            if h_obj.get("data_nascimento"):
                                try:
                                    dt_nasc_salva = datetime.strptime(str(h_obj.get("data_nascimento")), "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            
                            e_data_nasc = st.date_input(
                                "Data de Nascimento:",
                                value=dt_nasc_salva or date(1995, 1, 1),
                                min_value=date(1910, 1, 1),
                                max_value=date.today(),
                                format="DD/MM/YYYY",
                                key="edit_h_nasc"
                            )
                        with col_en2:
                            gens = ["Não informado", "Feminino", "Masculino", "Outro"]
                            gen_atual = h_obj.get("genero", "Não informado")
                            idx_g = gens.index(gen_atual) if gen_atual in gens else 0
                            e_genero = st.selectbox("Gênero:", gens, index=idx_g, key="edit_h_gen")

                        e_idade = calcular_idade(e_data_nasc)
                        e_is_menor = (e_idade is not None and e_idade < 18)
                        e_resp_menor = h_obj.get("responsavel_menor")

                        if e_is_menor:
                            st.warning(f"⚠️ Hóspede Menor de Idade ({e_idade} anos) — ECA Art. 82")
                            e_resp_menor = st.text_input("Responsável Legal / Autorização:", value=e_resp_menor or "", key="edit_h_resp_menor")
                        else:
                            st.caption(f"Idade apurada: **{e_idade} anos** (Maior de idade)")

                        col_ed1, col_ed2 = st.columns(2)
                        with col_ed1:
                            e_tel = st.text_input("Telefone:", value=h_obj.get("telefone", ""), key="edit_h_tel")
                        with col_ed2:
                            e_email = st.text_input("E-mail:", value=h_obj.get("email", ""), key="edit_h_email")

                        col_edoc1, col_edoc2 = st.columns(2)
                        with col_edoc1:
                            nac_atual = h_obj.get("nacionalidade", "Brasileira")
                            e_nac = st.selectbox("Nacionalidade:", ["Brasileira", "Estrangeira"], index=0 if nac_atual == "Brasileira" else 1, key="edit_h_nac")
                        with col_edoc2:
                            e_cpf = st.text_input("CPF:", value=h_obj.get("cpf") or h_obj.get("documento") or "", key="edit_h_cpf")
                            e_pass = st.text_input("Passaporte / RNE:", value=h_obj.get("passaporte_rne") or h_obj.get("documento") or "", key="edit_h_pass")

                        col_eloc1, col_eloc2, col_eloc3 = st.columns([1.5, 1, 1])
                        with col_eloc1:
                            e_cid = st.text_input("Cidade de Origem:", value=h_obj.get("cidade_origem", ""), key="edit_h_cid")
                        with col_eloc2:
                            uf_salva = h_obj.get("estado_origem", "RS")
                            idx_uf = UFS_BRASIL.index(uf_salva) if uf_salva in UFS_BRASIL else 0
                            e_uf = st.selectbox("Estado (UF):", UFS_BRASIL, index=idx_uf, key="edit_h_uf")
                        with col_eloc3:
                            e_pais = st.text_input("País:", value=h_obj.get("pais_origem", "Brasil"), key="edit_h_pais")

                        e_obs = st.text_area("Observações:", value=h_obj.get("observacoes", ""), key="edit_h_obs")

                    st.markdown("##### 📸 Alterar Foto")
                    opcao_nova_foto = st.radio("Opção:", ["Manter a atual", "Carregar Arquivo", "Tirar Foto", "Remover Foto"], horizontal=True, key="edit_h_opcao_foto")
                    
                    nova_foto_buffer = None
                    if opcao_nova_foto == "Carregar Arquivo":
                        nova_foto_buffer = st.file_uploader("Arquivo", type=["png", "jpg", "jpeg"], key="edit_h_upload")
                    elif opcao_nova_foto == "Tirar Foto":
                        nova_foto_buffer = st.camera_input("Capturar", key="edit_h_camera")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Atualizar Cadastro", type="primary", use_container_width=True, key="btn_atualizar_hosp"):
                            if e_nac == "Brasileira" and e_cpf and not validar_cpf(e_cpf):
                                st.error("CPF informado é inválido.")
                            elif e_is_menor and not (e_resp_menor and e_resp_menor.strip()):
                                st.error("Informe o responsável legal para hóspedes menores de idade.")
                            else:
                                e_cpf_limpo = re.sub(r'\D', '', e_cpf) if e_cpf else None
                                e_doc_unificado = e_cpf_limpo if e_nac == "Brasileira" else e_pass
                                foto_final = foto_cad
                                if opcao_nova_foto == "Remover Foto":
                                    foto_final = None
                                elif opcao_nova_foto in ["Carregar Arquivo", "Tirar Foto"] and nova_foto_buffer:
                                    foto_final = converter_para_base64(nova_foto_buffer)

                                db.supabase.table("hospedes").update({
                                    "nome": e_nome,
                                    "data_nascimento": e_data_nasc.isoformat(),
                                    "genero": e_genero,
                                    "documento": e_doc_unificado,
                                    "email": e_email,
                                    "telefone": e_tel,
                                    "nacionalidade": e_nac,
                                    "cpf": e_cpf_limpo,
                                    "passaporte_rne": e_pass,
                                    "cidade_origem": e_cid,
                                    "estado_origem": e_uf,
                                    "pais_origem": e_pais,
                                    "responsavel_menor": e_resp_menor if e_is_menor else None,
                                    "observacoes": e_obs,
                                    "foto": foto_final
                                }).eq("id", h_obj["id"]).execute()
                                db.notificar_sucesso("Cadastro do hóspede atualizado com sucesso!")
                                st.rerun()

                    with c2:
                        if st.button("Excluir Cadastro", use_container_width=True, key="btn_excluir_hosp"):
                            db.supabase.table("hospedes").delete().eq("id", h_obj["id"]).execute()
                            db.notificar_sucesso("Hóspede excluído!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar hóspedes: {e}")

def renderizar_empresas():
    aba_cad_emp, aba_cons_emp = st.tabs(["Cadastrar Empresa", "Consultar / Editar / Excluir"])

    with aba_cad_emp:
        with st.form("form_cad_empresa"):
            emp_razao = st.text_input("Razão Social / Nome Fantasia")
            emp_cnpj = st.text_input("CNPJ (Com ou sem pontuação)")
            emp_email = st.text_input("E-mail para Faturamento")
            emp_telefone = st.text_input("Telefone de Contato")
            emp_obs = st.text_area("Observações Adicionais")

            if st.form_submit_button("Salvar Empresa Parceira"):
                cnpj_limpo = re.sub(r'\D', '', emp_cnpj)
                if not emp_razao:
                    st.error("A Razão Social é obrigatória.")
                elif not validar_cnpj(cnpj_limpo):
                    st.error("CNPJ inválido! Verifique a digitação.")
                else:
                    try:
                        db.supabase.table("empresas").insert({
                            "razao_social": emp_razao, "cnpj": cnpj_limpo, "email": emp_email,
                            "telefone": emp_telefone, "observacoes": emp_obs
                        }).execute()
                        db.notificar_sucesso("Empresa parceira cadastrada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    with aba_cons_emp:
        try:
            res_emp = db.supabase.table("empresas").select("*").execute()
            lista_emp = res_emp.data or []
            if not lista_emp:
                st.info("Nenhuma empresa parceira cadastrada.")
            else:
                emp_labels = ["-- Selecione a Empresa --"] + [f"{e['razao_social']} (CNPJ: {e['cnpj']})" for e in lista_emp]
                emp_escolhida = st.selectbox("Buscar Empresa:", emp_labels)

                if emp_escolhida != "-- Selecione a Empresa --":
                    idx = emp_labels.index(emp_escolhida) - 1
                    e_obj = lista_emp[idx]

                    with st.form("form_edit_empresa"):
                        edit_razao = st.text_input("Razão Social", value=e_obj.get("razao_social", ""))
                        edit_cnpj = st.text_input("CNPJ", value=e_obj.get("cnpj", ""))
                        edit_email = st.text_input("E-mail", value=e_obj.get("email", ""))
                        edit_telefone = st.text_input("Telefone", value=e_obj.get("telefone", ""))
                        edit_obs = st.text_area("Observações", value=e_obj.get("observacoes", ""))

                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Atualizar Informações"):
                            cnpj_edit_limpo = re.sub(r'\D', '', edit_cnpj)
                            if not validar_cnpj(cnpj_edit_limpo):
                                st.error("CNPJ informado é inválido.")
                            else:
                                db.supabase.table("empresas").update({
                                    "razao_social": edit_razao, "cnpj": cnpj_edit_limpo, "email": edit_email,
                                    "telefone": edit_telefone, "observacoes": edit_obs
                                }).eq("id", e_obj["id"]).execute()
                                db.notificar_sucesso("Empresa atualizada!")
                                st.rerun()

                        if c2.form_submit_button("Excluir Empresa"):
                            db.supabase.table("empresas").delete().eq("id", e_obj["id"]).execute()
                            db.notificar_sucesso("Empresa removida!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

def renderizar_quartos():
    aba_qc, aba_qe = st.tabs(["Cadastrar Quarto", "Editar / Excluir Quarto"])

    with aba_qc:
        with st.form("form_cad_quarto"):
            col_q1, col_q2 = st.columns([2, 1])
            with col_q1:
                q_nome = st.text_input("Identificação do Quarto (ex: 101, Suíte Master, Dormitório 6)")
                q_ala = st.text_input("Ala / Andar / Setor (ex: Térreo, Ala Norte, Anexo)")
            with col_q2:
                q_preco_base = st.number_input("Preço Base da Diária (R$):", min_value=0.0, value=80.0, step=5.0, format="%.2f")
                q_perfil = st.selectbox("Perfil de Acomodação:", ["Misto", "Feminino", "Masculino", "Privativo (Casal/Família)"])

            col_cb1, col_cb2 = st.columns(2)
            with col_cb1:
                q_ar = st.checkbox("❄️ Equipado com Ar-Condicionado (Split)", value=False)
            with col_cb2:
                q_pcd = st.checkbox("♿ Acomodação com Acessibilidade (PCD)", value=False)

            q_desc = st.text_area("Descrição Adicional:")

            if st.form_submit_button("Salvar Quarto", type="primary", use_container_width=True):
                if not q_nome:
                    st.error("O nome ou identificação do quarto é obrigatório.")
                else:
                    db.supabase.table("quartos").insert({
                        "nome": q_nome, "ala": q_ala, "perfil": q_perfil,
                        "ar_condicionado": q_ar, "pcd": q_pcd,
                        "preco_base": q_preco_base, "descricao": q_desc
                    }).execute()
                    db.notificar_sucesso(f"Quarto {q_nome} cadastrado!")
                    st.rerun()

    with aba_qe:
        try:
            res_q = db.supabase.table("quartos").select("*").execute()
            lista_q = res_q.data or []
            if not lista_q:
                st.info("Nenhum quarto cadastrado.")
            else:
                lista_q_ordenados = ordenar_natural(lista_q, "nome")
                q_labels = ["-- Selecione o Quarto --"]
                for q in lista_q_ordenados:
                    ar_txt = "❄️ Ar" if q.get("ar_condicionado") else "🌀 Vent"
                    p_txt = f"R$ {float(q.get('preco_base') or 80):.2f}"
                    q_labels.append(f"Quarto {q['nome']} ({q.get('ala', 'Geral')} | {ar_txt} | {p_txt})")

                q_selecionado = st.selectbox("Buscar Quarto para Editar:", q_labels)

                if q_selecionado != "-- Selecione o Quarto --":
                    idx_q = q_labels.index(q_selecionado) - 1
                    q_obj = lista_q_ordenados[idx_q]

                    with st.form("form_edit_quarto"):
                        col_eq1, col_eq2 = st.columns([2, 1])
                        with col_eq1:
                            eq_nome = st.text_input("Nome / Número", value=q_obj.get("nome", ""))
                            eq_ala = st.text_input("Ala / Setor", value=q_obj.get("ala", ""))
                        with col_eq2:
                            eq_preco_base = st.number_input("Preço Base (R$):", min_value=0.0, value=float(q_obj.get("preco_base") or 80.0), step=5.0, format="%.2f")
                            perfis = ["Misto", "Feminino", "Masculino", "Privativo (Casal/Família)"]
                            p_atual = q_obj.get("perfil", "Misto")
                            idx_p = perfis.index(p_atual) if p_atual in perfis else 0
                            eq_perfil = st.selectbox("Perfil", perfis, index=idx_p)

                        col_ecb1, col_ecb2 = st.columns(2)
                        with col_ecb1:
                            eq_ar = st.checkbox("❄️ Equipado com Ar-Condicionado", value=bool(q_obj.get("ar_condicionado", False)))
                        with col_ecb2:
                            eq_pcd = st.checkbox("♿ Acessibilidade (PCD)", value=bool(q_obj.get("pcd", False)))

                        eq_desc = st.text_area("Descrição", value=q_obj.get("descricao", ""))

                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Atualizar Quarto", type="primary"):
                            db.supabase.table("quartos").update({
                                "nome": eq_nome, "ala": eq_ala, "perfil": eq_perfil,
                                "ar_condicionado": eq_ar, "pcd": eq_pcd,
                                "preco_base": eq_preco_base, "descricao": eq_desc
                            }).eq("id", q_obj["id"]).execute()
                            db.notificar_sucesso("Quarto atualizado!")
                            st.rerun()
                        if c2.form_submit_button("Excluir Quarto"):
                            db.supabase.table("quartos").delete().eq("id", q_obj["id"]).execute()
                            db.notificar_sucesso("Quarto excluído!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro ao gerenciar quartos: {e}")

def renderizar_camas():
    aba_cc, aba_ce = st.tabs(["Cadastrar Cama / Leito", "Gerenciar / Alterar Valores dos Leitos"])

    with aba_cc:
        try:
            res_quartos = db.supabase.table("quartos").select("*").execute()
            quartos_lista = res_quartos.data or []
            if not quartos_lista:
                st.warning("Cadastre quartos antes de adicionar camas.")
            else:
                quartos_lista_ord = ordenar_natural(quartos_lista, "nome")
                with st.form("form_cad_cama"):
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        q_opcoes = {f"Quarto {q['nome']} (Base: R$ {float(q.get('preco_base') or 80):.2f})": q for q in quartos_lista_ord}
                        quarto_sel_str = st.selectbox("Quarto de Destino:", list(q_opcoes.keys()))
                        quarto_escolhido = q_opcoes[quarto_sel_str]
                        c_numero = st.text_input("Identificação da Cama (ex: 1, 2, Cama A, Superior 3)")

                    with col_c2:
                        tipos_leito = [
                            "Beliche - Inferior (Mais acessível/concorrida)",
                            "Beliche - Superior",
                            "Cama de Solteiro Tradicional",
                            "Cama de Casal",
                            "Sofá-Cama / Extra"
                        ]
                        c_tipo = st.selectbox("Tipo / Posição do Leito:", tipos_leito)
                        preco_sugerido = float(quarto_escolhido.get("preco_base") or 80.0)
                        c_preco_individual = st.number_input(
                            "Preço Individual Desta Cama (R$):",
                            min_value=0.0,
                            value=preco_sugerido,
                            step=5.0,
                            format="%.2f"
                        )

                    c_status = st.selectbox("Situação Inicial:", ["Disponível", "Limpeza Pendente", "Ocupado"])
                    c_toalha = st.checkbox("Equipada com toalha de banho?", value=False)

                    if st.form_submit_button("Salvar Cama / Leito", type="primary", use_container_width=True):
                        if not c_numero:
                            st.error("Informe a identificação da cama.")
                        else:
                            db.supabase.table("camas").insert({
                                "quarto_id": quarto_escolhido["id"],
                                "numero": c_numero,
                                "tipo_leito": c_tipo.split(" (")[0],
                                "preco_diaria": c_preco_individual,
                                "status": c_status,
                                "toalha_colocada": c_toalha
                            }).execute()
                            db.notificar_sucesso(f"Cama {c_numero} salva com sucesso!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

    with aba_ce:
        try:
            camas_todas = db.buscar_camas_com_quartos()
            if not camas_todas:
                st.info("Nenhuma cama cadastrada.")
            else:
                camas_ord = ordenar_natural(camas_todas, "numero")
                c_labels = ["-- Selecione a Cama --"]
                for c in camas_ord:
                    if c.get("quartos"):
                        preco_c = float(c.get("preco_diaria") or c["quartos"].get("preco_base") or 80.0)
                        c_labels.append(f"Quarto {c['quartos']['nome']} — Cama {c['numero']} [R$ {preco_c:.2f} | {c.get('status')}]")

                c_selecionada = st.selectbox("Buscar Cama:", c_labels)

                if c_selecionada != "-- Selecione a Cama --":
                    idx_c = c_labels.index(c_selecionada) - 1
                    c_obj = camas_ord[idx_c]

                    with st.form("form_edit_cama"):
                        col_ec1, col_ec2 = st.columns(2)
                        with col_ec1:
                            novo_num = st.text_input("Identificação da Cama", value=c_obj.get("numero", ""))
                            tipos_leito = ["Beliche - Inferior", "Beliche - Superior", "Cama de Solteiro Tradicional", "Cama de Casal", "Sofá-Cama / Extra"]
                            t_atual = c_obj.get("tipo_leito", "Beliche - Inferior")
                            idx_t = tipos_leito.index(t_atual) if t_atual in tipos_leito else 0
                            novo_tipo = st.selectbox("Tipo de Leito", tipos_leito, index=idx_t)
                        with col_ec2:
                            val_atual = float(c_obj.get("preco_diaria") or (c_obj.get("quartos", {}).get("preco_base") if c_obj.get("quartos") else 80.0))
                            novo_preco = st.number_input("Preço Individual Deste Leito (R$):", min_value=0.0, value=val_atual, step=5.0, format="%.2f")
                            status_opcoes = ["Disponível", "Limpeza Pendente", "Ocupado"]
                            novo_status = st.selectbox("Situação", status_opcoes, index=status_opcoes.index(c_obj.get("status", "Disponível")))

                        novo_toalha = st.checkbox("Equipada com toalha?", value=bool(c_obj.get("toalha_colocada", False)))

                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Atualizar Informações", type="primary"):
                            db.supabase.table("camas").update({
                                "numero": novo_num, "tipo_leito": novo_tipo,
                                "preco_diaria": novo_preco, "status": novo_status,
                                "toalha_colocada": novo_toalha
                            }).eq("id", c_obj["id"]).execute()
                            db.notificar_sucesso("Cama atualizada!")
                            st.rerun()
                        if c2.form_submit_button("Excluir Cama"):
                            db.supabase.table("camas").delete().eq("id", c_obj["id"]).execute()
                            db.notificar_sucesso("Cama removida!")
                            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

def renderizar_colaboradores():
    aba_cad_colab, aba_cons_colab = st.tabs(["Cadastrar Colaborador", "Consultar / Editar Equipe"])

    with aba_cad_colab:
        with st.form("form_cad_colab"):
            c_nome = st.text_input("Nome Completo")
            c_nac = st.selectbox("Nacionalidade", ["Brasileira", "Estrangeira"])
            c_cpf = st.text_input("CPF") if c_nac == "Brasileira" else ""
            c_pass = st.text_input("Passaporte / RNE") if c_nac != "Brasileira" else ""
            c_cargo = st.selectbox("Função / Cargo", ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"])
            c_turno = st.selectbox("Turno de Trabalho", ["Manhã", "Tarde", "Noite", "Madrugada", "Integral"])
            c_tel = st.text_input("Telefone de Contato")

            if st.form_submit_button("Salvar Colaborador"):
                if not c_nome:
                    st.error("O nome do colaborador é obrigatório.")
                elif c_nac == "Brasileira" and not validar_cpf(c_cpf):
                    st.error("CPF inválido.")
                else:
                    cpf_limpo = re.sub(r'\D', '', c_cpf) if c_cpf else None
                    db.supabase.table("colaboradores").insert({
                        "nome": c_nome, "nacionalidade": c_nac, "cpf": cpf_limpo,
                        "passaporte_rne": c_pass if c_pass else None, "cargo": c_cargo,
                        "turno": c_turno, "telefone": c_tel, "status": "Ativo"
                    }).execute()
                    db.notificar_sucesso("Colaborador cadastrado!")
                    st.rerun()

    with aba_cons_colab:
        res_col = db.supabase.table("colaboradores").select("*").execute()
        lista_col = res_col.data or []
        if not lista_col:
            st.info("Nenhum colaborador cadastrado.")
        else:
            col_labels = ["-- Selecione o Colaborador --"] + [f"{c['nome']} — {c['cargo']}" for c in lista_col]
            col_escolhido = st.selectbox("Buscar Colaborador:", col_labels)
            if col_escolhido != "-- Selecione o Colaborador --":
                idx = col_labels.index(col_escolhido) - 1
                col_obj = lista_col[idx]
                with st.form("form_edit_colab"):
                    e_nome = st.text_input("Nome", value=col_obj.get("nome", ""))
                    e_cargo = st.selectbox("Cargo", ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"], index=0)
                    e_status = st.selectbox("Situação", ["Ativo", "Inativo"], index=0 if col_obj.get("status") == "Ativo" else 1)
                    if st.form_submit_button("Atualizar"):
                        db.supabase.table("colaboradores").update({"nome": e_nome, "cargo": e_cargo, "status": e_status}).eq("id", col_obj["id"]).execute()
                        db.notificar_sucesso("Colaborador atualizado!")
                        st.rerun()

def renderizar_prestadores():
    res_cat_serv = db.supabase.table("categorias_servicos").select("nome").order("nome").execute()
    cat_servicos_lista = [c["nome"] for c in res_cat_serv.data] if res_cat_serv.data else ["Sem categoria"]
    
    aba_cad, aba_cons, aba_cat = st.tabs(["Cadastrar Prestador", "Consultar / Avaliar", "Configurar Categorias"])
    with aba_cad:
        with st.form("form_cad_prestador"):
            p_nome = st.text_input("Nome ou Razão Social")
            p_cat = st.selectbox("Categoria", cat_servicos_lista)
            p_tel = st.text_input("Telefone")
            p_aval = st.slider("Classificação (1 a 5)", 1, 5, 5)
            if st.form_submit_button("Salvar"):
                if p_nome:
                    db.supabase.table("prestadores").insert({"nome_razao": p_nome, "categoria_servico": p_cat, "telefone": p_tel, "avaliacao": p_aval}).execute()
                    db.notificar_sucesso("Prestador cadastrado!")
                    st.rerun()

    with aba_cons:
        res_prest = db.supabase.table("prestadores").select("*").execute()
        for p in (res_prest.data or []):
            st.write(f"• **{p['nome_razao']}** ({p.get('categoria_servico')}) — {'⭐'*p.get('avaliacao', 5)} — Tel: {p.get('telefone', 'N/D')}")

    with aba_cat:
        nova_c = st.text_input("Nova Categoria de Serviço (ex: Encanador, Lavanderia)")
        if st.button("Adicionar Categoria de Serviço"):
            if nova_c:
                db.supabase.table("categorias_servicos").insert({"nome": nova_c}).execute()
                db.notificar_sucesso("Categoria adicionada!")
                st.rerun()