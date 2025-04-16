import pdfplumber
import os
import io
import Config
import sys
import re
import pypandoc
import RemplazarTablasDeMarkdown
# pypandoc.download_pandoc()
try:
    # Intenta obtener la ruta de Pandoc. Si no se encuentra, lo descarga.
    pypandoc.get_pandoc_path()
except OSError:
    print("[INFO] Pandoc no encontrado, descargando...")
    pypandoc.download_pandoc()

import dateparser
from datetime import datetime

def extract_header_data(content_text):
    """
    Extrae información del encabezado de un documento a partir de un bloque de texto.
    
    El proceso es el siguiente:
      - Se limpia el contenido eliminando espacios y saltos de línea redundantes.
      - Se inicializa un diccionario con valores por defecto para campos importantes:
          "Nombre", "Para", "De", "Asunto", "Fecha Vigencia" y "Fecha Actualización".
      - Se buscan y extraen los valores de "Para", "De" y "Asunto" mediante expresiones regulares.
      - Se asigna "Nombre" al valor de "Asunto".
      - Se busca y extrae el campo "Fecha Vigencia".
      - Se normalizan las fechas de vigencia utilizando el módulo dateparser, formateándolas en "dd de Month de yyyy".
      - Se generan dos cadenas en formato Markdown: un título y un cuerpo de contenido.
    
    :param content_text: Cadena de texto que se utiliza como contenido del encabezado.
    :return: Tuple (markdown_title, markdown_content) con la información en formato Markdown.
    """
    # Unificar espacios y eliminar saltos adicionales
    content_text = re.sub(r'\s+', ' ', content_text.strip())
    
    # Inicializar el diccionario con valores por defecto
    data = {
        "Nombre": "Desconocido",
        "Para": "No especificado",
        "De": "No especificado",
        "Asunto": "No especificado",
        "Fecha Vigencia": "Desconocida",
        "Fecha Actualización": "No proporcionada"
    }
    
    # Extraer y eliminar el campo "Para"
    match = re.search(r'(?i)para\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["Para"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Extraer y eliminar el campo "De"
    match = re.search(r'(?i)de\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["De"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Extraer y eliminar el campo "Asunto"; se utiliza hasta que se encuentre "Fecha" o final del texto.
    match = re.search(r'(?i)asunto\s*:?\s*(.*?)(?=(?:fecha|$))', content_text)
    if match:
        data["Asunto"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Asignar el título ("Nombre") con el valor de "Asunto"
    data["Nombre"] = data["Asunto"]
    
    # Extraer y eliminar "Fecha Vigencia" del contenido
    match = re.search(r'(?i)(?:fecha\s+oferta\s+v[aá]lida|fecha vigencia)\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["Fecha Vigencia"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Normalizar la fecha de vigencia, si se extrajo, utilizando dateparser
    if data["Fecha Vigencia"] != "Desconocida":
        date_matches = re.findall(r'\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}', data["Fecha Vigencia"])
        if date_matches and len(date_matches) == 2:
            formatted_dates = [dateparser.parse(date, languages=['es']).strftime("%d de %B de %Y") for date in date_matches]
            data["Fecha Vigencia"] = f"{formatted_dates[0]} al {formatted_dates[1]}"
    
    # Formatear la salida en Markdown: se genera un título y se listan los campos con negritas.
    markdown_title = f"# {data['Nombre']}."
    markdown_content = f"**Nombre:** {data['Nombre']}\r\n\r\n**Para:** {data['Para']}\r\n\r\n**De:** {data['De']}\r\n\r\n**Asunto:** {data['Asunto']}\r\n\r\n**Fecha Vigencia:** {data['Fecha Vigencia']}\r\n\r\n**Fecha Actualización:** {data['Fecha Actualización']}\r\n\r\n"
    
    return markdown_title, markdown_content


def extract_policy_data(title_text, content_text):
    """
    Extrae y organiza información de políticas (por ejemplo, campañas o tarifas) a partir 
    del título y el contenido de un documento, y la devuelve en formato Markdown.

    El proceso es similar a extract_header_data, pero enfocado en extraer un identificador
    (por ejemplo, "PTAR 1023" o "PCAM 1023") y otros datos específicos como emisión, versión, ciudades, y vigencia.
    
    :param title_text: Texto del título del documento.
    :param content_text: Contenido del documento con la información a extraer.
    :return: Tuple (markdown_title_output, markdown_title_content) en formato Markdown.
    """
    # Limpiar y unificar el título
    title_text = re.sub(r'\s+', ' ', title_text.strip())
    
    # Extraer el identificador (PTAR o PCAM seguido de número)
    title_match = re.search(r'\b(PTAR|PCAM)\s*\d+', title_text, re.IGNORECASE)
    title_id = title_match.group(0) if title_match else "Desconocido"
    
    # Limpiar y unir líneas en el contenido
    content_text = re.sub(r'\s+', ' ', content_text.strip())
    
    # Inicializar un diccionario con valores por defecto
    data = {
        "Nombre": title_id,
        "Emisión": "Desconocida",
        "Versión": "Desconocida",
        "Ciudades": "No especificadas",
        "Fecha Vigencia": "Desconocida",
        "Fecha Actualización": "No proporcionada"
    }
    
    # Patrones para extraer cada campo importante
    patterns = {
        "Emisión": r'(?:emisi[oó]n|emision|E M I S I O N)\s*:?\s*(\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4})',
        "Versión": r'(?:versi[oó]n|version|vrsn|vers)\s*:?\s*(\d+)',
        "Ciudades": r'(?:ciudades)\s*:?\s*([\w_,\.\s]+)',
        "Fecha Vigencia": r'(?:vigencia)\s*:?\s*((?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}).*?(?:\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}|\d{2}[/-]\d{2}[/-]\d{4}))'
    }
    
    # Buscar y asignar los valores extraídos
    for key, pattern in patterns.items():
        match = re.search(pattern, content_text, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()
    
    # Normalizar las fechas para "Emisión" y "Fecha Vigencia" usando dateparser
    for key in ["Emisión", "Fecha Vigencia"]:
        if data[key] != "Desconocida":
            parsed_date = dateparser.parse(data[key], languages=['es'])
            if parsed_date:
                data[key] = parsed_date.strftime("%d de %B de %Y")
    
    # Formatear la salida en Markdown
    markdown_title_output = f"# {title_text}."
    markdown_title_content = f"**Nombre:** {data['Nombre']}\r\n\r\n\n**Emisión:** {data['Emisión']}\r\n\r\n\n**Versión:** {data['Versión']}\r\n\r\n\n**Ciudades:** {data['Ciudades']}\r\n\r\n\n**Fecha Vigencia:** {data['Fecha Vigencia']}\r\n\r\n\n**Fecha Actualización:** {data['Fecha Actualización']}\r\n\r\n\n"
    
    return markdown_title_output, markdown_title_content


def convertir_pdf_a_markdown(pdf_bytes):
    """
    Convierte un PDF a texto en formato Markdown.

    Procedimiento:
      1. Se reinicia el flujo de pdf_bytes y se crea una copia como BytesIO.
      2. Se abre el PDF usando pdfplumber.
      3. Se itera sobre las páginas del PDF, extrayendo el texto de cada página.
      4. Para las primeras páginas, se utiliza el encabezado para extraer información (por ejemplo, mediante extract_policy_data).
         En modo no móvil se toma la información de las dos primeras páginas; en modo móvil se trata de forma diferente.
      5. Se utiliza Pandoc para convertir el texto extraído a Markdown (para páginas a partir de la segunda).
      6. Finalmente, se devuelve el texto completo en Markdown.
    
    :param pdf_bytes: Objeto BytesIO que contiene el PDF.
    :return: String con el contenido del PDF convertido a Markdown.
    """
    pdf_bytes.seek(0)
    pdf_copy = io.BytesIO(pdf_bytes.getvalue())
    pdf = pdfplumber.open(pdf_copy)

    markdown_text = ""
    encabezado = []

    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if Config.DEBUG_PRINTS:
            print("--" * 50)
            print("Texto extraido\n")
            print("--" * 50)
        
        if text:
            # Preprocesar el texto extraído antes de convertirlo a Markdown
            text = limpiar_texto(text)
            if not Config.MOVIL:
                # En modo no móvil, usar las primeras dos páginas como encabezado
                if i < 2:
                    encabezado.append(text)
                if i == 1:
                    # Obtener datos de política a partir del encabezado
                    title, content = extract_policy_data(encabezado[0], encabezado[1])
                    markdown_text += f"{title}\r\n\n\n{content}\n\n"
            else:
                # En modo móvil, se utiliza extract_header_data (definida en otro módulo) para extraer encabezado
                if i == 0:
                    if Config.DEBUG_PRINTS:
                        print(text)
                    title, content = extract_header_data(text)
                    markdown_text += f"{title}\r\n\n\n{content}\n\n"
                elif i == 1:
                    markdown_text += pypandoc.convert_text(text, 'md', format='markdown')
            
            if i > 1:
                # Para el resto de las páginas, convertir directamente a Markdown usando Pandoc
                markdown_text += pypandoc.convert_text(text, 'md', format='markdown')
                if Config.DEBUG_PRINTS:
                    print("--" * 50)
                    print("Texto MD\n", markdown_text.encode("utf-8", errors="ignore").decode("utf-8"))
                    print("--" * 50)

    return markdown_text


def limpiar_texto(texto):
    """
    Aplica preprocesamiento al texto extraído del PDF para mejorar la conversión a Markdown.

    Acciones realizadas:
      - Elimina subrayados repetidos.
      - Reduce múltiples saltos de línea a uno solo.
      - Convierte patrones como "Pagina X" en encabezados Markdown.
      - Reconoce y formatea ciertos encabezados secundarios (p.ej., "OFERTA ..." o "POLÍTICAS GENERALES").
      - Convierte guiones seguidos de espacios en asteriscos para listas en Markdown.

    :param texto: Cadena de texto extraída del PDF.
    :return: Texto preprocesado listo para conversión a Markdown.
    """
    texto = re.sub(r'_{2,}', '', texto)  # Eliminar subrayados repetidos
    texto = re.sub(r'\n{2,}', '\n', texto)  # Reducir saltos de línea
    texto = re.sub(r'(Pagina\s\d+)', r'# \1', texto)  # Convertir "Pagina X" en un encabezado
    texto = re.sub(r'\b(OFERTA .+|POLÍTICAS GENERALES)\b', r'## \1', texto)  # Encabezados secundarios
    texto = re.sub(r'-\s', r'* ', texto)  # Formatear listas a sintaxis Markdown
    return texto.strip()


def main(pdf_bytes, folder_path):
    """
    Función principal para procesar un PDF y convertir su contenido a Markdown.
    
    Se obtiene el contenido en Markdown mediante convertir_pdf_a_markdown y luego se guarda
    en dos archivos:
      - "markdown_puro.md": Contenido Markdown sin separar por líneas.
      - "markdown_tablas_remplazadas.md": Versión del Markdown después de reemplazar las tablas.
    
    :param pdf_bytes: Objeto BytesIO del PDF a procesar.
    :param folder_path: Ruta de la carpeta donde se guardarán los archivos resultantes.
    :return: Markdown final con las tablas reemplazadas.
    """
    markdown_result = convertir_pdf_a_markdown(pdf_bytes)
    # Guardar versión "pura" en un archivo
    with open(os.path.join(folder_path, "markdown_puro.md"), 'w', encoding='utf-8') as f:
        f.write("".join(markdown_result.split("\n")))
    # Si existe una carpeta de tablas HTML, se procede al reemplazo en el Markdown
    if os.path.exists(os.path.join(folder_path, "tablas_html")):
        markdown_result_tablas_remplazadas = RemplazarTablasDeMarkdown.remplazar_tablas_en_md("".join(markdown_result.split("\n")), folder_path)
    else:
        markdown_result_tablas_remplazadas = "".join(markdown_result.split("\n"))
    # Guardar la versión final con las tablas reemplazadas
    with open(os.path.join(folder_path, "markdown_tablas_remplazadas.md"), 'w', encoding='utf-8') as f:
        f.write(markdown_result_tablas_remplazadas)
    
    return markdown_result_tablas_remplazadas


def pdfplumber_to_fitz(pdf):
    """
    Convierte un objeto PDF abierto con pdfplumber a un objeto BytesIO
    para que PyMuPDF (fitz) pueda procesarlo correctamente.

    :param pdf: Objeto PDF abierto con pdfplumber.
    :return: Objeto BytesIO con el contenido del PDF.
    """
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)  # Reinicia el stream en el PDF
    pdf_bytes.write(pdf.stream.read())
    pdf_bytes.seek(0)
    return pdf_bytes


# Bloque principal: se ejecuta si el script es invocado directamente desde la terminal.
if __name__ == "__main__":
    # Si se pasan argumentos, se utiliza el primer argumento como pdf_bytes.
    if len(sys.argv) > 1:
        pdf_bytes = sys.argv[1]
    else:
        pdf_path = "documento_verticalizado_llaves_tablas_imagenes.pdf"  # Ruta por defecto si no se pasa argumento
        folder_path = "Curacion_Md_" + pdf_path.split(".pdf")[0]
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
            if Config.DEBUG_PRINTS:
                print(f"Carpeta '{folder_path}' creada con éxito.")
        else:
            if Config.DEBUG_PRINTS:
                print(f"La carpeta '{folder_path}' ya existe.")
        with pdfplumber.open(pdf_path) as pdf:
            pdf_bytes = pdfplumber_to_fitz(pdf)
            pdf_bytes.seek(0)
    
    main(pdf_bytes, folder_path)
