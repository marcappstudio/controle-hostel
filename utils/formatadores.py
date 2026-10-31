import re
import base64
from datetime import datetime

def converter_para_base64(arquivo_buffer, mime_padrao="image/jpeg"):
    if not arquivo_buffer:
        return None
    bytes_data = arquivo_buffer.getvalue()
    mime_type = getattr(arquivo_buffer, "type", None) or mime_padrao
    b64_str = base64.b64encode(bytes_data).decode("utf-8")
    return f"data:{mime_type};base64,{b64_str}"

def extrair_data(dt_val):
    if not dt_val:
        return None
    try:
        if isinstance(dt_val, str):
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00")).date()
        elif isinstance(dt_val, datetime):
            return dt_val.date()
    except Exception:
        try:
            return datetime.strptime(str(dt_val).split("T")[0], "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r'\D', '', str(cpf or ''))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(i))
        digito = ((soma * 10) % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True

def validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r'\D', '', str(cnpj or ''))
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6] + pesos_1
    soma_1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    d1 = 11 - (soma_1 % 11)
    d1 = 0 if d1 >= 10 else d1
    if d1 != int(cnpj[12]):
        return False
    soma_2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    d2 = 11 - (soma_2 % 11)
    d2 = 0 if d2 >= 10 else d2
    if d2 != int(cnpj[13]):
        return False
    return True

def formatar_data_br(data_str: str) -> str:
    if not data_str:
        return "Não informada"
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        try:
            dt = datetime.strptime(data_str.split("T")[0], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return data_str

def ordenar_natural(lista, chave_str):
    def chave_conversao(item):
        texto = str(item.get(chave_str, ""))
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', texto)]
    return sorted(lista, key=chave_conversao)