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
    Extrae texto y atributos como negrilla, numeración, color, indentación y bullets desde un PDF,
    usando pikepdf y convirtiéndolo en Markdown.
    """
    pdf = pikepdf.open(pdf_path)
    markdown_output = ""
    
    for page_number, page in enumerate(pdf.pages):
        if "/Contents" not in page.obj:
            continue  # Página sin contenido
        
        page_content = page.obj["/Contents"]
        objects = page_content if isinstance(page_content, pikepdf.Array) else [page_content]
        
        for obj_ref in objects:
            obj = pdf.get_object(obj_ref.objgen)
            if not isinstance(obj, pikepdf.Stream):
                continue  # No es un flujo de texto
            
            decoded_data = obj.read_bytes().decode('utf-8', errors='ignore')
            lines = decoded_data.split('\n')
            
            for line in lines:
                # Detectar fuentes (negrilla, itálica, etc.)
                font_match = re.search(r'/([A-Za-z0-9#]+) Tf', line)
                font_name = font_match.group(1) if font_match else ""
                is_bold = "Bold" in font_name or "Black" in font_name
                
                # Detectar color de texto
                color_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) rg', line)
                text_color = color_match.groups() if color_match else "default"
                
                # Detectar numeraciones y bullets
                if re.match(r'^\d+\.\s', line):
                    markdown_output += f'1. {line}\n'
                elif re.match(r'^[a-z]\)\s', line, re.IGNORECASE):
                    markdown_output += f'- {line}\n'
                elif '•' in line or '○' in line:
                    markdown_output += f'- {line}\n'
                else:
                    # Aplicar negrilla si es necesario
                    if is_bold:
                        line = f'**{line}**'
                    markdown_output += line + '\n'
                
        markdown_output += f'\n\n'  # Separación entre páginas
    
    return markdown_output

def extraer_texto(decoded_data):
    """
    Extrae y limpia el texto de un flujo de contenido PDF respetando el orden, eliminando repeticiones
    y cerrando correctamente paréntesis abiertos.
    """
    text_positions = []  # Lista para almacenar el texto con su posición
    seen_texts = set()  # Para evitar duplicaciones
    current_x, current_y = 0, 0  # Posición del texto

    lines = decoded_data.split("\n")
    print(''.join(lines))
    for line in lines:
        # Ignorar metadatos y artefactos
        if "/Artifact" in line or "BT" in line or "ET" in line:
            continue
        
        # Detectar matrices de transformación (Tm)
        tm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) Tm', line)
        if tm_match:
            _, _, _, _, current_x, current_y = map(float, tm_match.groups())

        # Detectar desplazamiento de texto (Td)
        td_match = re.search(r'([-0-9.]+) ([-0-9.]+) Td', line)
        if td_match:
            dx, dy = map(float, td_match.groups())
            current_x += dx
            current_y += dy

        # Detectar texto en Tj y TJ
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            cleaned_text = "".join(tj_match).strip()

            # Evitar agregar texto duplicado
            if cleaned_text and cleaned_text not in seen_texts:
                seen_texts.add(cleaned_text)
                text_positions.append((current_y, cleaned_text))

    # Ordenar el texto según la posición Y para respetar la estructura del documento
    text_positions.sort(reverse=True, key=lambda x: x[0])
    texto_final = " ".join([text for _, text in text_positions])
    
    # **Correcciones adicionales**
    texto_final = re.sub(r'\s*\([-0-9.]+\)\s*', '', texto_final)  # Eliminar valores numéricos en paréntesis
    texto_final = re.sub(r'\s+', ' ', texto_final).strip()  # Reemplazar múltiples espacios con un solo espacio
    texto_final = re.sub(r'(?<! )([A-Za-z])([A-Z])', r'\1 \2', texto_final)  # Separar palabras pegadas
    texto_final = re.sub(r'\b(\w+)\s+\1\b', r'\1', texto_final, flags=re.IGNORECASE)  # Eliminar duplicados consecutivos
    texto_final = re.sub(r'(\d)\s+\.(?=\d)', r'\1.', texto_final)  # Corregir separación en números
    texto_final = re.sub(r'(\d)\s+(\d)', r'\1\2', texto_final)  # Unir números separados erróneamente

    # **Asegurar que los numerales estén en líneas separadas**
    texto_final = re.sub(r'(\d+)\.\s*', r'\n\1. ', texto_final)  # Forzar salto de línea antes de "1.", "2.", "3."

    return texto_final




def procesar_stream(obj, page_number, key):
    """
    Intenta decodificar y extraer el texto de un stream, manejando compresión y errores.
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
    Fusiona todos los flujos de contenido de la página en un solo flujo antes de extraer el texto.
    Respetando el orden de los `Streams` y la posición del texto.
    """
    combined_texts = []
    
    # Verificar si el contenido de la página es un array de múltiples streams
    if isinstance(page.obj.get("/Contents"), pikepdf.Array):
        for content_ref in page.obj["/Contents"]:
            obj = pdf.get_object(content_ref.objgen)
            if isinstance(obj, pikepdf.Stream):
                combined_texts.append(procesar_stream(obj, page.page_number, "/Contents Array"))
    else:
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
    
    # Unir y limpiar texto final
    final_text = " ".join(combined_texts)
    final_text = re.sub(r'\s*\([-0-9.]+\)\s*', '', final_text)  # Eliminar valores numéricos en paréntesis
    final_text = re.sub(r'\s+', ' ', final_text).strip()  # Reemplazar múltiples espacios con un solo espacio
    final_text = re.sub(r'(?<! )([A-Za-z])([A-Z])', r'\1 \2', final_text)  # Separar palabras pegadas
    return final_text

def convertir_pdf_a_texto(pdf_bytes, output_txt_path):
    """
    Convierte el texto de un PDF a un archivo de texto sin formato, asegurando el orden correcto de los flujos.
    """
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)
    text_content = ""
    
    for page_number, page in enumerate(pdf.pages):
        page.page_number = page_number  # Agregar el número de página como atributo
        extracted_text = combinar_y_fusionar_streams(pdf, page)
        print("OTRA PAGINA"*50)
        input()
        
        text_content += f"\n\n## Página {page_number + 1}\n"
        if extracted_text.strip():
            text_content += extracted_text
        else:
            text_content += "_(Sin texto en esta página)_"
    
    print(text_content)

    with open(output_txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(text_content)
    
    return output_txt_path


def main(pdf_bytes,folder_path):
    """
    Función principal que muestra tablas de un PDF con pdfplumber y botones.
    
    Parámetros:
        ruta_pdf (str): Ruta del PDF a procesar.
    """
    output_md_path = os.path.join(folder_path, "Texto_Extraido.txt")
    convertir_pdf_a_texto(pdf_bytes, output_md_path)

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