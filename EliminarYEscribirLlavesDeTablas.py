import pikepdf
import zlib
import re
import io
import traceback
import Config
from pathlib import Path

def convertir_a_ruta_larga(path_str):
    """
    Convierte una ruta relativa a una ruta "larga" para Windows utilizando el prefijo '\\\\?\\'.
    Esto permite manejar rutas que exceden el límite habitual de Windows.
    
    :param path_str: Ruta original en forma de cadena.
    :return: Ruta formateada como "ruta larga".
    """
    path = Path(path_str)
    abs_path = path.resolve()  # Obtiene la ruta absoluta
    if not abs_path.drive:
        return str(abs_path)
    # Si se detecta una unidad de disco, aplica el prefijo para rutas largas.
    return r"\\?\{}".format(str(abs_path))


def elemento_en_area(x, y, area):
    """
    Determina si un punto (x, y) está dentro del área de interés.

    :param x: Coordenada X del punto.
    :param y: Coordenada Y del punto.
    :param area: Tuple (ax1, ay1, ax2, ay2) que define la zona de interés.
    :return: True si el punto está dentro del área, False en caso contrario.
    """
    ax1, ay1, ax2, ay2 = area
    return ax1 <= x <= ax2 and ay1 <= y <= ay2


def agregar_texto_a_pagina(pdf, page_number, x, y, texto, font_name="/F1", font_size=8.04, color="0 G"):
    """
    Construye una cadena de comandos PDF que inserta un bloque de texto en una página en una ubicación específica.
    
    La cadena generada está compuesta por:
      - 'q' para guardar el estado gráfico.
      - 'BT' y 'ET' para iniciar y terminar el bloque de texto.
      - 'Tf' para definir la fuente y su tamaño.
      - 'Tm' para posicionar el texto.
      - 'TJ' para mostrar el texto.
      - 'Q' para restaurar el estado gráfico.
    
    Esta función se utiliza para insertar "llaves" en el PDF en el sitio donde se ha eliminado una imagen.
    
    :param pdf: Objeto PDF (no se utiliza directamente para modificar, pero puede extenderse).
    :param page_number: Número de la página (0-indexado) en la que se insertará el texto.
    :param x: Coordenada X de la posición.
    :param y: Coordenada Y de la posición.
    :param texto: Texto a insertar.
    :param font_name: Nombre de la fuente, por defecto "/F1".
    :param font_size: Tamaño de la fuente (por defecto 8.04).
    :param color: Comando de color en sintaxis PDF ("0 G" para negro).
    :return: Cadena en sintaxis PDF que representa la inserción del texto.
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
    if Config.DEBUG_PRINTS:
        print(f"Texto añadido en página {page_number + 1} en coordenadas ({x}, {y}).")
    return text_stream


def filtrar_contenido(decoded_data, area_interes, primera_pagina, page_number):
    """
    Filtra el contenido de un flujo de página, eliminando líneas (comandos de texto,
    vectores, rectángulos, etc.) cuyo punto de referencia se encuentre dentro de un área de interés.

    El proceso es el siguiente:
      - Se divide el contenido en líneas.
      - Se actualizan las coordenadas actuales (current_x, current_y) usando comandos Tm y Td.
      - Para cada línea se detecta la presencia de texto (Tj o TJ), líneas vectoriales (m, l) o rectángulos (re).
      - Si la posición (current_x, current_y) cae dentro del área de interés, se marca la línea para eliminarla.
      - Se detecta también el uso de imágenes ('Do'); si se determina que la imagen está en el área, se elimina.
      - Finalmente, se unen las líneas que no fueron eliminadas.

    :param decoded_data: Cadena decodificada del flujo de contenido de la página.
    :param area_interes: Tuple (ax1, ay1, ax2, ay2) que define la región donde se desea filtrar contenido.
    :param primera_pagina: Indicador para imprimir mensajes de depuración en la primera página.
    :param page_number: Número de la página actual (0-indexado).
    :return: Cadena resultante con el contenido filtrado.
    """
    text_chunks = []  # Almacena las líneas que se conservarán
    current_x, current_y = 0, 0  # Inicializa las coordenadas en 0
    eliminar = False  # Bandera que indica si la línea se debe eliminar

    # Dividir el contenido en líneas para procesamiento
    lines = decoded_data.split("\n")
    if page_number == 0 and primera_pagina == 0 and Config.DEBUG_PRINTS:
        # Ajuste inicial para la primera página
        primera_pagina = 1

    # Procesar línea por línea
    for i, line in enumerate(lines):
        eliminar = False  # Reiniciar la bandera para cada línea

        # Detectar matriz de transformación (Tm) para actualizar la posición
        tm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) Tm', line)
        if tm_match:
            # Se ignoran los primeros 4 valores; se extraen 'e' y 'f'
            _, _, _, _, current_x, current_y = map(float, tm_match.groups())

        # Detectar desplazamiento (Td) para actualizar la posición
        td_match = re.search(r'([-0-9.]+) ([-0-9.]+) Td', line)
        if td_match:
            dx, dy = map(float, td_match.groups())
            current_x += dx
            current_y += dy

        # Detectar líneas de texto en Tj
        text_match = re.search(r'\[((?:\([^)]*\)|<[^>]+>)[^]]*)\] T[Jj]', line)
        if text_match:
            text = text_match.group(1)
            x1, y1 = current_x, current_y  # Posición de referencia
            # Si la posición se encuentra en el área de interés, marcar para eliminar
            eliminar = elemento_en_area(x1, y1, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar texto fragmentado con TJ y unirlo
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            text = "".join(tj_match)
            x1, y1 = current_x, current_y
            eliminar = elemento_en_area(x1, y1, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar comandos de movimiento 'm' y de dibujo de líneas 'l'
        vector_match = re.search(r'([-0-9.]+) ([-0-9.]+) m', line)
        line_match = re.search(r'([-0-9.]+) ([-0-9.]+) l', line)
        if vector_match:
            x, y = map(float, vector_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Vector (m): ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")
        if line_match:
            x, y = map(float, line_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Línea (l): ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar comando para dibujar un rectángulo ('re')
        rect_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) re', line)
        if rect_match:
            x, y, w, h = map(float, rect_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Rectángulo: ({x}, {y}, {w}, {h}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar el uso de imágenes (comando 'Do')
        cm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) cm', line)
        if cm_match:
            a, b, c, d, e, f = map(float, cm_match.groups())
            current_x, current_y = e, f  # Actualizar la posición de la imagen
        
        do_match = re.search(r'/([A-Za-z0-9]+)\s+Do', line)
        if do_match:
            obj_id = do_match.group(1)
            eliminar_img = elemento_en_area(current_x, current_y, area_interes)
            if primera_pagina == 1 and Config.DEBUG_PRINTS:
                print(f"Imagen (Do) detectada en ({current_x}, {current_y}) - {'[ELIMINADO]' if eliminar_img else '[MANTENIDO]'}")
            if eliminar_img:
                # Si la imagen debe eliminarse, quitar la referencia
                line = re.sub(r'/([A-Za-z0-9]+)\s+Do', '', line)
        # Solo agregar la línea si no fue marcada para eliminar
        if not eliminar:
            text_chunks.append(line)

    # Devolver el contenido filtrado uniendo las líneas conservadas
    return "\n".join(text_chunks)


def eliminar_elementos_area(crop_data, pdf_bytes, folder_path):
    """
    Elimina los elementos (texto, vectores, etc.) contenidos dentro de las áreas de interés definidas
    en 'crop_data' de un PDF. Se crea un nuevo PDF en el que se han removido dichos elementos.

    Procedimiento:
      1. Se reinicia el puntero del BytesIO del PDF.
      2. Se abre el PDF original con pikepdf.
      3. Se crea un nuevo PDF (vacío) para alojar las páginas modificadas.
      4. Se agrupan las áreas de interés por página.
      5. Para cada página:
         - Se realiza una copia de la página original.
         - Se convierten las coordenadas del área de interés del sistema de Matplotlib al sistema de pikepdf (invirtiendo el eje Y).
         - Se recorre cada objeto del contenido de la página y se filtra el contenido utilizando 'filtrar_contenido'.
         - Se reemplaza el contenido original por el filtrado.
      6. Se añaden las páginas modificadas al nuevo PDF.
      7. Se remueven recursos sin usar y se guarda el PDF resultante en el folder de destino.
      8. Se retorna el PDF modificado como un objeto BytesIO.

    :param crop_data: Lista de tuplas (page_number, area) donde 'area' es (left, top, right, bottom) en coordenadas de Matplotlib.
    :param pdf_bytes: BytesIO del PDF original.
    :param folder_path: Ruta de la carpeta donde se guardará el PDF modificado.
    :return: BytesIO del nuevo PDF con los elementos internos eliminados en las áreas definidas.
    """
    primera_pagina = 0

    # Asegurar que el flujo de bytes comience desde el principio
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)

    # Crear un nuevo PDF para almacenar las páginas modificadas
    new_pdf = pikepdf.Pdf.new()

    # Inicializar un diccionario con una lista de áreas para cada página
    page_areas = {}
    for i in range(len(pdf.pages)):
        page_areas[i] = []
    for page_number, rect in crop_data:
        page_areas[page_number].append(rect)

    if Config.DEBUG_PRINTS:
        print("Page_Areas:")
        print(page_areas)

    # Iterar sobre cada página con áreas de interés
    for page_number, areas_interes in page_areas.items():
        if Config.DEBUG_PRINTS:
            print(f"\nProcesando Página {page_number + 1} con {len(areas_interes)} área(s) de interés")
        
        # Obtener la página original
        original_page = pdf.pages[page_number]
        
        # Crear una copia temporal de la página para modificarla
        temp_pdf = pikepdf.Pdf.new()
        temp_pdf.pages.append(original_page)
        page_copy = temp_pdf.pages[0]

        # Obtener dimensiones de la página para convertir las coordenadas
        _, _, width, height = original_page.mediabox

        if Config.DEBUG_PRINTS:
            print("Cantidad de áreas en la página:", len(areas_interes))

        if len(areas_interes) > 0:
            # Convertir cada área de interés del sistema Matplotlib al sistema de pikepdf (invertir eje Y)
            areas_interes_pdf = []
            for area_interes in areas_interes:
                table_idx, left, top, right, bottom = area_interes
                top_pdf = float(height) - bottom
                bottom_pdf = float(height) - top
                areas_interes_pdf.append((table_idx, (left, top_pdf, right, bottom_pdf)))
            
            page_obj = page_copy.obj

            # Iterar sobre cada objeto en la página
            for key, obj_ref in page_obj.items():
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
                                print(f"[!] No se pudo descomprimir el flujo en Página {page_number + 1}")
                                continue

                        # Para cada área de interés, filtrar el contenido de la página
                        for table_idx, area_interes_pdf in areas_interes_pdf:
                            left, top, right, bottom = area_interes_pdf
                            decoded_data = filtrar_contenido(decoded_data, area_interes_pdf, primera_pagina, page_number)
                            # Agregar una llave única indicando la remoción de contenido en la tabla
                            texto = f"(Llave_Unica_Tabla_{page_number+1}_{table_idx+1})"
                            decoded_data = decoded_data + agregar_texto_a_pagina(new_pdf, page_number, left, top + ((bottom - top)/2), texto)
                        
                        if primera_pagina == 0:
                            primera_pagina = None

                        # Si el contenido no cambió, continuar
                        if decoded_data == obj.read_bytes().decode('latin1', errors='ignore'):
                            continue

                        # Crear un nuevo flujo con el contenido filtrado y reemplazar el original
                        new_stream = pikepdf.Stream(temp_pdf, decoded_data.encode('latin1', errors='ignore'))
                        page_obj[key] = new_stream

                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f"[!] Error al procesar el objeto en Página {page_number + 1}: {e}")
                    print(f"[!] Detalles del error:\n{error_trace}")

        else:
            page_copy = original_page

        # Agregar la página modificada al nuevo PDF
        new_pdf.pages.append(page_copy)

    # Remover recursos sin referenciar
    new_pdf.remove_unreferenced_resources()

    # Convertir la carpeta de destino a ruta larga para Windows
    folder_path_ruta_larga = convertir_a_ruta_larga(folder_path)
    new_pdf.save(folder_path_ruta_larga + r"\documento_verticalizado_llaves_tablas.pdf")
    
    pdf_bytes_llaves_tabla_escrita = io.BytesIO()
    new_pdf.save(pdf_bytes_llaves_tabla_escrita)
    pdf_bytes.seek(0)  # Reiniciar el buffer
    if Config.DEBUG_PRINTS:
        print("\nProceso finalizado: Nuevo PDF guardado como 'documento_verticalizado_llaves_tablas.pdf'.")
    return pdf_bytes_llaves_tabla_escrita
