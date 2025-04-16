import re
import dateparser
from datetime import datetime

def extract_policy_data(title_text, content_text):
    """
    Extrae y organiza información clave (política) a partir de un título y un contenido 
    textual, y genera una salida en formato Markdown.

    El proceso se realiza en varias etapas:

    1. Limpieza y normalización del título:
       - Se eliminan espacios extra y se unifican los espacios en blanco.
       - Se intenta extraer un identificador, buscando patrones "PTAR" o "PCAM" seguidos de un número.
       - Si no se encuentra, se asigna "Desconocido" como identificador.

    2. Limpieza del contenido:
       - Se eliminan espacios extra y saltos de línea redundantes, unificando el texto.

    3. Extracción de campos específicos mediante expresiones regulares:
       - "Emisión": Se busca una fecha de emisión en el contenido.
       - "Versión": Se extrae un número que represente la versión.
       - "Ciudades": Se recopilan palabras o frases que indiquen ciudades.
       - "Fecha Vigencia": Se intenta capturar un rango de fechas (vigencia).

    4. Normalización de fechas:
       - Se utiliza el módulo dateparser para interpretar las fechas extraídas y convertirlas 
         al formato "dd de Month de yyyy" (en español).

    5. Formateo final:
       - Se construye una cadena de texto en formato Markdown que incluye el título y los
         campos extraídos, con negrita y saltos de línea para mayor claridad.

    :param title_text: Cadena que representa el título, del cual se extrae el identificador.
    :param content_text: Cadena que contiene el contenido del documento, del cual se extraen 
                         otros atributos (fecha de emisión, versión, ciudades, vigencia, etc.).
    :return: Una cadena en formato Markdown con la información organizada.
    """

    # 1. Limpiar y unificar espacios en el título.
    title_text = re.sub(r'\s+', ' ', title_text.strip())
    
    # 2. Extraer el identificador (por ejemplo, "PCAM 1023" o "PTAR 1234") del título.
    title_match = re.search(r'\b(PTAR|PCAM)\s*\d+', title_text, re.IGNORECASE)
    title_id = title_match.group(0) if title_match else "Desconocido"
    
    # 3. Limpiar y unir líneas dispersas en el contenido.
    content_text = re.sub(r'\s+', ' ', content_text.strip())
    
    # 4. Inicializar un diccionario con valores por defecto para los campos a extraer.
    data = {
        "Nombre": title_id,
        "Emisión": "Desconocida",
        "Versión": "Desconocida",
        "Ciudades": "No especificadas",
        "Fecha Vigencia": "Desconocida",
        "Fecha Actualización": "No proporcionada"
    }
    
    # 5. Definir patrones regulares (regex) para cada campo.
    patterns = {
        "Emisión": r'(?:emisi[oó]n|emision|E M I S I O N)\s*:?\s*(\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4})',
        "Versión": r'(?:versi[oó]n|version|vrsn|vers)\s*:?\s*(\d+)',
        "Ciudades": r'(?:ciudades)\s*:?\s*([\w_,\.\s]+)',
        "Fecha Vigencia": r'(?:vigencia)\s*:?\s*((?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}).*?(?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}))'
    }
    
    # 6. Buscar y extraer los valores en el contenido utilizando los patrones definidos.
    for key, pattern in patterns.items():
        match = re.search(pattern, content_text, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()
    
    # 7. Normalizar las fechas extraídas para los campos "Emisión" y "Fecha Vigencia"
    for key in ["Emisión", "Fecha Vigencia"]:
        if data[key] != "Desconocida":
            parsed_date = dateparser.parse(data[key], languages=['es'])
            if parsed_date:
                data[key] = parsed_date.strftime("%d de %B de %Y")
    
    # 8. Formatear el resultado en Markdown, incluyendo el título y los campos extraídos.
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

# Ejemplo de uso:
# (Se puede descomentar para pruebas individuales)
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
#
# resultado = extract_policy_data(title_text, content_text)
# print(resultado)
