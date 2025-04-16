import pikepdf
import zlib
import re
import traceback
import io
import Config

def elemento_en_area(x, y, area):
    """
    Determina si un punto (x, y) está dentro del área de interés.

    Nota: La función devuelve el valor NEGADO. Es decir, 
          retorna True si el punto NO está dentro del área, y False si está.
    
    :param x: Coordenada X del punto.
    :param y: Coordenada Y del punto.
    :param area: Tuple (ax1, ay1, ax2, ay2) que define el área.
    :return: Booleano indicando si el punto está fuera del área.
    """
    ax1, ay1, ax2, ay2 = area
    return not (ax1 <= x <= ax2 and ay1 <= y <= ay2)


def filtrar_contenido(decoded_data, area_interes, primera_pagina, page_number, page):
    """
    Filtra el contenido de un flujo de la página eliminando líneas que se encuentren
    dentro del área de interés. Esto se utiliza para eliminar texto, líneas vectoriales,
    comandos de dibujo y otros elementos que no se desean conservar en determinadas áreas.

    El proceso consiste en:
      - Dividir el contenido en líneas.
      - Actualizar la posición actual mediante la detección de transformaciones (Tm y Td).
      - Evaluar cada línea: se eliminan aquellas cuyo punto de referencia (current_x, current_y)
        caiga dentro del área de interés.
      - También se detectan comandos de dibujo de rectángulos y se evalúa si deben eliminarse.
      - Finalmente, se unen las líneas que no se eliminaron.

    :param decoded_data: Cadena de texto decodificada del flujo de la página.
    :param area_interes: Tuple (ax1, ay1, ax2, ay2) que define el área donde se filtrará el contenido.
    :param primera_pagina: Indicador para ejecutar acciones de depuración en la primera página.
    :param page_number: Número de la página actual (0-indexed).
    :param page: Objeto o diccionario que representa la página (para referencia adicional si fuera necesario).
    :return: Cadena resultante con las líneas (comandos) que no están dentro del área de interés.
    """
    text_chunks = []      # Lista para acumular las líneas que se conservarán
    current_x, current_y = 0, 0  # Coordenadas iniciales (se actualizarán con Tm/Td)

    eliminar = False  # Bandera para determinar si se debe eliminar la línea

    lineas_codificadas = []  # (No se utiliza en el código actual, pero puede servir para depuración)

    # Dividir el contenido del flujo en líneas
    lines = decoded_data.split("\n")
    if page_number == 0 and primera_pagina == 0:
        # Inicialización para la primera página (comentarios de depuración opcionales)
        primera_pagina = 1

    # Iterar sobre cada línea del flujo
    for line in lines:
        eliminar = False  # Reiniciar la bandera para cada línea

        # Buscar comandos de transformación Tm que establecen la matriz de transformación
        tm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) Tm', line)
        if tm_match:
            # Actualizar current_x, current_y según los valores obtenidos
            _, _, _, _, current_x, current_y = map(float, tm_match.groups())

        # Buscar comandos de desplazamiento Td que mueven la posición del texto
        td_match = re.search(r'([-0-9.]+) ([-0-9.]+) Td', line)
        if td_match:
            dx, dy = map(float, td_match.groups())
            current_x += dx
            current_y += dy

        # Detectar líneas de texto delimitadas por Tj
        text_match = re.search(r'\[((?:\([^)]*\)|<[^>]+>)[^]]*)\] T[Jj]', line)
        if text_match:
            text = text_match.group(1)
            # Usar current_x y current_y para determinar la posición donde se ubica el texto
            x1, y1 = current_x, current_y
            # Se decide eliminar la línea si el punto (x1, y1) está dentro del área de interés
            eliminar = elemento_en_area(x1, y1, area_interes)

            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar texto fragmentado usando TJ (se extraen todos los fragmentos y se unen)
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            text = "".join(tj_match)
            x1, y1 = current_x, current_y
            eliminar = elemento_en_area(x1, y1, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar comandos de dibujo de líneas: 'm' para movimiento inicial y 'l' para trazar línea
        vector_match = re.search(r'([-0-9.]+) ([-0-9.]+) m', line)
        line_match = re.search(r'([-0-9.]+) ([-0-9.]+) l', line)
        if vector_match:
            x, y = map(float, vector_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Vector: Movimiento a ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")
        if line_match:
            x, y = map(float, line_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Vector: Línea a ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar comandos de dibujo de rectángulos (re)
        rect_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) re', line)
        if rect_match:
            x, y, w, h = map(float, rect_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Rectángulo: ({x}, {y}, {w}, {h}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")
        
        # Comentado: Detección de imágenes en XObjects (se omite este procesamiento)
        # ...

        # Detectar comandos de transformación 'cm' para actualizar la posición en el flujo
        cm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) cm', line)
        if cm_match:
            a, b, c, d, e, f = map(float, cm_match.groups())
            current_x, current_y = e, f  # Actualizar posición según la transformación

        # Detectar el uso del comando 'Do' para imágenes y, si se debe eliminar, se remueve la línea
        do_match = re.search(r'/([A-Za-z0-9]+)\s+Do', line)
        if do_match:
            obj_id = do_match.group(1)
            eliminar_img = elemento_en_area(current_x, current_y, area_interes)
            if primera_pagina == 1 and Config.DEBUG_PRINTS:
                print(f"Imagen detectada en ({current_x}, {current_y}) - {'[ELIMINADO]' if eliminar_img else '[MANTENIDO]'}")
            if eliminar_img:
                # Eliminar la referencia a la imagen reemplazándola por cadena vacía
                line = re.sub(r'/([A-Za-z0-9]+)\s+Do', '', line)

        # Solo se conservan las líneas que no se hayan marcado para eliminar
        if not eliminar:
            text_chunks.append(line)

    # Unir las líneas filtradas en una sola cadena
    return "\n".join(text_chunks)


def eliminar_elementos_area(crop_data, pdf_bytes, folder_path):
    """
    Elimina elementos internos (texto, vectores, etc.) dentro de las áreas definidas en crop_data.
    
    El proceso es el siguiente:
      1. Se asegura que el flujo de bytes del PDF esté al inicio.
      2. Se abre el PDF original con pikepdf.
      3. Se crea un nuevo PDF en el que se agregarán las páginas modificadas.
      4. Se agrupan las áreas de interés por página.
      5. Para cada página con áreas definidas:
         - Se crea una copia de la página original.
         - Se convierte el sistema de coordenadas de Matplotlib a las coordenadas del PDF (invirtiendo el eje Y).
         - Se recorre el contenido de la página y se filtra (usando filtrar_contenido) para eliminar líneas
           que se encuentren dentro del área de interés.
         - Se reemplaza el contenido original por el contenido filtrado.
         - Se añade la página modificada al nuevo PDF.
      6. Se guarda el nuevo PDF en la carpeta destino.
    
    :param crop_data: Lista de tuplas (page_number, area) donde area es (left, top, right, bottom) en coordenadas de Matplotlib.
    :param pdf_bytes: BytesIO del PDF original.
    :param folder_path: Carpeta donde se guardará el PDF modificado.
    :return: BytesIO del nuevo PDF con los elementos en las áreas eliminados.
    """
    primera_pagina = 0

    # Asegurarse de que el flujo de bytes comience desde el inicio
    pdf_bytes.seek(0)

    # Abrir el PDF original con pikepdf
    pdf = pikepdf.open(pdf_bytes)

    # Crear un nuevo PDF para almacenar las páginas modificadas
    new_pdf = pikepdf.Pdf.new()

    # Agrupar las áreas de interés por página
    page_areas = {}
    for page_number, rect in crop_data:
        if page_number not in page_areas:
            page_areas[page_number] = []
        page_areas[page_number].append(rect)

    # Iterar sobre cada página con áreas definidas
    for page_number, areas_interes in page_areas.items():
        if Config.DEBUG_PRINTS:
            print(f"\nProcesando Página {page_number + 1} ({len(areas_interes)} áreas)")
        original_page = pdf.pages[page_number]
        # Obtener dimensiones de la página desde su mediabox (usado para la conversión de coordenadas)
        _, _, width, height = original_page.mediabox  

        # Para cada área de interés, crear una copia de la página y filtrar su contenido
        for area_interes in areas_interes:
            if Config.DEBUG_PRINTS:
                print(f"\nÁrea de interés en la Página {page_number + 1}: {area_interes}")

            # Crear un PDF temporal para procesar esta copia de la página
            temp_pdf = pikepdf.Pdf.new()
            temp_pdf.pages.append(original_page)
            page_copy = temp_pdf.pages[0]

            # Convertir coordenadas de Matplotlib al sistema del PDF (invirtiendo el eje Y)
            left, top, right, bottom = area_interes
            top_pdf = float(height) - bottom
            bottom_pdf = float(height) - top

            # Definir el área de interés en coordenadas del PDF
            area_interes_pdf = (left, top_pdf, right, bottom_pdf)

            page_obj = page_copy.obj

            # Recorrer cada objeto en la página y filtrar el contenido que cae en el área de interés
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

                        # Filtrar el contenido para eliminar elementos en el área de interés
                        new_content = filtrar_contenido(decoded_data, area_interes_pdf, primera_pagina, page_number, page_copy)
                        if primera_pagina == 0:
                            primera_pagina = None

                        # Si no se modificó nada, continuar sin reemplazar
                        if new_content == decoded_data:
                            continue

                        # Crear un nuevo flujo con el contenido filtrado y reemplazar el original
                        new_stream = pikepdf.Stream(temp_pdf, new_content.encode('latin1', errors='ignore'))
                        page_obj[key] = new_stream
                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f"[!] Error en Página {page_number + 1}: {e}")
                    print(f"[!] Detalles del error:\n{error_trace}")

            # Agregar la página modificada al nuevo PDF final
            new_pdf.pages.append(page_copy)

    # Guardar el nuevo PDF modificado en la carpeta destino
    new_pdf.save(folder_path + r"\documento_verticalizado.pdf")
    
    pdf_bytes = io.BytesIO()
    new_pdf.save(pdf_bytes)
    pdf_bytes.seek(0)  # Reiniciar el buffer
    if Config.DEBUG_PRINTS:
        print("\nProceso finalizado: Nuevo PDF guardado como 'documento_verticalizado.pdf'.")
    return pdf_bytes
