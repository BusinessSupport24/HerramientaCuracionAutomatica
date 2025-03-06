import pikepdf
import zlib
import re
import io
import traceback
import Config

def elemento_en_area(x, y, area):
    """
    Determina si un punto (x, y) está dentro del área de interés.
    """
    ax1, ay1, ax2, ay2 = area
    return ax1 <= x <= ax2 and ay1 <= y <= ay2

def agregar_texto_a_pagina(pdf, page_number, x, y, texto, font_name="/F1", font_size=8.04, color="0 G"):
    """
    Agrega un texto en una página PDF con configuración completa.
    
    Parámetros:
        - pdf_path (str): Ruta del PDF de entrada.
        - output_path (str): Ruta del PDF de salida.
        - page_number (int): Número de la página (0-indexed).
        - x (float): Posición X del texto.
        - y (float): Posición Y del texto.
        - texto (str): Texto a escribir.
        - font_name (str): Nombre de la fuente en el PDF (ejemplo: "/F1").
        - font_size (float): Tamaño de la fuente.
        - color (str): Color del texto en sintaxis PDF ("0 G" para negro, "1 0 0 rg" para rojo).
    """
    # Abrir el PDF
    # pdf = pikepdf.Pdf.open(pdf_path)

    # Obtener la página seleccionada
    # page = pdf.pages[page_number]

    # Construir el contenido de texto en sintaxis PDF
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

    # # Crear un nuevo flujo de contenido
    # new_stream = pikepdf.Stream(pdf, text_stream.encode('latin1'))

    # # Agregar el texto al contenido de la página
    # page.contents_add(new_stream)

    if Config.DEBUG_PRINTS:
        print(f"Texto añadido en página {page_number + 1} en coordenadas ({x}, {y}).")

    return text_stream

def filtrar_contenido(decoded_data, area_interes, primera_pagina,page_number):
    already_writed = False
    is_rectangle = False
    is_text = False
    is_line = False
    is_vector = False

    ax1, ay1, ax2, ay2 = area_interes

    """
    Filtra el contenido del flujo de la página eliminando texto y vectores dentro del área de interés.
    """
    text_chunks = []
    current_x, current_y = 0, 0  # Coordenadas iniciales

    eliminar = False

    lineas_codificadas = []

    lines = decoded_data.split("\n")
    if page_number == 0 and primera_pagina == 0 and Config.DEBUG_PRINTS:
        # print("Decodificado")
        # print(decoded_data[:30000])
        # print("Lineas")
        # print(lines)
        primera_pagina = 1
        # print(lines)

    # if page_number == 0:
    #     print("Lineas",lines)
    #     # print(lines)

    for i, line in enumerate(lines):
        # if Config.DEBUG_PRINTS:
        #   print(line)
        # line = lines[i]
        eliminar = False  # Bandera para eliminar la línea

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

        # Detectar texto con Tj
        text_match = re.search(r'\[((?:\([^)]*\)|<[^>]+>)[^]]*)\] T[Jj]', line)
        if text_match:
            text = text_match.group(1)

            # Solo usamos x1, y1
            x1, y1 = current_x, current_y
            is_text = True
            eliminar = elemento_en_area(x1, y1, area_interes)

            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar texto con TJ (fragmentado)
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            text = "".join(tj_match)
            x1, y1 = current_x, current_y
            # is_text = True
            eliminar = elemento_en_area(x1, y1, area_interes)

            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar líneas vectoriales (l) y movimiento (m)
        vector_match = re.search(r'([-0-9.]+) ([-0-9.]+) m', line)  # Movimiento inicial
        line_match = re.search(r'([-0-9.]+) ([-0-9.]+) l', line)  # Línea

        if vector_match:
            x, y = map(float, vector_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            is_vector = True
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Vector: Movimiento a ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        if line_match:
            x, y = map(float, line_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            is_line = True
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Vector: Línea a ({x}, {y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar rectángulos (re)
        rect_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) re', line)
        if rect_match:
            x, y, w, h = map(float, rect_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
            is_rectangle = True
            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Rectángulo: ({x}, {y}, {w}, {h}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # # Detectar imágenes en XObjects
        # xobject_match = re.search(r'/XObject\s+(\d+\s+\d+\s+obj)', line)
        # if xobject_match:
        #     obj_id = xobject_match.group(1)
        #     eliminar = elemento_en_area(current_x, current_y, area_interes)
        #     if primera_pagina == 0 and Config.DEBUG_PRINTS:
        #         print(f"Imagen: XObject {obj_id} en ({current_x}, {current_y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar imágenes usadas en la página (Do)

        # Detectar matrices de transformación (cm) para obtener coordenadas de la imagen
        cm_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) cm', line)
        if cm_match:
            a, b, c, d, e, f = map(float, cm_match.groups())
            current_x, current_y = e, f  # e, f representan la posición de la imagen

        # Detectar uso de imágenes en la página (Do), verificando que sean imágenes
        do_match = re.search(r'/([A-Za-z0-9]+)\s+Do', line)
        if do_match:
            obj_id = do_match.group(1)
            # # Buscar si el objeto es una imagen
            # is_image = re.search(rf'/Subtype\s*/Image\s+/Name\s+/{obj_id}', "\n".join(lines))
            # if is_image:
            eliminar_img = elemento_en_area(current_x, current_y, area_interes)
            if primera_pagina == 1 and Config.DEBUG_PRINTS:
                print(f"Imagen detectada en ({current_x}, {current_y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")
            if eliminar_img:
                line = re.sub(r'/([A-Za-z0-9]+)\s+Do', '', line)  # Solo elimina `/Image20 Do`
            # if Config.DEBUG_PRINTS:
            #   print(area_interes)
            #   print("linea",line)
            #   print(f"Imagen: Referencia Do a {obj_id} en ({current_x}, {current_y})")

        # # Detectar si el objeto es una imagen (Subtype /Image)
        # image_match = re.search(r'/Subtype\s*/Image', line)
        # if image_match:
        #     eliminar = elemento_en_area(current_x, current_y, area_interes)
        #     if primera_pagina == 0 and Config.DEBUG_PRINTS:
        #         print(f"Imagen detectada en ({current_x}, {current_y}) - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")


        # Solo agregamos líneas que no sean eliminadas
        if not eliminar:
            text_chunks.append(line)


    return "\n".join(text_chunks)
    

def eliminar_elementos_area(crop_data, pdf_bytes,folder_path):
    primera_pagina = 0

    # Asegurarse de que el flujo de bytes está al inicio
    pdf_bytes.seek(0)

    # Cargar el PDF original
    pdf = pikepdf.open(pdf_bytes)

    # Crear un nuevo PDF modificado
    new_pdf = pikepdf.Pdf.new()

    # Agrupar áreas de interés por número de página
    page_areas = {}

    for i in range(len(pdf.pages)):
        page_areas[i] = []
    for page_number, rect in crop_data:
        page_areas[page_number].append(rect)

    if Config.DEBUG_PRINTS:
        print("Page_Areas")
        print(page_areas)

    # Iterar sobre cada página con áreas de interés
    for page_number, areas_interes in page_areas.items():
        if Config.DEBUG_PRINTS:
            print(f"\nProcesando Página {page_number + 1} con {len(areas_interes)} áreas de interés")

        # Obtener la página original sin modificarla
        original_page = pdf.pages[page_number]
        
        # Crear un nuevo PDF temporal para modificar la página original
        temp_pdf = pikepdf.Pdf.new()
        temp_pdf.pages.append(original_page)
        page_copy = temp_pdf.pages[0]

        # Obtener el tamaño de la página (ancho, alto)
        _, _, width, height = original_page.mediabox

        if Config.DEBUG_PRINTS:
            print("AREAS DE INTERES")
            print(len(areas_interes))

        if len(areas_interes)>0:

            # Convertir coordenadas de Matplotlib a PikePDF (invertir Y)
            areas_interes_pdf = []
            for area_interes in areas_interes:
                table_idx, left, top, right, bottom = area_interes
                top_pdf = float(height) - bottom
                bottom_pdf = float(height) - top
                areas_interes_pdf.append((table_idx,(left, top_pdf, right, bottom_pdf)))

            page_obj = page_copy.obj

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

                        # Filtrar todas las áreas de interés en una sola copia de la página
                        for table_idx, area_interes_pdf in areas_interes_pdf:
                            left, top, right, bottom = area_interes_pdf
                            decoded_data = filtrar_contenido(decoded_data, area_interes_pdf, primera_pagina, page_number)
                            texto = f"(Llave_Unica_Tabla_{page_number+1}_{table_idx+1})"
                            decoded_data = decoded_data+ agregar_texto_a_pagina(new_pdf,page_number, left, top+((bottom-top)/2), texto)
                            # agregar_texto_a_pagina(temp_pdf, page_copy, ax1, ay1, f"Llave_unica_tabla_{page_number}_{table_idx}", font_name="/F1", font_size=8.04, color="0 G")

                        if primera_pagina == 0:
                            primera_pagina = None

                        # Si no hubo cambios, no modificar la página
                        if decoded_data == obj.read_bytes().decode('latin1', errors='ignore'):
                            continue

                        # Modificar solo el contenido sin afectar imágenes ni gráficos
                        new_stream = pikepdf.Stream(temp_pdf, decoded_data.encode('latin1', errors='ignore'))

                        # Reemplazar el contenido modificado
                        page_obj[key] = new_stream

                except Exception as e:
                    error_trace = traceback.format_exc()
                    print(f"[!] Error al procesar el objeto en Página {page_number + 1}: {e}")
                    print(f"[!] Detalles del error:\n{error_trace}")
        else:
            page_copy = original_page
            areas_interes_pdf = []

        new_pdf.pages.append(page_copy)

        # if len(areas_interes_pdf)>0:
        #     for table_idx, area_interes_pdf in areas_interes_pdf:
        #         ax1, ay1, ax2, ay2 = area_interes_pdf
        #         if Config.DEBUG_PRINTS:
        #             print("Cantidad de paginas en el nuevo pdf")
        #             print(len(new_pdf.pages))
        #         #   print("Numero de la pagina a agregar el texto")
        #         #   print(page_number)
        #         texto = f"(Llave_Unica_Tabla_{page_number+1}_{table_idx+1})"
        #         if Config.DEBUG_PRINTS:
        #             print("Agregando el texto: ",texto)
        #         agregar_texto_a_pagina(new_pdf,page_number, ax1, ay1+((ay2-ay1)/2), texto)



    # Guardar el PDF sin texto ni vectores en las áreas de interés
    new_pdf.remove_unreferenced_resources()
    new_pdf.save(folder_path+r"\documento_verticalizado_llaves_tablas.pdf")
    
    pdf_bytes_llaves_tabla_escrita = io.BytesIO()
    new_pdf.save(pdf_bytes_llaves_tabla_escrita)
    pdf_bytes.seek(0)  # Volver al inicio del buffer

    if Config.DEBUG_PRINTS:
        print("\nProceso finalizado: Se ha guardado el nuevo PDF con los elementos dentro de las áreas eliminadas como documento_recortado_tb_remplazadas.pdf.")

    return pdf_bytes_llaves_tabla_escrita

