import pikepdf
import re
import io
import zlib
import pdfplumber
import sys
import os
import Config

def agregar_texto_a_pagina(pdf, page_number, x, y, texto, font_name="/F1", font_size=8.04, color="0 G"):
    """
    Agrega un texto en una página PDF en la misma ubicación donde se eliminó una imagen.
    """
    # page = pdf.pages[page_number]
    text_stream = f"""
    q
    BT
    {font_name} {font_size} Tf
    1 0 0 1 {x} {y} Tm
    {color}
    [{texto}] TJ
    ET
    Q
    """
    # new_stream = pikepdf.Stream(pdf, text_stream.encode('latin1'))
    # page.contents_add(new_stream)
    return text_stream

def eliminar_imagenes_y_agregar_llaves(pdf_bytes, folder_path):
    """
    Elimina todas las imágenes en un PDF y agrega una llave en su posición.
    """
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)
    new_pdf = pikepdf.Pdf.new()
    imagenes_eliminadas = []  # Lista para almacenar coordenadas y números de imágenes eliminadas
    
    for page_number, page in enumerate(pdf.pages):
        page_obj = page.obj
        img_count = 0  # Contador de imágenes eliminadas por página
        
        for key, obj_ref in list(page_obj.items()):
            try:
                if isinstance(obj_ref, pikepdf.Stream):
                    obj = obj_ref
                elif isinstance(obj_ref, pikepdf.Object) and obj_ref.is_indirect:
                    obj = pdf.get_object(obj_ref.objgen)
                else:
                    continue
                
                if isinstance(obj, pikepdf.Stream):
                    raw_data = obj.read_raw_bytes()
                    try:
                        decoded_data = obj.get_data().decode('latin1', errors='ignore')
                    except:
                        try:
                            decoded_data = zlib.decompress(raw_data).decode('latin1', errors='ignore')
                        except:
                            continue
                    
                    lines = decoded_data.split("\n")
                    text_chunks = []
                    current_x, current_y = 0, 0
                    
                    for line in lines:
                        cm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) cm', line)
                        if cm_match:
                            _, _, _, _, e, f = map(float, cm_match.groups())
                            current_x, current_y = e, f  # Posición de la imagen
                        
                        do_match = re.search(r'/([A-Za-z0-9]+)\s+Do', line)
                        if do_match and page_number != 1:
                            img_count += 1
                            imagenes_eliminadas.append((page_number, img_count, current_x, current_y))
                            text_chunks.append(f"% Imagen eliminada: {do_match.group(1)}")  # Comentario en el PDF
                            line = re.sub(r'/([A-Za-z0-9]+)\s+Do', '', line)  # Eliminar referencia a la imagen       
                            texto_llave = f"(Llave_Unica_Imagen_{page_number+1}_{img_count})"
                            line = line + agregar_texto_a_pagina(new_pdf, page_number, current_x, current_y, texto_llave)
                            # text_chunks.append(line_llave)
                        
                        text_chunks.append(line)
                        # text_chunks.append(agregar_texto_a_pagina(new_pdf, page_number, current_x, current_y, texto_llave))
                    
                    new_stream = pikepdf.Stream(pdf, "\n".join(text_chunks).encode('latin1', errors='ignore'))
                    page_obj[key] = new_stream
            except Exception as e:
                continue
        
        new_pdf.pages.append(page)
    
    # # Agregar las llaves en el PDF ya modificado
    # for page_number, img_count, x, y in imagenes_eliminadas:
    #     texto_llave = f"(Llave_Unica_Imagen_{page_number+1}_{img_count})"
    #     agregar_texto_a_pagina(new_pdf, page_number, x, y, texto_llave)

    new_pdf.remove_unreferenced_resources()
    new_pdf.save(folder_path+r"\documento_verticalizado_llaves_tablas_imagenes.pdf")
    
    pdf_bytes_final = io.BytesIO()
    new_pdf.save(pdf_bytes_final)
    pdf_bytes_final.seek(0)
    return pdf_bytes_final

def main(pdf_bytes,folder_path):
    """
    Función principal que muestra tablas de un PDF con pdfplumber y botones.
    
    Parámetros:
        ruta_pdf (str): Ruta del PDF a procesar.
    """
    eliminar_imagenes_y_agregar_llaves(pdf_bytes, folder_path)  # Llama a tu función con el parámetro recibido

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
        pdf_path = "documento_verticalizado_llaves_tablas.pdf"  # Valor por defecto si no se pasa argumento}
        folder_path = "Curacion_"+pdf_path.split(".pdf")[0]
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