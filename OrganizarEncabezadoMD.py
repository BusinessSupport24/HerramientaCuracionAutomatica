import re
import dateparser
from datetime import datetime

def extract_policy_data(title_text, content_text):
    # Limpiar y unificar espacios en el título
    title_text = re.sub(r'\s+', ' ', title_text.strip())
    
    # Extraer el identificador (PCAM o PTAR y su código numérico)
    title_match = re.search(r'\b(PTAR|PCAM)\s*\d+', title_text, re.IGNORECASE)
    title_id = title_match.group(0) if title_match else "Desconocido"
    
    # Limpiar y unir líneas dispersas en el contenido
    content_text = re.sub(r'\s+', ' ', content_text.strip())
    
    # Diccionario para almacenar resultados
    data = {
        "Nombre": title_id,
        "Emisión": "Desconocida",
        "Versión": "Desconocida",
        "Ciudades": "No especificadas",
        "Fecha Vigencia": "Desconocida",
        "Fecha Actualización": "No proporcionada"
    }
    
    # Expresiones regulares para detectar campos con errores humanos
    patterns = {
        "Emisión": r'(?:emisi[oó]n|emision|E M I S I O N)\s*:?\s*(\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4})',
        "Versión": r'(?:versi[oó]n|version|vrsn|vers)\s*:?\s*(\d+)',
        "Ciudades": r'(?:ciudades)\s*:?\s*([\w_,\.\s]+)',
        "Fecha Vigencia": r'(?:vigencia)\s*:?\s*((?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}).*?(?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}))'
    }
    
    # Buscar los valores en el contenido
    for key, pattern in patterns.items():
        match = re.search(pattern, content_text, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()
    
    # Normalizar fechas usando dateparser
    for key in ["Emisión", "Fecha Vigencia"]:
        if data[key] != "Desconocida":
            parsed_date = dateparser.parse(data[key], languages=['es'])
            if parsed_date:
                data[key] = parsed_date.strftime("%d de %B de %Y")
    
    # Formatear el resultado en Markdown
    markdown_output = f"""
    #{title_text}.
    
    **Nombre:** {data['Nombre']}
    
    **Emisión:** {data['Emisión']}
    
    **Versión:** {data['Versión']}
    
    **Ciudades:** {data['Ciudades']}
    
    **Fecha Vigencia:** {data['Fecha Vigencia']}
    
    **Fecha Actualización:** {data['Fecha Actualización']}
    """.strip()
    
    return markdown_output

# # Texto de ejemplo
# title_text = """
# PCAM 1023 CAMPAÑA HBO Y MAX TODO CLARO 12 MESES Y NO TODO CLARO 6 MESES
# AMBOS CON 50 % DE DESCUENTO PARA RED HFC_FTTH Y EN DTH UNIDAD DE MERCADO MASIVO
# """

# content_text = """
# Emisión: 23 de mayo de 2017. 
# Vigencia: 1 de marzo de 2025 al 31 de marzo de 2025. 
# Versión: 62. 
# Ciudades: HFC_FTTH_DTH. NACIONAL.
# """

# # Ejecutar función
# resultado = extract_policy_data(title_text, content_text)
# print(resultado)
