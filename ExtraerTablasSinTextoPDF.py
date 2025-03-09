import pdfplumber
import fitz  # PyMuPDF
import pikepdf
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button
import numpy as np
import os
from tabulate import tabulate  # Para mostrar tablas en consola de forma bonita
from PIL import Image
from colorama import Style, Fore, Back
import RenderizarTablaHTML as RtHTML
import cv2
import EliminarYEscribirLlavesDeTablas as EYELDT
import sys
import io
import Extraer_Imagenes
import Config
import EliminarYEscribirImagenes
import PasarTextoPlanoAMarkdown
import EnviarImagenesAChatGPT
import RemplazarImagenesDeMarkdown

# ============================
# 1. FUNCION PARA ELIMINAR TEXTO DEL PDF
# ============================
def eliminar_texto_preciso(pdf_bytes, output_path, altura_pagina):
    """Genera un nuevo PDF sin texto en la parte superior."""
    pdf_bytes.seek(0)

    # Cargar el PDF original
    pdf = pikepdf.open(pdf_bytes)

    for page in pdf.pages:
        if "/Contents" not in page:
            continue  # Saltar páginas sin contenido

        contenido_obj = page["/Contents"]
        if isinstance(contenido_obj, pikepdf.Array):  
            contenido_completo = b"".join(p.read_bytes() for p in contenido_obj)
        else:
            contenido_completo = contenido_obj.read_bytes()

        contenido_decodificado = contenido_completo.decode("latin1", errors="ignore")

        # Expresión regular para encontrar comandos de texto en el PDF
        patron_texto = re.compile(r"\((.*?)\)\s*Tj|\[(.*?)\]\s*TJ")
        patron_coordenadas = re.compile(r"([\d\.\-]+) ([\d\.\-]+) Td|([\d\.\-]+) ([\d\.\-]+) Tm")

        lineas_modificadas = []
        eliminar_siguiente_texto = False  

        for line in contenido_decodificado.split("\n"):
            match = patron_coordenadas.search(line)
            if match:
                try:
                    y_pos = float(match.group(2) or match.group(4))  

                    if y_pos > (altura_pagina * (0/3)):  
                        eliminar_siguiente_texto = True
                    else:
                        eliminar_siguiente_texto = False
                except ValueError:
                    pass

            if eliminar_siguiente_texto:
                line = re.sub(patron_texto, "", line)

            lineas_modificadas.append(line)

        nuevo_contenido = "\n".join(lineas_modificadas).encode("latin1")

        if isinstance(contenido_obj, pikepdf.Array):
            for obj in contenido_obj:
                obj.write(nuevo_contenido)
        else:
            contenido_obj.write(nuevo_contenido)

    pdf.save(output_path)
    pdf_bytes_sin_texto = io.BytesIO()
    pdf.save(pdf_bytes_sin_texto)
    pdf_bytes_sin_texto.seek(0)  # Volver al inicio del buffer}
    if Config.DEBUG_PRINTS:
        print(f"PDF sin texto guardado en: {output_path}")
    return pdf_bytes_sin_texto

# ============================
# 2. FUNCION PARA RECORTAR TABLAS Y GUARDAR COMO IMAGEN DE ALTA CALIDAD
# ============================
def crop_and_save_image(original_pdf, page_number, coords, output_path,tabla_actual,lista_tablas):
    """ Recorta la tabla y la guarda como imagen de alta calidad. """
    left, top, right, bottom = coords
    rect = fitz.Rect(left-3, top-4, right+6, bottom+4)
    
    page = original_pdf[page_number]  
    zoom_x, zoom_y = 4.0, 4.0  # Ajusta la calidad (factor de escala)
    mat = fitz.Matrix(zoom_x, zoom_y)  # Transformación para mejorar resolución

    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=True)  # Renderizar imagen con transparencia
    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)

    img.save(output_path, format="PNG", dpi=(300, 300))  # Guardar con alta resolución
    if Config.DEBUG_PRINTS:
        print(f"Imagen de tabla guardada en: {output_path}")

    return RtHTML.image_to_HTML(output_path,tabla_actual)

# ============================
# 3. FUNCION PRINCIPAL: OBTENER TABLAS USANDO EL PDF ORIGINAL
# ============================
def convertir_coordenadas_imagen_a_pdf(coordenadas_celdas, x0, top, x1, bottom,dimensiones_tabla,
                                       left_margin=3, top_margin=4):

    if Config.DEBUG_PRINTS:
        print("x0, x1, top, bottom originales\n",x0,  x1, top, bottom)

    xt1,  xt2, yt1, yt2 = dimensiones_tabla

    if Config.DEBUG_PRINTS:
        print("dimensiones_tabla\n",dimensiones_tabla)
    
    
    # Calcular factores de escala en X y Y
    scale_x = (x1 - x0) / (xt2 - xt1)
    scale_y = (bottom - top) / (yt2 - yt1)

    # Convertir dimensiones detectadas a escala original
    xt1_original = x0 + (xt1 * scale_x)-left_margin
    xt2_original = x0 + (xt2 * scale_x)-left_margin
    yt1_original = top + (yt1 * scale_y)-top_margin
    yt2_original = top + (yt2 * scale_y)-top_margin

    # Imprimir para verificar
    if Config.DEBUG_PRINTS:
        print("Factor de escala X:", scale_x)
        print("Factor de escala Y:", scale_y)
        print("Dimensiones de la tabla en escala original:")
        print("xt1_original:", xt1_original)
        print("xt2_original:", xt2_original)
        print("yt1_original:", yt1_original)
        print("yt2_original:", yt2_original)

    # Ajustar las coordenadas de las celdas
    coordenadas_ajustadas = []
    for id_celda, x, y, w, h in coordenadas_celdas:
        x_original = x0 + (x * scale_x) - left_margin
        y_original = top + (y * scale_y) - top_margin
        w_original = w * scale_x  # Escalar solo el ancho
        h_original = h * scale_y  # Escalar solo la altura

        if Config.DEBUG_PRINTS:
            print("x_original,w_original,y_original,h_original\n",x_original,w_original,y_original,h_original)
        coordenadas_ajustadas.append((id_celda, x_original, y_original, w_original, h_original))


    return coordenadas_ajustadas


# ============================
# 4. FUNCION ASIGNAR TEXTO: ASIGNA EL TEXTO SEGUN LA COORDENADA MAS CERCANA
# ============================

def asignar_texto_a_estructura(tabla_estructura, coordenadas_celdas_convertidas, textos_pdf):
    """
    Asigna el contenido a cada celda en la estructura de la tabla,
    verificando si el centro promedio del texto está dentro de los límites de la celda.

    Parámetros:
        tabla_estructura (list): Lista de listas representando la estructura de la tabla con id_celda y coordenadas.
        coordenadas_celdas_convertidas (list): Lista de tuplas (id_celda, x_original, y_original, w_original, h_original).
        textos_pdf (list): Lista de textos con sus coordenadas en el PDF [(texto, x_texto, y_texto)].

    Retorna:
        list: Tabla estructura actualizada con los contenidos asignados a cada celda.
    """
    # Diccionario para mapear id_celda a una lista de textos
    contenido_por_celda = {id_celda: [] for id_celda, _, _, _, _ in coordenadas_celdas_convertidas}

    # Asignar cada texto a la celda correcta
    for texto, x_texto, y_texto in textos_pdf:
        for id_celda, x_original, y_original, w_original, h_original in coordenadas_celdas_convertidas:
            x_min, x_max = x_original, x_original + w_original
            y_min, y_max = y_original, y_original + h_original

            if x_min <= x_texto <= x_max and y_min <= y_texto <= y_max:
                contenido_por_celda[id_celda].append((y_texto, x_texto, texto))
                break  # Se encontró la celda correcta, no es necesario seguir buscando

    # Ordenar los textos dentro de cada celda primero por Y y luego por X
    for id_celda in contenido_por_celda:
        contenido_por_celda[id_celda].sort(key=lambda t: (t[0], t[1]))  # Orden por y_texto, luego por x_texto
        contenido_por_celda[id_celda] = " ".join(texto for _, _, texto in contenido_por_celda[id_celda]).strip()

    # Asignar el contenido directamente a la estructura de la tabla
    for fila in tabla_estructura:
        for celda in fila:
            if celda["rowspan"] > 0 and celda["colspan"] > 0:
                if "id_celda" not in celda:
                    celda["id_celda"] = None  # Asignar un valor nulo para evitar errores
                id_celda = celda["id_celda"]
                celda["contenido"] = contenido_por_celda.get(id_celda, "")

    return tabla_estructura  # Retornar la estructura modificada


# ============================
# 4. FUNCION PRINCIPAL: OBTENER TABLAS USANDO EL PDF ORIGINAL
# ============================
def show_pdfplumber_tables_with_buttons(pdf_bytes,folder_path):
    """Muestra las tablas y las guarda como imágenes recortadas desde el PDF sin texto."""
    # Crear PDF sin texto solo para recortar las tablas
    pdf_bytes.seek(0)
    pdf_copy = io.BytesIO(pdf_bytes.getvalue())

    pdf_sin_texto_path = folder_path+r"\documento_temporal_sin_texto.pdf"
    pdf_bytes_sin_texto = eliminar_texto_preciso(pdf_bytes, pdf_sin_texto_path, 800)  

    # Abrir ambos PDFs
    pdf_original = pdfplumber.open(pdf_copy)  # Ahora usamos la copia, no el original
    # pdf_original = pdfplumber.open(io.BytesIO(pdf_bytes.read()))  # Abrir PDF desde memoria
    pdf_sin_texto = fitz.open(stream=pdf_bytes_sin_texto, filetype="pdf")  # Se usa solo para recortes
    total_pages = len(pdf_original.pages)
    
    if Config.DEBUG_PRINTS:
        print(total_pages)
    current_page_idx = 0  

    output_folder = folder_path+r"\tablas_recortadas"
    # os.makedirs(output_folder, exist_ok=True)

    
    fig, ax = plt.subplots(figsize=(11, 8), dpi = 150)
    plt.subplots_adjust(bottom=0.15)
    ax.axis("off")

    lista_tablas = []
    crop_data=[]

    def display_page(page_idx):
        ax.clear()
        ax.axis("off")

        page = pdf_original.pages[page_idx]  
        # Obtener la imagen de la página
        page_image = page.to_image(resolution=72)
        pil_img = page_image.original  
        img_array = np.array(pil_img)
        ax.imshow(img_array)

        # Detectar tablas en la página
        tables = page.find_tables()
        if Config.DEBUG_PRINTS:
            print(tables)

            print(f"\n=== Página {page_idx + 1} ===")

        # Función para verificar si una tabla está dentro de otra
        def is_inside(inner_bbox, outer_bbox):
            x0_inner, top_inner, x1_inner, bottom_inner = inner_bbox
            x0_outer, top_outer, x1_outer, bottom_outer = outer_bbox
            
            return (x0_outer <= x0_inner <= x1_inner <= x1_outer) and (top_outer <= top_inner <= bottom_inner <= bottom_outer)

        # Lista para almacenar tablas que están contenidas dentro de otras
        contained_tables = set()

        # Comparar cada tabla con todas las demás
        for i, table_a in enumerate(tables):
            bbox_a = table_a.bbox  # Coordenadas de la tabla A

            for j, table_b in enumerate(tables):
                if i != j:  # No comparar la tabla consigo misma
                    bbox_b = table_b.bbox  # Coordenadas de la tabla B
                    
                    if is_inside(bbox_a, bbox_b):
                        contained_tables.add(i)  # Marcar tabla como contenida

        # Filtrar tablas que no están contenidas dentro de otra
        filtered_tables = [table for idx, table in enumerate(tables) if idx not in contained_tables]

        tables = filtered_tables

        if not tables:
            if Config.DEBUG_PRINTS:
                print("  No se han encontrado tablas en esta página.")
        elif Config.MOVIL == False and page_idx<2:
            if Config.DEBUG_PRINTS:
                print(f" Página {page_idx}, se ignora")
        else:     
            path_tablas = os.path.join(folder_path,"tablas_html")

            if not os.path.exists(path_tablas):  # Verifica si la carpeta no existe
                os.mkdir(path_tablas)  # Crea la carpeta
                if Config.DEBUG_PRINTS:
                    print(f"Carpeta '{path_tablas}' creada con éxito.")
            else:
                if Config.DEBUG_PRINTS:
                    print(f"La carpeta '{path_tablas}' ya existe.")
            for table_idx, table in enumerate(tables):
                x0, top, x1, bottom = table.bbox
                if Config.DEBUG_PRINTS:
                    print(f"  - Tabla {table_idx + 1} | BBox = ({x0:.2f}, {top:.2f}) - ({x1:.2f}, {bottom:.2f})")

                # Obtener la estructura de la tabla
                data = table.extract()
                if not data:
                    if Config.DEBUG_PRINTS:
                        print("    (Tabla vacía o no se pudo extraer contenido)")
                else:
                    headers = data[0]  # Encabezados de la tabla
                    rows = data[1:] if len(data) > 1 else []
                    tabla_formateada = tabulate(rows, headers=headers, tablefmt="fancy_grid")
                    if Config.DEBUG_PRINTS:
                        print("    Contenido de la tabla:\n", tabla_formateada)

                # Verificar la estructura de data antes de iterar
                if Config.DEBUG_PRINTS:
                    print("\n=== Data Extraída ===")
                for i, row in enumerate(data):
                    if Config.DEBUG_PRINTS:
                        print(f"Fila {i}: {row}")

                # Lista para almacenar datos de celdas con coordenadas
                celda_texto_centros = []
                textos_pdf = []
                        
                # Diccionario para rastrear celdas procesadas y evitar duplicados
                procesadas = {}

                # EXTRAER LOS ENCABEZADOS
                for col_idx, header_text in enumerate(headers):
                    if col_idx < len(table.rows[0].cells):  # Verificar que haya una celda
                        header_cell = table.rows[0].cells[col_idx]
                        if header_cell is None:
                            continue

                        cell_x0, cell_top, cell_x1, cell_bottom = header_cell  

                        # Calcular el centro del encabezado
                        centro_x = (cell_x0 + cell_x1) / 2
                        centro_y = (cell_top + cell_bottom) / 2

                        if Config.DEBUG_PRINTS:
                            print(f"    - Encabezado ({col_idx}) | BBox: ({cell_x0:.2f}, {cell_top:.2f}) - ({cell_x1:.2f}, {cell_bottom:.2f})")
                            print(f"      - Contenido extraído: {header_text}")

                        # Evitar duplicados de encabezados
                        if (0, col_idx) in procesadas:
                            continue  # Si ya lo procesamos, lo omitimos

                        # Agregar a textos_pdf y celda_texto_centros
                        textos_pdf.append((header_text, centro_x, centro_y))
                        celda_texto_centros.append({
                            "fila": 0,
                            "columna": col_idx,
                            "bbox": (cell_x0, cell_top, cell_x1, cell_bottom),
                            "centro_texto": (centro_x, centro_y),
                            "contenido": header_text
                        })

                        # Marcar como procesado
                        procesadas[(0, col_idx)] = True

                #RECORRER `data` EN ORDEN Y ASIGNAR LAS COORDENADAS CORRECTAS
                for row_idx, row_data in enumerate(data[1:]):  # Omitimos la fila de encabezados (data[0])
                    for col_idx, texto_celda in enumerate(row_data):
                        # Buscar la celda correspondiente en table.rows
                        try:
                            cell = table.rows[row_idx + 1].cells[col_idx]  # +1 porque data[0] son los encabezados
                        except IndexError:
                            continue  # Si no existe la celda, saltar

                        if cell is None:
                            continue  # No hay celda en esa posición

                        # Extraer coordenadas de la celda
                        cell_x0, cell_top, cell_x1, cell_bottom = cell  

                        # Asegurar que texto_celda no sea None
                        if texto_celda is None:
                            texto_celda = ""  # Evitar errores en .strip()

                        if Config.DEBUG_PRINTS:
                            print(f"      Celda ({row_idx+1}, {col_idx}) | BBox: ({cell_x0:.2f}, {cell_top:.2f}) - ({cell_x1:.2f}, {cell_bottom:.2f})")
                            print(f"        - Contenido extraído de la tabla: {texto_celda}")

                        if texto_celda.strip():  # Si la celda no está vacía
                            # Calcular el centro de la celda basado en su bounding box
                            centro_x = (cell_x0 + cell_x1) / 2
                            centro_y = (cell_top + cell_bottom) / 2

                            # Guardar en textos_pdf para su uso en asignar_texto_a_estructura
                            textos_pdf.append((texto_celda, centro_x, centro_y))

                            # Guardar en celda_texto_centros para referencia adicional
                            celda_texto_centros.append({
                                "fila": row_idx + 1,  # +1 porque omitimos los encabezados
                                "columna": col_idx,
                                "bbox": (cell_x0, cell_top, cell_x1, cell_bottom),
                                "centro_texto": (centro_x, centro_y),
                                "contenido": texto_celda
                            })

                output_img_path = folder_path+r"\imagenTemporal.png"
                tabla_actual = os.path.join(output_folder, f"tabla_{page_idx + 1}_{table_idx + 1}.png")
                tabla_generada,coordenadas_celdas, centros_celdas, image_width, image_height, dimensiones_tabla = crop_and_save_image(pdf_sin_texto, page_idx, (x0, top, x1, bottom), output_img_path,tabla_actual,lista_tablas)
                # coordenadas_celdas_convertidas = [convertir_coordenadas_imagen_a_pdf(id_celda, x, y, w, h, x0, top, zoom_x=4.0, zoom_y=4.0)for id_celda, x, y, w, h in cordenadas_celdas]
                if len(coordenadas_celdas) > 0:
                    coordenadas_celdas_convertidas = convertir_coordenadas_imagen_a_pdf(
                        coordenadas_celdas, x0, top, x1,bottom,dimensiones_tabla,
                        left_margin=3, top_margin=4
                    )
                    if Config.DEBUG_PRINTS:
                        print("Centros de celdas:\n", centros_celdas)
                        print("Centros de celdas convertidos:\n",coordenadas_celdas_convertidas )

                    #**Dibujar cada celda detectada en VERDE usando las coordenadas escaladas**
                    for id_celda, x_original, y_original, w_original, h_original in coordenadas_celdas_convertidas:
                        rect = Rectangle((x_original, y_original), w_original, h_original, 
                                        edgecolor="green", facecolor="none", linewidth=0.5)
                        ax.add_patch(rect)

                    nueva_estructura_tabla = asignar_texto_a_estructura(tabla_generada, coordenadas_celdas_convertidas,textos_pdf)
                    cv2.destroyAllWindows()
                    if Config.DEBUG_PRINTS:
                        print("NUEVA ESTRUCTURA GENERADA\n",nueva_estructura_tabla)
                    RtHTML.guardar_tabla(nueva_estructura_tabla,tabla_actual,folder_path,path_tablas)
                    # if Config.DEBUG_PRINTS:
                        # input("Presione Enter para continuar")
                        # RtHTML.mostrar_html_pyqt(nueva_estructura_tabla, tabla_actual)
                    lista_tablas.append(tabla_generada)
                    crop_data.append((page_idx, (table_idx, x0-3, top-4, x1+6, bottom+4)))

        # input()

        for t in tables:
            x0, top, x1, bottom = t.bbox
            rect_w, rect_h = x1 - x0, bottom - top
            rect = Rectangle((x0, top), rect_w, rect_h, edgecolor="red", facecolor="none", linewidth=2)
            ax.add_patch(rect)

        ax.set_xlim([0, page.width])
        ax.set_ylim([page.height, 0])
        ax.set_title(f"Página {page_idx + 1} / {total_pages}")
        
        next_page(0)#> COMENTAR PARA DEBUG
        # if Config.DEBUG_PRINTS:
        # plt.close("all")
        plt.draw()
            

    def next_page(event):
        nonlocal current_page_idx
        if current_page_idx < total_pages - 1:
            current_page_idx += 1
            display_page(current_page_idx)
        else:
            if len(crop_data) > 0:
                # if Config.DEBUG_PRINTS:
                #   print(f"tabla_{page_idx + 1}_{table_idx + 1}")
                pdf_bytes_llaves_tabla_escrita = EYELDT.eliminar_elementos_area(crop_data, pdf_bytes, folder_path)
                crop_data.clear()
                print("TABLAS OBTENIDAS CON EXITO.")
            print("INICIANDO LA OBTENCION DE IMAGENES.")
            Extraer_Imagenes.extraer_imagenes(pdf_bytes_llaves_tabla_escrita,folder_path)
            pdf_bytes_llaves_tabla_imagenes = EliminarYEscribirImagenes.eliminar_imagenes_y_agregar_llaves(pdf_bytes_llaves_tabla_escrita,folder_path)
            string_tablas_remplazadas = PasarTextoPlanoAMarkdown.main(pdf_bytes_llaves_tabla_imagenes,folder_path)
            EnviarImagenesAChatGPT.enviar_Imagenes_A_GPT(folder_path+r"\imagenes_extraidas")
            RemplazarImagenesDeMarkdown.remplazar_imagenes_en_md(string_tablas_remplazadas,folder_path)
            print("PROCESO TERMINADO!")

    def prev_page(event):
        nonlocal current_page_idx
        if current_page_idx > 0:
            current_page_idx -= 1
            display_page(current_page_idx)

    ax_prev = plt.axes([0.3, 0.02, 0.15, 0.07])
    ax_next = plt.axes([0.55, 0.02, 0.15, 0.07])
    btn_prev = Button(ax_prev, 'Anterior')
    btn_next = Button(ax_next, 'Siguiente')

    btn_prev.on_clicked(prev_page)
    btn_next.on_clicked(next_page)

    display_page(current_page_idx)
    # if not Config.DEBUG_PRINTS:
    #     plt.show()
    # RtHTML.mostrar_html_todas_las_tablas(lista_tablas)
    pdf_original.close()
    pdf_sin_texto.close()

def main(pdf_bytes,folder_path):
    """
    Función principal que muestra tablas de un PDF con pdfplumber y botones.
    
    Parámetros:
        ruta_pdf (str): Ruta del PDF a procesar.
    """
    show_pdfplumber_tables_with_buttons(pdf_bytes,folder_path)  # Llama a tu función con el parámetro recibido

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
        pdf_path = "documento_verticalizado.pdf"  # Valor por defecto si no se pasa argumento}
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