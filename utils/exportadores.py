import io
import pandas as pd
from datetime import datetime

def sanitizar_texto(texto):
    """Higieniza o texto, tratando caracteres acentuados para WinAnsi e removendo quebras de linha em literais."""
    if texto is None:
        return ""
    s = str(texto).replace("\r", " ").replace("\n", " ")
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("cp1252", errors="replace").decode("latin-1")

def gerar_csv(df: pd.DataFrame) -> bytes:
    """Gera CSV compatível com Excel em português (separador ponto e vírgula e BOM UTF-8)."""
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")

class PDFNativo:
    """Compilador de PDF 1.4 nativo em conformidade estrita com ISO 32000-1."""
    def __init__(self, landscape=True):
        self.width = 842.0 if landscape else 595.0
        self.height = 595.0 if landscape else 842.0
        self.pages = []
        self.stream_atual = []

    def nova_pagina(self):
        if self.stream_atual:
            self.pages.append("".join(self.stream_atual))
            self.stream_atual = []

    def cmd(self, c):
        self.stream_atual.append(c + "\n")

    def desenhar_retangulo(self, x, y, w, h, r, g, b, fill=True, stroke=False):
        if fill:
            self.cmd(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
        if stroke:
            self.cmd(f"0.800 0.830 0.880 RG 0.5 w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")

    def desenhar_texto(self, x, y, texto, tamanho=9, bold=False, italic=False, r=0.0, g=0.0, b=0.0):
        font_id = "/F2" if bold else ("/F3" if italic else "/F1")
        t_limpo = sanitizar_texto(texto)
        self.cmd(f"BT {font_id} {tamanho} Tf {r:.3f} {g:.3f} {b:.3f} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({t_limpo}) Tj ET")

    def desenhar_linha(self, x1, y1, x2, y2, r=0.85, g=0.88, b=0.92, espessura=0.5):
        self.cmd(f"{r:.3f} {g:.3f} {b:.3f} RG {espessura:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def compilar(self) -> bytes:
        if self.stream_atual:
            self.pages.append("".join(self.stream_atual))
            self.stream_atual = []

        if not self.pages:
            self.pages.append("BT /F1 10 Tf 50 500 Td (Relatorio sem registros) Tj ET\n")

        total_pags = len(self.pages)
        objetos = []

        # Objeto 1: Catálogo
        objetos.append("<< /Type /Catalog /Pages 2 0 R >>")

        # Objeto 2: Árvore de Páginas
        kids = " ".join([f"{6 + (i * 2)} 0 R" for i in range(total_pags)])
        objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {total_pags} >>")

        # Objetos 3, 4, 5: Fontes Standard WinAnsi
        objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>")

        # Objetos de Páginas e Streams
        for i, stream_text in enumerate(self.pages):
            content_id = 7 + (i * 2)
            content_bytes = stream_text.encode("latin-1", errors="replace")

            # Objeto Página
            objetos.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )
            # Objeto Conteúdo
            objetos.append(
                f"<< /Length {len(content_bytes)} >>\nstream\n{stream_text}endstream"
            )

        # Montagem do binário PDF 1.4
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []

        for idx, obj in enumerate(objetos):
            offsets.append(out.tell())
            obj_str = f"{idx + 1} 0 obj\n{obj}\nendobj\n"
            out.write(obj_str.encode("latin-1"))

        # Tabela XREF rigorosa (exatamente 20 bytes por linha)
        xref_offset = out.tell()
        total_objs = len(objetos) + 1
        out.write(f"xref\n0 {total_objs}\n".encode("latin-1"))
        out.write(b"0000000000 65535 f \r\n")
        for off in offsets:
            out.write(f"{off:010d} 00000 n \r\n".encode("latin-1"))

        trailer = f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        out.write(trailer.encode("latin-1"))

        return out.getvalue()

def _cabecalho_rodape(pdf, titulo, pag_num):
    w = pdf.width
    pdf.desenhar_texto(30, pdf.height - 35, "SISTEMA DE GESTAO INTEGRADA DE HOSTEL", tamanho=12, bold=True, r=0.12, g=0.16, b=0.23)
    pdf.desenhar_texto(30, pdf.height - 48, titulo.upper(), tamanho=9, bold=True, r=0.28, g=0.33, b=0.41)
    
    data_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    pdf.desenhar_texto(w - 200, pdf.height - 35, f"Emitido em: {data_str}", tamanho=8, italic=True, r=0.55, g=0.60, b=0.68)
    pdf.desenhar_linha(30, pdf.height - 54, w - 30, pdf.height - 54, r=0.85, g=0.88, b=0.92, espessura=1.0)

    # Rodapé
    pdf.desenhar_linha(30, 30, w - 30, 30, r=0.85, g=0.88, b=0.92, espessura=0.5)
    pdf.desenhar_texto(w - 80, 20, f"Página {pag_num}", tamanho=8, italic=True, r=0.55, g=0.60, b=0.68)

def gerar_pdf_tabela(titulo: str, colunas: list, dados: list, orientacao="L") -> bytes:
    landscape = (orientacao.upper() == "L")
    pdf = PDFNativo(landscape=landscape)
    
    margem = 30.0
    largura_util = pdf.width - (margem * 2)
    largura_col = largura_util / max(1, len(colunas))
    altura_linha = 18.0
    y_topo = pdf.height - 80
    y = y_topo
    pag = 1

    _cabecalho_rodape(pdf, titulo, pag)

    # Cabeçalho da Tabela
    pdf.desenhar_retangulo(margem, y - altura_linha, largura_util, altura_linha, 0.12, 0.16, 0.23, fill=True)
    for idx, col in enumerate(colunas):
        col_x = margem + (idx * largura_col) + 5
        pdf.desenhar_texto(col_x, y - 13, str(col).upper(), tamanho=8, bold=True, r=1.0, g=1.0, b=1.0)
    y -= altura_linha

    if not dados:
        pdf.desenhar_texto(margem + 10, y - 25, "Nenhum registro encontrado para este relatorio.", tamanho=9, italic=True, r=0.4, g=0.4, b=0.4)
        return pdf.compilar()

    zebra = False
    for item in dados:
        if y < 60:
            pdf.nova_pagina()
            pag += 1
            _cabecalho_rodape(pdf, titulo, pag)
            y = y_topo
            pdf.desenhar_retangulo(margem, y - altura_linha, largura_util, altura_linha, 0.12, 0.16, 0.23, fill=True)
            for idx, col in enumerate(colunas):
                col_x = margem + (idx * largura_col) + 5
                pdf.desenhar_texto(col_x, y - 13, str(col).upper(), tamanho=8, bold=True, r=1.0, g=1.0, b=1.0)
            y -= altura_linha

        r_bg, g_bg, b_bg = (0.96, 0.97, 0.99) if zebra else (1.0, 1.0, 1.0)
        pdf.desenhar_retangulo(margem, y - altura_linha, largura_util, altura_linha, r_bg, g_bg, b_bg, fill=True, stroke=True)

        for idx, col in enumerate(colunas):
            col_x = margem + (idx * largura_col) + 5
            val = str(item.get(col, ""))
            if len(val) > 34:
                val = val[:31] + "..."
            pdf.desenhar_texto(col_x, y - 12, val, tamanho=8, r=0.06, g=0.09, b=0.16)

        y -= altura_linha
        zebra = not zebra

    return pdf.compilar()

def gerar_pdf_recibo(hospede: str, quarto: str, cama: str, periodo: str, responsavel: str, total_geral: float, detalhes_texto: str = "") -> bytes:
    pdf = PDFNativo(landscape=False)
    _cabecalho_rodape(pdf, "Comprovante de Hospedagem e Quitacao", 1)

    y = pdf.height - 75
    margem = 35.0
    largura = pdf.width - (margem * 2)

    pdf.desenhar_texto(margem, y, "DADOS DA ACOMODACAO E DO HOSPEDE", tamanho=10, bold=True, r=0.12, g=0.16, b=0.23)
    pdf.desenhar_linha(margem, y - 5, margem + largura, y - 5, r=0.85, g=0.88, b=0.92, espessura=0.8)
    y -= 22

    pdf.desenhar_texto(margem, y, f"Hospede: {hospede}", tamanho=9, bold=True, r=0.06, g=0.09, b=0.16)
    y -= 14
    pdf.desenhar_texto(margem, y, f"Quarto: {quarto}   |   Cama / Leito: {cama}", tamanho=9, r=0.2, g=0.25, b=0.3)
    y -= 14
    pdf.desenhar_texto(margem, y, f"Periodo da Estadia: {periodo}", tamanho=9, r=0.2, g=0.25, b=0.3)
    y -= 14
    pdf.desenhar_texto(margem, y, f"Responsavel Financeiro: {responsavel}", tamanho=9, r=0.2, g=0.25, b=0.3)
    y -= 25

    if detalhes_texto:
        pdf.desenhar_texto(margem, y, "DISCRIMINACAO DOS VALORES E SERVICOS", tamanho=10, bold=True, r=0.12, g=0.16, b=0.23)
        pdf.desenhar_linha(margem, y - 5, margem + largura, y - 5, r=0.85, g=0.88, b=0.92, espessura=0.8)
        y -= 20

        linhas = [l for l in detalhes_texto.strip().split("\n") if l.strip()]
        for linha in linhas:
            if "---" in linha:
                pdf.desenhar_linha(margem, y - 2, margem + largura, y - 2, r=0.85, g=0.88, b=0.92, espessura=0.5)
                y -= 8
                continue
            pdf.desenhar_texto(margem + 5, y, linha, tamanho=8.5, r=0.2, g=0.25, b=0.3)
            y -= 13
        y -= 12

    pdf.desenhar_retangulo(margem, y - 32, largura, 32, 0.86, 0.99, 0.90, fill=True, stroke=True)
    pdf.desenhar_texto(margem + 15, y - 20, f"VALOR TOTAL QUITADO: R$ {total_geral:.2f}", tamanho=13, bold=True, r=0.09, g=0.40, b=0.20)
    pdf.desenhar_texto(margem + 15, y - 28, "Status: Estadia Concluida e Paga", tamanho=8, italic=True, r=0.09, g=0.40, b=0.20)

    y -= 55
    pdf.desenhar_texto(margem, y, "Agradecemos por sua preferencia. Desejamos uma excelente viagem!", tamanho=8.5, italic=True, r=0.4, g=0.45, b=0.5)

    return pdf.compilar()