import pikepdf
import zlib
import re
import traceback
import io
import Config

def elemento_en_area(x, y, area):
    """
    Determina si un punto (x, y) está dentro del área de interés.
    """
    ax1, ay1, ax2, ay2 = area
    return not (ax1 <= x <= ax2 and ay1 <= y <= ay2)


def filtrar_contenido(decoded_data, area_interes, primera_pagina,page_number,page):
    """
    Filtra el contenido del flujo de la página eliminando texto y vectores dentro del área de interés.
    """
    text_chunks = []
    current_x, current_y = 0, 0  # Coordenadas iniciales

    eliminar = False

    lineas_codificadas = []

    lines = decoded_data.split("\n")
    if page_number == 0 and primera_pagina == 0:
        # if Config.DEBUG_PRINTS:
        #   print("Decodificado")
        #   print(decoded_data[:30000])
        #   print("Lineas")
        #   print(lines)
        primera_pagina = 1
        #   print(lines)

    # if page_number == 0 and Config.DEBUG_PRINTS:
    #     print("Lineas",lines)
    #     # print(lines)

    # def extraer_xobjects(page):
    #     """Extrae y decodifica el contenido de los XObjects encontrados en la página."""
    #     xobjects_contenido = []
    #     if "/Resources" in page and "/XObject" in page["/Resources"]:
    #         xobjects = page["/Resources"]["/XObject"]
    #         print("XObjects detectados en la página:", list(xobjects.keys()))
    #         for xobj_name in list(xobjects):
    #             xobj = xobjects[xobj_name]
    #             if isinstance(xobj, pikepdf.Stream):
    #                 try:
    #                     contenido_xobj = xobj.read_bytes().decode("latin1", errors="ignore")
    #                     print(f"Contenido decodificado de XObject {xobj_name}:")
    #                     print(contenido_xobj[:10000])  # Imprime una parte del contenido del XObject
    #                     xobjects_contenido.extend(contenido_xobj.split("\n"))
    #                 except pikepdf.PdfError:
    #                     print(f"No se pudo leer el contenido de XObject {xobj_name}, posiblemente está codificado.")
    #     return xobjects_contenido

    # # Extraer y agregar contenido de XObjects antes de procesar las líneas de la página
    # lines = extraer_xobjects(page) + lines

    for line in lines:
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
            eliminar = elemento_en_area(x1, y1, area_interes)

            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar texto con TJ (fragmentado)
        tj_match = re.findall(r'\((.*?)\)', line)
        if tj_match and "TJ" in line:
            text = "".join(tj_match)
            x1, y1 = current_x, current_y
            eliminar = elemento_en_area(x1, y1, area_interes)

            if primera_pagina == 0 and Config.DEBUG_PRINTS:
                print(f"Texto: '{text}' - X1: {x1}, Y1: {y1} - {'[ELIMINADO]' if eliminar else '[MANTENIDO]'}")

        # Detectar líneas vectoriales (l) y movimiento (m)
        vector_match = re.search(r'([-0-9.]+) ([-0-9.]+) m', line)  # Movimiento inicial
        line_match = re.search(r'([-0-9.]+) ([-0-9.]+) l', line)  # Línea

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

        # Detectar rectángulos (re)
        rect_match = re.search(r'([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) re', line)
        if rect_match:
            x, y, w, h = map(float, rect_match.groups())
            eliminar = elemento_en_area(x, y, area_interes)
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
                # print(area_interes)
                # print("linea",line)
                # print(f"Imagen: Referencia Do a {obj_id} en ({current_x}, {current_y})")

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
    for page_number, rect in crop_data:
        if page_number not in page_areas:
            page_areas[page_number] = []
        page_areas[page_number].append(rect)

    # Iterar sobre cada página con áreas de interés
    for page_number, areas_interes in page_areas.items():
        if Config.DEBUG_PRINTS:
            print(f"\nProcesando Página {page_number + 1} ({len(areas_interes)} copias)")

        # Obtener la página original sin modificarla
        original_page = pdf.pages[page_number]

        # Obtener el tamaño de la página (ancho, alto)
        _, _, width, height = original_page.mediabox  

        # Para cada área de interés, hacer una copia independiente de la página original
        for area_interes in areas_interes:
            if Config.DEBUG_PRINTS:
                print(f"\nÁrea de interés en la copia de la página {page_number + 1}: {area_interes}")

            # **Crear un nuevo PDF temporal para hacer la copia**
            temp_pdf = pikepdf.Pdf.new()
            temp_pdf.pages.append(original_page)  # Copiar la página original
            page_copy = temp_pdf.pages[0]  # Obtener la copia

            # Convertir coordenadas Matplotlib → PikePDF (invertir Y)
            left, top, right, bottom = area_interes
            top_pdf = float(height) - bottom
            bottom_pdf = float(height) - top

            # Modificar área_interes para que funcione con pikepdf
            area_interes_pdf = (left, top_pdf, right, bottom_pdf)

            page_obj = page_copy.obj

            # if primera_pagina == 1 and Config.DEBUG_PRINTS:
                # print("objeto de la página\n", page_obj)

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

                        # **Filtrar SOLO el área de interés de esta copia**
                        new_content = filtrar_contenido(decoded_data, area_interes_pdf, primera_pagina,page_number, page_copy)

                        if primera_pagina == 0:
                            primera_pagina = None

                        # Si no hubo cambios, no modificar la página
                        if new_content == decoded_data:
                            continue

                        # Modificar solo el contenido sin afectar imágenes ni gráficos
                        new_stream = pikepdf.Stream(temp_pdf, new_content.encode('latin1', errors='ignore'))

                        # Reemplazar el contenido modificado
                        page_obj[key] = new_stream
                except Exception as e:
                    # Obtener detalles del error y la línea donde ocurrió
                    error_trace = traceback.format_exc()
                    print(f"[!] Error al procesar el objeto en Página {page_number + 1}: {e}")
                    print(f"[!] Detalles del error:\n{error_trace}")

            # **Agregar la copia procesada al PDF final**
            new_pdf.pages.append(page_copy)

    # Guardar el PDF sin texto ni vectores en las áreas de interés
    new_pdf.save(folder_path+r"\documento_verticalizado.pdf")
    
    pdf_bytes = io.BytesIO()
    new_pdf.save(pdf_bytes)
    pdf_bytes.seek(0)  # Volver al inicio del buffer

    if Config.DEBUG_PRINTS:
        print("\nProceso finalizado: Se ha guardado el nuevo PDF con los elementos dentro de las áreas eliminadas como documento_recortado.pdf. ")

    return pdf_bytes
