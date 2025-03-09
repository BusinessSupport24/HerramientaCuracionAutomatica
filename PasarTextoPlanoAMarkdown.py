import pdfplumber
import os
import io
import Config
import sys
import mistune
import re
import pypandoc
import RemplazarTablasDeMarkdown
pypandoc.download_pandoc()
import dateparser
from datetime import datetime

def extract_header_data(content_text):
    # Limpiar y unificar espacios y saltos de línea en el contenido
    content_text = re.sub(r'\s+', ' ', content_text.strip())
    
    # Diccionario para almacenar resultados
    data = {
        "Nombre": "Desconocido",
        "Para": "No especificado",
        "De": "No especificado",
        "Asunto": "No especificado",
        "Fecha Vigencia": "Desconocida",
        "Fecha Actualización": "No proporcionada"
    }
    
    # Extraer y eliminar "Para"
    match = re.search(r'(?i)para\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["Para"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Extraer y eliminar "De"
    match = re.search(r'(?i)de\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["De"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Extraer y eliminar "Asunto" hasta el primer salto de línea o "Fecha"
    match = re.search(r'(?i)asunto\s*:?\s*(.*?)(?=(?:fecha|$))', content_text)
    if match:
        data["Asunto"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # El título será el mismo valor que el Asunto
    data["Nombre"] = data["Asunto"]
    
    # Extraer y eliminar "Fecha Vigencia"
    match = re.search(r'(?i)(?:fecha\s+oferta\s+v[aá]lida|fecha vigencia)\s*:?\s*(.*?)(?:\.|$)', content_text)
    if match:
        data["Fecha Vigencia"] = match.group(1).strip()
        content_text = content_text.replace(match.group(0), '', 1)
    
    # Normalizar fechas usando dateparser
    if data["Fecha Vigencia"] != "Desconocida":
        date_matches = re.findall(r'\d{1,2}\s*de\s*[a-zA-Z]+\s*de\s*\d{4}', data["Fecha Vigencia"])
        if date_matches and len(date_matches) == 2:
            formatted_dates = [dateparser.parse(date, languages=['es']).strftime("%d de %B de %Y") for date in date_matches]
            data["Fecha Vigencia"] = f"{formatted_dates[0]} al {formatted_dates[1]}"
    
            
    # Formatear el resultado en Markdown
    markdown_title = f"# {data['Nombre']}."
    markdown_content = f"**Nombre:** {data['Nombre']}\r\n\r\n**Para:** {data['Para']}\r\n\r\n**De:** {data['De']}\r\n\r\n**Asunto:** {data['Asunto']}\r\n\r\n**Fecha Vigencia:** {data['Fecha Vigencia']}\r\n\r\n**Fecha Actualización:** {data['Fecha Actualización']}\r\n\r\n"
    
    return markdown_title, markdown_content



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
    markdown_title_output = f"# {title_text}."
    markdown_title_content = f"**Nombre:** {data['Nombre']}\r\n\r\n\n**Emisión:** {data['Emisión']}\r\n\r\n\n**Versión:** {data['Versión']}\r\n\r\n\n**Ciudades:** {data['Ciudades']}\r\n\r\n\n**Fecha Vigencia:** {data['Fecha Vigencia']}\r\n\r\n\n**Fecha Actualización:** {data['Fecha Actualización']}\r\n\r\n\n"
    
    return markdown_title_output, markdown_title_content


def convertir_pdf_a_markdown(pdf_bytes):
    pdf_bytes.seek(0)
    pdf_copy = io.BytesIO(pdf_bytes.getvalue())
    pdf = pdfplumber.open(pdf_copy)

    markdown_text = ""
    encabezado = []

    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        print("--"*50)
        print("Texto extraido\n")
        print("--"*50)
        
        if text:
            text = limpiar_texto(text)  # Preprocesar el texto antes de pasarlo a Pandoc
            if not Config.MOVIL:
                if i < 2:
                    encabezado.append(text)
                if i == 1:# markdown_text += f"\n\n### Página {i+1}\n\n"  # Agregar encabezado de página
                    title,content = extract_policy_data(encabezado[0],encabezado[1])
                    markdown_text += f"{title}\r\n\n\n{content}\n\n"
            else:
                if i == 0:# markdown_text += f"\n\n### Página {i+1}\n\n"  # Agregar encabezado de página
                    print(text)
                    title, content = extract_header_data(text)
                    # title,content = extract_policy_data(text,encabezado[0])
                    markdown_text += f"{title}\r\n\n\n{content}\n\n"
                elif i==1:
                    markdown_text += pypandoc.convert_text(text, 'md', format='markdown')  # Convertir con Pandoc
                
            if i > 1:
                markdown_text += pypandoc.convert_text(text, 'md', format='markdown')  # Convertir con Pandoc
                print("--"*50)
                print("Texto MD\n",markdown_text)
                print("--"*50)


    return markdown_text

def limpiar_texto(texto):
    """
    Aplica preprocesamiento al texto extraído:
    - Elimina espacios múltiples
    - Formatea títulos y negritas
    - Agrega saltos de línea para una mejor conversión a Markdown
    """
    texto = re.sub(r'_{2,}', '', texto)  # Elimina subrayados repetidos
    texto = re.sub(r'\n{2,}', '\n', texto)  # Evita múltiples saltos de línea
    texto = re.sub(r'(Pagina\s\d+)', r'# \1', texto)  # Convierte "Pagina X" en encabezado Markdown
    texto = re.sub(r'\b(OFERTA .+|POLÍTICAS GENERALES)\b', r'## \1', texto)  # Encabezados secundarios
    texto = re.sub(r'-\s', r'* ', texto)  # Convierte listas en Markdown
    return texto.strip()


def main(pdf_bytes,folder_path):
    """
    Función principal que muestra tablas de un PDF con pdfplumber y botones.
    
    Parámetros:
        ruta_pdf (str): Ruta del PDF a procesar.
    """
    # output_md_path = os.path.join(folder_path, "Texto_Extraido.txt")
    # Llamar a la función con un archivo PDF en memoria
    markdown_result = convertir_pdf_a_markdown(pdf_bytes)
    with open(folder_path+r"\markdown_puro.md", 'w', encoding='utf-8') as f:
        f.write("".join(markdown_result.split("\n")))
    markdown_result_tablas_remplazadas = RemplazarTablasDeMarkdown.remplazar_tablas_en_md("".join(markdown_result.split("\n")),folder_path)
    # print(markdown_result_tablas_remplazadas)
    with open(folder_path+r"\markdown_tablas_remplazadas.md", 'w', encoding='utf-8') as f:
        f.write(markdown_result_tablas_remplazadas)
    
    return markdown_result_tablas_remplazadas

def pdfplumber_to_fitz(pdf):
    pdf_bytes = io.BytesIO()
    
    pdf.stream.seek(0)  # Asegurar que estamos al inicio del archivo
    pdf_bytes.write(pdf.stream.read())  # Guardar el contenido en memoria
    pdf_bytes.seek(0)  # Volver al inicio para que fitz lo lea correctamente

    return pdf_bytes  # Retornar el PDF en memoria

# Si el script se ejecuta directamente desde la terminal
if __name__ == "__main__":
    # Verifica si se pasó un argumento desde la línea de comandos
    if len(sys.argv) > 1:
        pdf_bytes = sys.argv[1]  # Toma el primer argumento después del script
    else:
        pdf_path = "documento_verticalizado_llaves_tablas_imagenes.pdf"  # Valor por defecto si no se pasa argumento}
        folder_path = "Curacion_Md_"+pdf_path.split(".pdf")[0]
        if not os.path.exists(folder_path):  # Verifica si la carpeta no existe
            os.mkdir(folder_path)  # Crea la carpeta
            if Config.DEBUG_PRINTS:
                print(f"Carpeta '{folder_path}' creada con éxito.")
        else:
            if Config.DEBUG_PRINTS:
                print(f"La carpeta '{folder_path}' ya existe.")

        with pdfplumber.open(pdf_path) as pdf:
            pdf_bytes = pdfplumber_to_fitz(pdf)  # Convertir pdfplumber a BytesIO para fitz    
            # Asegurar que el stream está en la posición correcta antes de usarlo
            pdf_bytes.seek(0)

    main(pdf_bytes,folder_path)  # Llama a la función con el argumento