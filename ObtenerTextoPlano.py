import pikepdf
import re
import io
import zlib
import pdfplumber
import Config
import os
import sys

def extraer_atributos_pikepdf(pdf_path):
    """
    Extrae texto y algunos atributos (como fuente, negrilla, tamaño, color y tipos de listas)
    desde un PDF usando pikepdf, y lo convierte en un texto en formato Markdown.

    Procedimiento:
      - Abre el PDF con pikepdf.
      - Itera por cada página y extrae el contenido del objeto "/Contents".
      - Para cada stream de contenido, se decodifica y se divide en líneas.
      - Utiliza expresiones regulares para detectar atributos como la fuente (Tf) y color (rg),
        y para identificar numeraciones, bullets o letras que inicien la línea.
      - Construye el resultado Markdown, agregando una sintaxis particular para listas numeradas o bullets.

    :param pdf_path: Ruta del PDF a procesar.
    :return: Un string con el contenido extraído y formateado en Markdown.
    """
    pdf = pikepdf.open(pdf_path)
    markdown_output = ""
    
    for page_number, page in enumerate(pdf.pages):
        # Si la página no tiene contenido, se omite.
        if "/Contents" not in page.obj:
            continue
        
        # Obtener el contenido de la página, que puede ser un array o un solo objeto.
        page_content = page.obj["/Contents"]
        objects = page_content if isinstance(page_content, pikepdf.Array) else [page_content]
        
        # Procesar cada objeto de contenido
        for obj_ref in objects:
            obj = pdf.get_object(obj_ref.objgen)
            if not isinstance(obj, pikepdf.Stream):
                continue  # Se omite si no es un flujo de texto
            
            # Decodificar el flujo en UTF-8 ignorando errores
            decoded_data = obj.read_bytes().decode('utf-8', errors='ignore')
            lines = decoded_data.split('\n')
            
            # Procesar cada línea para detectar atributos y formatear según corresponda
            for line in lines:
                # Buscar la fuente utilizada, detectando comandos como "Tf"
                font_match = re.search(r'/([A-Za-z0-9#]+) Tf', line)
                font_name = font_match.group(1) if font_match else ""
                # Determinar si la fuente indica negrilla (Bold o Black)
                is_bold = "Bold" in font_name or "Black" in font_name
                
                # Buscar el color del texto (comando 'rg') y convertirlo a RGB
                color_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) rg', line)
                text_color = color_match.groups() if color_match else "default"
                
                # Detectar si la línea comienza con un patrón numérico (lista numerada)
                if re.match(r'^\d+\.\s', line):
                    markdown_output += f'1. {line}\n'
                # Detectar si la línea comienza con una letra seguida de ')'
                elif re.match(r'^[a-z]\)\s', line, re.IGNORECASE):
                    markdown_output += f'- {line}\n'
                # Detectar bullets o símbolos de lista
                elif '•' in line or '○' in line:
                    markdown_output += f'- {line}\n'
                else:
                    # Si se detecta negrilla, envolver la línea en ** (sintaxis Markdown para negritas)
                    if is_bold:
                        line = f'**{line}**'
                    markdown_output += line + '\n'
                
        # Separador de páginas
        markdown_output += f'\n\n'
    
    return markdown_output


def extraer_texto(decoded_data):
    """
    Extrae y limpia el texto de un flujo de contenido PDF, respetando el orden original
    y realizando algunos ajustes para unir textos fragmentados, eliminar repeticiones y corregir separaciones.

    Procedimiento:
      - Se divide el contenido en líneas.
      - Se ignoran líneas que contengan metadatos o comandos (como "BT", "ET" o "/Artifact").
      - Se actualizan las coordenadas actuales mediante la detección de transformaciones (Tm y Td).
      - Se extrae el texto contenido dentro de paréntesis (usualmente en Tj/TJ) y se ignoran duplicados.
      - Se ordenan los textos según la posición Y (para preservar el orden de lectura).
      - Se aplican varias expresiones regulares para corregir el texto:
         * Eliminar valores numéricos entre paréntesis.
         * Reemplazar múltiples espacios por uno solo.
         * Separar palabras pegadas.
         * Unir duplicados y corregir separaciones erróneas en números.
         * Asegurar que numeraciones comiencen en líneas separadas.
    
    :param decoded_data: Cadena decodificada del flujo de contenido extraído del PDF.
    :return: Cadena de texto final limpia y ordenada.
    """
    text_positions = []  # Lista para almacenar tuplas (posición_Y, texto)
    seen_texts = set()   # Para evitar textos duplicados
    current_x, current_y = 0, 0  # Posición actual en el flujo

    lines = decoded_data.split("\n")
    print(''.join(lines))
    for line in lines:
        # Ignorar líneas que contienen artefactos o comandos no textuales
        if "/Artifact" in line or "BT" in line or "ET" in line:
            continue
        
        # Actualizar posición mediante la detección de la matriz de transformación (Tm)
        tm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) Tm', line)
        if tm_match:
            _, _, _, _, current_x, current_y = map(float, tm_match.groups())

        # Actualizar posición mediante desplazamientos (Td)
        td_match = re.search(r'([-0-9.]+) ([-0-9.]+) Td', line)
        if td_match:
            dx, dy = map(float, td_match.groups())
            current_x += dx
            current_y += dy

        # Extraer el texto contenido entre paréntesis y que esté asociado al comando TJ
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            cleaned_text = "".join(tj_match).strip()
            # Evitar duplicados agregando solo textos nuevos
            if cleaned_text and cleaned_text not in seen_texts:
                seen_texts.add(cleaned_text)
                text_positions.append((current_y, cleaned_text))

    # Ordenar los textos en base a la posición Y (de mayor a menor) para respetar el orden de lectura
    text_positions.sort(reverse=True, key=lambda x: x[0])
    texto_final = " ".join([text for _, text in text_positions])
    
    # Aplicar correcciones adicionales al texto resultante:
    # - Eliminar números entre paréntesis
    texto_final = re.sub(r'\s*\([-0-9.]+\)\s*', '', texto_final)
    # - Reemplazar múltiples espacios por uno solo
    texto_final = re.sub(r'\s+', ' ', texto_final).strip()
    # - Separar palabras pegadas (por ejemplo, cuando se juntan letras mayúsculas)
    texto_final = re.sub(r'(?<! )([A-Za-z])([A-Z])', r'\1 \2', texto_final)
    # - Eliminar duplicados consecutivos
    texto_final = re.sub(r'\b(\w+)\s+\1\b', r'\1', texto_final, flags=re.IGNORECASE)
    # - Corregir separaciones en números
    texto_final = re.sub(r'(\d)\s+\.(?=\d)', r'\1.', texto_final)
    texto_final = re.sub(r'(\d)\s+(\d)', r'\1\2', texto_final)
    # - Forzar salto de línea antes de numeraciones
    texto_final = re.sub(r'(\d+)\.\s*', r'\n\1. ', texto_final)

    return texto_final


def procesar_stream(obj, page_number, key):
    """
    Intenta extraer y decodificar el contenido de un stream del PDF.
    Se maneja la compresión (usando zlib) y se ignoran errores de decodificación.

    :param obj: Objeto pikepdf.Stream a procesar.
    :param page_number: Número de la página (0-indexado) donde se encuentra el stream.
    :param key: Clave o identificador del objeto para propósitos de logging o depuración.
    :return: Texto extraído procesado mediante la función extraer_texto.
             Retorna una cadena vacía en caso de error.
    """
    try:
        decoded_data = obj.get_data().decode('latin-1', errors='ignore')
    except:
        try:
            decoded_data = zlib.decompress(obj.read_raw_bytes()).decode('utf-8', errors='ignore')
        except:
            print(f"[!] No se pudo descomprimir el flujo en Página {page_number + 1}, Key: {key}")
            return ""
    
    return extraer_texto(decoded_data)


def combinar_y_fusionar_streams(pdf, page):
    """
    Fusiona todos los flujos (streams) de contenido de una página en un solo flujo de texto,
    respetando el orden y la posición original del contenido. Esto permite que se extraiga
    el texto de la página de manera coherente.

    Procedimiento:
      - Si el contenido ("/Contents") es un array, se iteran todos los streams.
      - Si no, se recorren todos los items del diccionario de la página.
      - Para cada stream, se procesan y se agrega el texto extraído a la lista de textos.
      - Se unen los textos con un espacio y se realizan algunas correcciones finales.

    :param pdf: Objeto PDF abierto con pikepdf.
    :param page: Objeto que representa la página actual, con su contenido.
    :return: Texto combinado y limpiado de la página.
    """
    combined_texts = []
    
    # Comprobar si "/Contents" es un array de streams
    if isinstance(page.obj.get("/Contents"), pikepdf.Array):
        for content_ref in page.obj["/Contents"]:
            combined_texts.append(procesar_stream(pdf.get_object(content_ref.objgen), page.page_number, "/Contents Array"))
    else:
        # Recorrer todos los objetos en la página y procesar aquellos que son streams o diccionarios con XObjects
        for key, obj_ref in list(page.obj.items()):
            try:
                if isinstance(obj_ref, pikepdf.Stream):
                    combined_texts.append(procesar_stream(obj_ref, page.page_number, key))
                elif isinstance(obj_ref, pikepdf.Object) and obj_ref.is_indirect:
                    obj = pdf.get_object(obj_ref.objgen)
                    if isinstance(obj, pikepdf.Stream):
                        combined_texts.append(procesar_stream(obj, page.page_number, key))
                elif isinstance(obj_ref, pikepdf.Dictionary) and "/XObject" in obj_ref:
                    for xobj_key, xobj_ref in obj_ref["/XObject"].items():
                        xobj = pdf.get_object(xobj_ref.objgen)
                        if isinstance(xobj, pikepdf.Stream):
                            combined_texts.append(procesar_stream(xobj, page.page_number, xobj_key))
            except Exception as e:
                print(f"[!] Error al procesar Página {page.page_number + 1}, Key: {key}: {e}")
                continue
    
    # Unir el texto extraído de todos los streams y limpiar algunos posibles artefactos
    final_text = " ".join(combined_texts)
    final_text = re.sub(r'\s*\([-0-9.]+\)\s*', '', final_text)  # Eliminar números entre paréntesis
    final_text = re.sub(r'\s+', ' ', final_text).strip()
    final_text = re.sub(r'(?<! )([A-Za-z])([A-Z])', r'\1 \2', final_text)
    return final_text


def convertir_pdf_a_texto(pdf_bytes, output_txt_path):
    """
    Convierte todo el contenido textual de un PDF en un único archivo de texto.
    La función itera sobre cada página del PDF, combina y fusiona todos los streams
    de contenido en un solo bloque de texto para cada página, y luego escribe el resultado
    en el archivo de salida especificado.

    :param pdf_bytes: Objeto BytesIO que contiene el PDF.
    :param output_txt_path: Ruta del archivo de texto de salida.
    :return: Ruta del archivo de texto de salida.
    """
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)
    text_content = ""
    
    for page_number, page in enumerate(pdf.pages):
        page.page_number = page_number  # Asignar número de página (0-indexado) al objeto de la página
        extracted_text = combinar_y_fusionar_streams(pdf, page)
        print("OTRA PAGINA" * 50)
        input()  # Pausa para depuración interactiva (puedes eliminar esto en producción)
        
        # Agregar un encabezado para cada página
        text_content += f"\n\n## Página {page_number + 1}\n"
        if extracted_text.strip():
            text_content += extracted_text
        else:
            text_content += "_(Sin texto en esta página)_"
    
    print(text_content)

    # Escribir el texto final en el archivo de salida con codificación UTF-8
    with open(output_txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(text_content)
    
    return output_txt_path


def main(pdf_bytes, folder_path):
    """
    Función principal para convertir un PDF a texto plano.
    
    Se guarda el resultado en un archivo de texto dentro del folder_path.

    :param pdf_bytes: Objeto BytesIO con el PDF a procesar.
    :param folder_path: Carpeta donde se guardará el archivo de texto.
    :return: Ruta del archivo de texto generado.
    """
    output_md_path = os.path.join(folder_path, "Texto_Extraido.txt")
    convertir_pdf_a_texto(pdf_bytes, output_md_path)


def pdfplumber_to_fitz(pdf):
    """
    Convierte un objeto PDF abierto con pdfplumber a un objeto BytesIO,
    para que PyMuPDF (fitz) pueda procesarlo correctamente.

    :param pdf: Objeto PDF abierto con pdfplumber.
    :return: Objeto BytesIO con el contenido del PDF.
    """
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)  # Asegurarse de que se lea desde el principio
    pdf_bytes.write(pdf.stream.read())
    pdf_bytes.seek(0)
    return pdf_bytes


# Bloque principal: Se ejecuta cuando el script se invoca directamente desde la terminal.
if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_bytes = sys.argv[1]  # Leer PDF desde argumentos de línea de comandos
    else:
        pdf_path = "documento_verticalizado_llaves_tablas_imagenes.pdf"  # Ruta por defecto
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
