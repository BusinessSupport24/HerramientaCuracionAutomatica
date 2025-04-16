import pikepdf
import re
import io
import zlib
import pdfplumber
import sys
import os
import Config
from pathlib import Path

def convertir_a_ruta_larga(path_str):
    """
    Convierte una ruta relativa a una "ruta larga" para Windows, utilizando el prefijo '\\\\?\\'.
    
    Esto es útil para evitar problemas con rutas demasiado largas en Windows.

    :param path_str: Ruta original (string).
    :return: Ruta en formato "largo" (string).
    """
    path = Path(path_str)
    abs_path = path.resolve()  # Obtiene la ruta absoluta
    if not abs_path.drive:
        return str(abs_path)
    return r"\\?\{}".format(str(abs_path))


def agregar_texto_a_pagina(pdf, page_number, x, y, texto, font_name="/F1", font_size=8.04, color="0 G"):
    """
    Genera una cadena que representa el operador de texto en sintaxis PDF para agregar
    un texto en una ubicación específica de una página. Se utiliza para insertar "llaves"
    en el PDF donde se han eliminado imágenes.

    La función genera una secuencia de comandos PDF (envuelta entre "q" y "Q") con los parámetros
    dados.

    :param pdf: Objeto PDF (no se usa directamente en el código, pero puede ser útil en extensiones futuras).
    :param page_number: Número de la página donde se insertará el texto.
    :param x: Coordenada X en la que se colocará el texto.
    :param y: Coordenada Y en la que se colocará el texto.
    :param texto: Texto a agregar.
    :param font_name: Nombre de la fuente (por defecto "/F1").
    :param font_size: Tamaño de fuente (por defecto 8.04).
    :param color: Comando de color en sintaxis PDF ("0 G" para negro por defecto).
    :return: Cadena de texto con la secuencia de operadores PDF para insertar el texto.
    """
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
    # La secuencia anterior abre un nuevo estado gráfico (q), inicia el bloque de texto (BT),
    # establece la fuente y tamaño, posiciona el texto, aplica el color, escribe el texto y cierra el bloque (ET) y el estado gráfico (Q).
    return text_stream


def eliminar_imagenes_y_agregar_llaves(pdf_bytes, folder_path):
    """
    Procesa un PDF para eliminar todas las imágenes y, en su lugar, inserta una "llave" (texto)
    que indica la posición original de la imagen eliminada.

    Procedimiento:
      1. Se abre el PDF a partir de un objeto BytesIO.
      2. Se crea un nuevo PDF vacío.
      3. Se itera por cada página, y por cada objeto de la página se verifica si es un flujo
         de datos (p.ej., imagen) mediante pikepdf.
      4. Para cada flujo, se intenta decodificar el contenido; si no es posible, se intenta descomprimirlo.
      5. Se procesa cada línea del contenido:
         - Se detectan transformaciones (cm) para obtener la posición.
         - Se detecta la presencia del operador "Do" (que indica el uso de una imagen).
         - Si se encuentra una imagen (y la página no es la 2, por ejemplo), se elimina su referencia.
         - Se agrega un comentario y se inserta una "llave" en el lugar donde la imagen fue eliminada.
      6. Se reemplaza el contenido de la página por el contenido modificado.
      7. Se agregan las páginas procesadas al nuevo PDF.
      8. Se eliminan recursos sin referenciar y se guarda el nuevo PDF en la carpeta especificada.
      9. Se retorna un objeto BytesIO con el PDF modificado.

    :param pdf_bytes: Objeto BytesIO que contiene el PDF original.
    :param folder_path: Carpeta en la que se guardará el PDF modificado.
    :return: Objeto BytesIO con el PDF resultante.
    """
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)
    new_pdf = pikepdf.Pdf.new()
    imagenes_eliminadas = []  # Lista para almacenar datos de imágenes eliminadas (para depuración)

    # Iterar sobre cada página
    for page_number, page in enumerate(pdf.pages):
        page_obj = page.obj
        img_count = 0  # Contador de imágenes eliminadas en la página

        # Iterar sobre cada objeto en la página
        for key, obj_ref in list(page_obj.items()):
            try:
                # Obtener el objeto: si es flujo directo o indirecto
                if isinstance(obj_ref, pikepdf.Stream):
                    obj = obj_ref
                elif isinstance(obj_ref, pikepdf.Object) and obj_ref.is_indirect:
                    obj = pdf.get_object(obj_ref.objgen)
                else:
                    continue

                if isinstance(obj, pikepdf.Stream):
                    # Leer el flujo en bruto
                    raw_data = obj.read_raw_bytes()
                    try:
                        # Intentar decodificar el flujo directamente
                        decoded_data = obj.get_data().decode('latin1', errors='ignore')
                    except:
                        try:
                            # Si falla, intentar descomprimirlo primero
                            decoded_data = zlib.decompress(raw_data).decode('latin1', errors='ignore')
                        except:
                            continue

                    # Dividir el contenido en líneas
                    lines = decoded_data.split("\n")
                    text_chunks = []
                    current_x, current_y = 0, 0

                    # Procesar cada línea para encontrar imágenes
                    for line in lines:
                        # Detectar transformación mediante 'cm' para obtener la posición de la imagen
                        cm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) cm', line)
                        if cm_match:
                            # Se ignoran los primeros 4 números; se usan e y f para la posición
                            _, _, _, _, e, f = map(float, cm_match.groups())
                            current_x, current_y = e, f
                        
                        # Detectar el comando 'Do' que indica el uso de un XObject (posible imagen)
                        do_match = re.search(r'/([A-Za-z0-9]+)\s+Do', line)
                        # Se ignora la página 1 (página 2 en índice 1) según el código
                        if do_match and page_number != 1:
                            img_count += 1
                            # Guardar coordenadas de la imagen eliminada (opcional, para depuración)
                            imagenes_eliminadas.append((page_number, img_count, current_x, current_y))
                            # Agregar un comentario en el contenido indicando la eliminación de la imagen
                            text_chunks.append(f"% Imagen eliminada: {do_match.group(1)}")
                            # Eliminar la referencia a la imagen removiendo el operador Do
                            line = re.sub(r'/([A-Za-z0-9]+)\s+Do', '', line)
                            # Generar la llave a insertar en su lugar
                            texto_llave = f"(Llave_Unica_Imagen_{page_number+1}_{img_count})"
                            line = line + agregar_texto_a_pagina(new_pdf, page_number, current_x, current_y, texto_llave)
                        
                        # Agregar la línea (modificada o no) al contenido final
                        text_chunks.append(line)

                    # Unir las líneas procesadas y crear un nuevo flujo con el contenido modificado
                    new_stream = pikepdf.Stream(pdf, "\n".join(text_chunks).encode('latin1', errors='ignore'))
                    page_obj[key] = new_stream
            except Exception as e:
                # En caso de error se omite el objeto y se continúa con el siguiente
                continue

        # Agregar la página modificada al nuevo PDF
        new_pdf.pages.append(page)
    
    # Remover recursos sin referenciar para limpiar el PDF final
    new_pdf.remove_unreferenced_resources()

    # Convertir la ruta de folder_path a formato "largo" para evitar problemas en Windows
    folder_path_ruta_larga = convertir_a_ruta_larga(folder_path)
    # Guardar el nuevo PDF modificado con imágenes eliminadas y llaves insertadas
    new_pdf.save(folder_path_ruta_larga + r"\documento_verticalizado_llaves_tablas_imagenes.pdf")
    
    pdf_bytes_final = io.BytesIO()
    new_pdf.save(pdf_bytes_final)
    pdf_bytes_final.seek(0)
    return pdf_bytes_final


def main(pdf_bytes, folder_path):
    """
    Función principal que llama a eliminar_imagenes_y_agregar_llaves para procesar un PDF.
    
    :param pdf_bytes: BytesIO del PDF a procesar.
    :param folder_path: Carpeta donde se guardarán los resultados.
    """
    eliminar_imagenes_y_agregar_llaves(pdf_bytes, folder_path)


def pdfplumber_to_fitz(pdf):
    """
    Convierte un objeto PDF abierto con pdfplumber a un objeto BytesIO para uso con PyMuPDF.

    :param pdf: Objeto PDF abierto con pdfplumber.
    :return: BytesIO con el contenido del PDF.
    """
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)  # Reiniciar la posición para leer el contenido completo
    pdf_bytes.write(pdf.stream.read())
    pdf_bytes.seek(0)
    return pdf_bytes


# Ejecutar el script principal si se invoca directamente desde la terminal
if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_bytes = sys.argv[1]  # Obtener PDF desde argumento de línea de comandos
    else:
        pdf_path = "documento_verticalizado_llaves_tablas.pdf"  # Ruta por defecto
        folder_path = "Curacion_" + pdf_path.split(".pdf")[0]
        # Crear la carpeta destino si no existe
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
            if Config.DEBUG_PRINTS:
                print(f"Carpeta '{folder_path}' creada con éxito.")
        else:
            if Config.DEBUG_PRINTS:
                print(f"La carpeta '{folder_path}' ya existe.")

        # Abrir el PDF usando pdfplumber y convertirlo a BytesIO para PyMuPDF
        with pdfplumber.open(pdf_path) as pdf:
            pdf_bytes = pdfplumber_to_fitz(pdf)
            pdf_bytes.seek(0)
    # Llamar a la función principal con el PDF procesado
    main(pdf_bytes, folder_path)
