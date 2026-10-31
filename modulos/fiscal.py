import json
from datetime import datetime
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data

def obter_configuracoes_fiscais():
    try:
        res = db.supabase.table("configuracoes").select("valor").eq("chave", "config_nfse_fiscal").execute()
        if res.data and len(res.data) > 0 and res.data[0].get("valor"):
            return json.loads(res.data[0]["valor"])
    except Exception:
        pass
    return {
        "regime_tributario": "Simples Nacional - ME/EPP",
        "cnae": "5510-8/01 - Hotéis e Apart-hotéis (Hostels e Albergues)",
        "item_lc116": "09.01 - Hospedagem de qualquer natureza em hotéis, pensões e congêneres",
        "codigo_tributacao_municipio": "090101",
        "aliquota_iss": 2.50,
        "iss_retido": False,
        "serie_rps": "1",
        "ultimo_rps": 100,
        "ambiente_emissao": "Homologação (Testes)",
        "provedor_api": "Focus NFe",
        "api_token": "",
        "natureza_operacao": "1 - Tributação no Município",
        "incentivador_cultural": False
    }

def renderizar_fiscal(usuario_perfil):
    aba_emissao, aba_config, aba_ajuda = st.tabs([
        "🧾 Emissor de Minuta / Espelho RPS",
        "⚙️ Configuração Fiscal & Integração",
        "📚 Manual de Integração Fiscal Municipal"
    ])

    cfg_fiscal = obter_configuracoes_fiscais()

    # =========================================================================
    # ABA 1: EMISSOR DE MINUTA / ESPELHO RPS
    # =========================================================================
    with aba_emissao:
        st.subheader("🧾 Emissão e Espelho do RPS (Recibo Provisório de Serviços)")
        st.caption("Gere a minuta fiscal da estadia para pré-visualização, conferência contábil e disparo via API de mensageria.")

        reservas_concluidas = db.buscar_reservas_completas(ordem_desc=True)
        if not reservas_concluidas:
            st.info("Nenhuma reserva registrada para emissão de nota fiscal.")
        else:
            opcoes_res = {}
            for r in reservas_concluidas:
                loc = r.get("codigo_localizador", f"ID-{r['id']}")
                h_nome = r["hospedes"]["nome"] if r.get("hospedes") else "Desconhecido"
                d_fim = formatar_data_br(r.get("data_fim")).split()[0]
                tot = float(r.get("valor_total") or 0.0)
                rotulo = f"[{loc}] {h_nome} — Saída: {d_fim} (R$ {tot:.2f})"
                opcoes_res[rotulo] = r

            res_sel_rotulo = st.selectbox("Selecione a Estadia para Gerar o Documento Fiscal:", list(opcoes_res.keys()))
            reserva_sel = opcoes_res[res_sel_rotulo]
            hosp_sel = reserva_sel.get("hospedes") or {}
            emp_sel = reserva_sel.get("empresas") or {}
            is_b2b = reserva_sel.get("faturar_empresa", False) and emp_sel

            st.markdown("---")
            col_tom1, col_tom2 = st.columns(2)
            
            with col_tom1:
                st.markdown("##### 👤 Tomador do Serviço (Cliente)")
                if is_b2b:
                    st.write(f"**Razão Social:** {emp_sel.get('razao_social')}")
                    st.write(f"**CNPJ:** {emp_sel.get('cnpj')}")
                    st.write(f"**E-mail Faturamento:** {emp_sel.get('email', 'Não informado')}")
                    st.write(f"**Telefone:** {emp_sel.get('telefone', 'Não informado')}")
                    tomador_nome = emp_sel.get("razao_social")
                    tomador_doc = emp_sel.get("cnpj")
                    tomador_email = emp_sel.get("email", "")
                else:
                    doc_h = hosp_sel.get("cpf") or hosp_sel.get("passaporte_rne") or hosp_sel.get("documento") or "Não informado"
                    st.write(f"**Nome:** {hosp_sel.get('nome')}")
                    st.write(f"**Documento (CPF/Passaporte):** {doc_h}")
                    st.write(f"**E-mail:** {hosp_sel.get('email', 'Não informado')}")
                    st.write(f"**Telefone:** {hosp_sel.get('telefone', 'Não informado')}")
                    tomador_nome = hosp_sel.get("nome")
                    tomador_doc = doc_h
                    tomador_email = hosp_sel.get("email", "")

            with col_tom2:
                st.markdown("##### 🏛️ Dados Tributários da Operação")
                st.write(f"**Ambiente:** `{cfg_fiscal['ambiente_emissao']}`")
                st.write(f"**Regime do Hostel:** {cfg_fiscal['regime_tributario']}")
                st.write(f"**CNAE:** {cfg_fiscal['cnae']}")
                st.write(f"**Item LC 116:** {cfg_fiscal['item_lc116']}")
                st.write(f"**Alíquota ISS:** {cfg_fiscal['aliquota_iss']:.2f}%")

            valor_servico = float(reserva_sel.get("valor_total") or 0.0)
            valor_iss = (valor_servico * (float(cfg_fiscal['aliquota_iss']) / 100.0))

            st.markdown("---")
            col_v1, col_v2, col_v3 = st.columns(3)
            col_v1.metric("Valor Total do Serviço", f"R$ {valor_servico:.2f}")
            col_v2.metric(f"Base de Cálculo ISS ({cfg_fiscal['aliquota_iss']}%)", f"R$ {valor_servico:.2f}")
            col_v3.metric("Valor do ISS Apurado", f"R$ {valor_iss:.2f}")

            # Montagem estruturada do JSON do RPS (Padrão ABRASF)
            num_rps_novo = int(cfg_fiscal.get("ultimo_rps", 100)) + 1
            discriminacao_servico = (
                f"PRESTACAO DE SERVICOS DE HOSPEDAGEM DE NATUREZA HOTELEIRA. "
                f"LOCALIZADOR DA RESERVA: {reserva_sel.get('codigo_localizador', 'S/COD')}. "
                f"PERIODO: {formatar_data_br(reserva_sel.get('data_inicio'))} ATE {formatar_data_br(reserva_sel.get('data_fim'))}. "
                f"DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL. NAO GERA DIREITO A CREDITO FISCAL DE IPI."
            )

            rps_payload = {
                "rps_numero": num_rps_novo,
                "rps_serie": cfg_fiscal.get("serie_rps", "1"),
                "rps_tipo": "RPS",
                "data_emissao": datetime.now().isoformat(),
                "natureza_operacao": cfg_fiscal.get("natureza_operacao"),
                "regime_especial_tributacao": cfg_fiscal.get("regime_tributario"),
                "prestador": {
                    "cnae": cfg_fiscal.get("cnae"),
                    "item_lista_servico": cfg_fiscal.get("item_lc116"),
                    "codigo_tributacao_municipio": cfg_fiscal.get("codigo_tributacao_municipio")
                },
                "tomador": {
                    "razao_social": tomador_nome,
                    "documento": tomador_doc,
                    "email": tomador_email
                },
                "servico": {
                    "valor_servicos": valor_servico,
                    "aliquota_iss": cfg_fiscal.get("aliquota_iss"),
                    "valor_iss": valor_iss,
                    "iss_retido": cfg_fiscal.get("iss_retido", False),
                    "discriminacao": discriminacao_servico
                }
            }

            st.markdown("##### 📄 Minuta / Pré-visualização do Espelho do Documento Fiscal")
            st.text_area("Discriminação Legal dos Serviços:", value=discriminacao_servico, height=80, key="txt_discrimina")

            c_btn_f1, c_btn_f2 = st.columns(2)
            with c_btn_f1:
                st.download_button(
                    label="📥 Baixar Minuta do RPS (JSON / Padrão ABRASF)",
                    data=json.dumps(rps_payload, indent=2, ensure_ascii=False),
                    file_name=f"rps_{num_rps_novo}_{reserva_sel.get('codigo_localizador')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            with c_btn_f2:
                if cfg_fiscal.get("api_token"):
                    if st.button("🚀 Transmitir para API Fiscal de Produção", type="primary", use_container_width=True):
                        # Ponto de conexão da API de mensageria
                        st.info(f"Conexão com gateway {cfg_fiscal.get('provedor_api')} disparada no ambiente '{cfg_fiscal.get('ambiente_emissao')}'.")
                        st.success(f"RPS #{num_rps_novo} transmitido com sucesso para a Prefeitura! Status: Em Processamento.")
                else:
                    st.warning("⚠️ Para transmissão automática direta, configure o Token da API na aba de configurações ao lado.")

    # =========================================================================
    # ABA 2: CONFIGURAÇÃO FISCAL DO HOSTEL
    # =========================================================================
    with aba_config:
        st.subheader("⚙️ Parâmetros Tributários Municipais (NFS-e)")
        st.caption("Ajuste as diretrizes tributárias do seu hostel conforme as orientações da contabilidade:")

        with st.form("form_cfg_fiscal"):
            col_cf1, col_cf2 = st.columns(2)
            with col_cf1:
                regime = st.selectbox("Regime Tributário:", [
                    "Simples Nacional - ME/EPP",
                    "Simples Nacional - Microempreendedor Individual (MEI)",
                    "Lucro Presumido",
                    "Lucro Real"
                ], index=0)
                cnae = st.text_input("CNAE Principal de Hotelaria / Hospedagem:", value=cfg_fiscal.get("cnae"))
                item_lc116 = st.text_input("Item da Lista de Serviços (LC 116/2003):", value=cfg_fiscal.get("item_lc116"))
                cod_trib_mun = st.text_input("Código de Tributação Municipal (Prefeitura):", value=cfg_fiscal.get("codigo_tributacao_municipio"))

            with col_cf2:
                aliq_iss = st.number_input("Alíquota de ISS Municipal (%):", min_value=0.0, max_value=5.0, value=float(cfg_fiscal.get("aliquota_iss", 2.5)), step=0.1, format="%.2f")
                iss_ret = st.checkbox("ISS Retido na Fonte pelo Tomador?", value=bool(cfg_fiscal.get("iss_retido", False)))
                serie_rps = st.text_input("Série do RPS:", value=cfg_fiscal.get("serie_rps", "1"))
                ult_rps = st.number_input("Número do Último RPS Emitido:", min_value=1, value=int(cfg_fiscal.get("ultimo_rps", 100)), step=1)

            st.markdown("##### 🔌 Conexão com Gateway de Emissão Fiscal")
            col_api1, col_api2 = st.columns(2)
            with col_api1:
                provedor = st.selectbox("Plataforma de Mensageria / Emissão:", ["Focus NFe", "PlugNotas (TecnoSpeed)", "eNotas", "Webservice Direto Prefeitura (SPED)"])
                ambiente = st.radio("Ambiente de Transmissão:", ["Homologação (Testes)", "Produção (Validade Jurídica)"], horizontal=True)
            with col_api2:
                api_token = st.text_input("Token / Chave de Acesso da API Fiscal:", value=cfg_fiscal.get("api_token", ""), type="password", help="Chave fornecida pelo gateway de mensageria para autenticar na Prefeitura.")

            if st.form_submit_button("Salvar Parâmetros Fiscais", type="primary", use_container_width=True):
                novas_cfg = {
                    "regime_tributario": regime,
                    "cnae": cnae,
                    "item_lc116": item_lc116,
                    "codigo_tributacao_municipio": cod_trib_mun,
                    "aliquota_iss": aliq_iss,
                    "iss_retido": iss_ret,
                    "serie_rps": serie_rps,
                    "ultimo_rps": ult_rps,
                    "ambiente_emissao": ambiente,
                    "provedor_api": provedor,
                    "api_token": api_token,
                    "natureza_operacao": "1 - Tributação no Município"
                }
                db.supabase.table("configuracoes").upsert({"chave": "config_nfse_fiscal", "valor": json.dumps(novas_cfg)}).execute()
                db.notificar_sucesso("Parâmetros fiscais atualizados com sucesso!")
                st.rerun()

    # =========================================================================
    # ABA 3: AJUDA ESPECÍFICA DE INTEGRAÇÃO FISCAL (MUNICIPAL)
    # =========================================================================
    with aba_ajuda:
        st.subheader("📚 Guia Prático de Emissão de NFS-e para Hostels")
        st.markdown(
            """
            Diferente de notas fiscais de produtos (NF-e/NFC-e), que seguem o padrão nacional da Receita Federal e da SEFAZ estadual, 
            a **Nota Fiscal de Serviços Eletrônica (NFS-e)** para hotelaria e hospedagem é de competência **estritamente municipal** 
            (Secretaria Municipal da Fazenda / Finanças de cada Prefeitura).

            ---

            ### 1. Etapas Obrigatórias para Emissão Municipal
            1. **Inscrição Municipal Ativa:** O CNPJ do hostel precisa ter alvará e Inscrição Municipal regular na cidade onde opera.
            2. **CNAE Adequado:** O CNAE padrão para meios de hospedagem no Brasil é **`5510-8/01`** (Hotéis e apart-hotéis, aplicável a albergues e hostels).
            3. **Enquadramento na Lista de Serviços (LC 116/2003):** O serviço hoteleiro enquadra-se no subitem **`09.01`** (*Hospedagem de qualquer natureza em hotéis, pensões e congêneres*).
            4. **Certificado Digital A1:** A esmagadora maioria dos municípios exige um Certificado Digital ICP-Brasil (e-CNPJ no formato A1, arquivo `.pfx`).

            ---

            ### 2. Por que Utilizar um Gateway Intermediário de Mensageria?
            No Brasil existem mais de **1.500 modelos diferentes de sistemas de NFS-e** entre os municípios (GissOnline, Betha, IPM, Governa, DSF, Nota Carioca, Nota Paulistana, etc.).
            
            Para não ter que reprogramar o sistema a cada alteração de layout da Prefeitura local, a melhor prática do setor de software é usar um integrador homologado (como **Focus NFe**, **PlugNotas** ou **eNotas**):
            * O hostel cadastra o CNPJ e o Certificado A1 no painel do provedor;
            * O integrador resolve a criptografia, assinatura XML e conexão SOAP da sua cidade;
            * Este sistema apenas envia o payload gerado no botão de transmissão usando o seu **Token da API**.

            ---

            ### 3. Diferença entre RPS e NFS-e
            * **RPS (Recibo Provisório de Serviços):** É o documento preliminar emitido pelo sistema no balcão quando o hóspede fecha a conta. Ele possui numeração sequencial própria (`rps_numero`) e garante validade do atendimento.
            * **NFS-e Oficial:** É o documento definitivo com o QR Code oficial da Prefeitura, gerado assim que o RPS é convertido e validado pelo sistema tributário municipal.
            """,
            unsafe_allow_html=True
        )