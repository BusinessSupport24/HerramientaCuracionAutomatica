"""
ExtraerTablasSinTextoPDF.py

Este módulo se encarga de extraer tablas de un PDF aplicando diversas técnicas:
1. Elimina todo el texto del PDF (incluido el contenido de XObjects) para facilitar la identificación de tablas.
2. Recorta las tablas y las guarda como imágenes de alta calidad.
3. Convierte las coordenadas de las celdas detectadas en la imagen recortada a coordenadas en el PDF original, teniendo en cuenta márgenes.
4. Asigna el contenido textual extraído a la estructura de la tabla.
5. Integra todo el proceso en una interfaz gráfica para la revisión y navegación a través de las páginas del PDF.

Utiliza varias librerías externas y módulos internos (InyectarXObjects, RenderizarTablaHTML, etc.) para completar todas las tareas.
"""

import pdfplumber               # Para extraer contenido de PDFs
import fitz                     # PyMuPDF, para manipulación de PDF y recorte de imágenes
import pikepdf                  # Para manipular el contenido del PDF en un nivel más bajo (eliminar texto)
import re                       # Expresiones regulares para búsqueda y filtrado de patrones de texto
import matplotlib.pyplot as plt # Visualización en la interfaz gráfica
from matplotlib.patches import Rectangle  # Para dibujar recuadros sobre imágenes
from matplotlib.widgets import Button       # Botones interactivos en la GUI
import numpy as np              # Cálculos y arrays
import os                       # Operaciones de sistema de archivos
from tabulate import tabulate   # Para formatear tablas en consola de forma bonita
from PIL import Image           # Manipulación de imágenes
from colorama import Style, Fore, Back  # Opcional, para resaltar salida en consola
import InyectarXObjects         # Módulo para trabajar con XObjects (imágenes/objetos incrustados)
import RenderizarTablaHTML as RtHTML # Para convertir tablas a HTML y mostrarlas en PyQt
import cv2                      # OpenCV para procesar imágenes (detección y recorte)
import EliminarYEscribirLlavesDeTablas as EYELDT  # Para eliminar elementos de área en el PDF y escribir llaves
import sys                      # Acceso a argumentos y salida del script
import io                       # Manejo de flujos de bytes
import Extraer_Imagenes         # Módulo para extracción de imágenes en PDF
import Config                   # Configuración global (DEBUG, etc.)
import EliminarYEscribirImagenes  # Para eliminar imágenes y agregar llaves en el PDF
import PasarTextoPlanoAMarkdown  # Convertir texto plano a Markdown
import EnviarImagenesAChatGPT    # Para enviar imágenes a la API de ChatGPT
import RemplazarImagenesDeMarkdown # Para reemplazar imágenes referenciadas en Markdown

from pathlib import Path         # Utilidad para manejo de rutas

def convertir_a_ruta_larga(path_str):
    """
    Convierte una ruta relativa a una ruta "larga" para Windows, que permite
    manejar rutas largas mediante el prefijo '\\\\?\\'.

    :param path_str: Ruta original como string.
    :return: Ruta en formato "largo" para Windows.
    """
    path = Path(path_str)
    abs_path = path.resolve()  # Convierte a ruta absoluta
    if not abs_path.drive:
        return str(abs_path)
    return r"\\?\{}".format(str(abs_path))


# =============================================================================
# 1. FUNCION PARA ELIMINAR TEXTO DEL PDF
# =============================================================================
def eliminar_texto_preciso(pdf_bytes, output_path):
    """
    Genera un nuevo PDF en el que se elimina todo el texto de cada página,
    incluyendo el contenido de XObjects y Form XObjects.
    
    Se utiliza pikepdf para abrir y modificar el contenido del PDF. Se aplican
    expresiones regulares para detectar comandos de texto (Tj y TJ) y se eliminan
    de los flujos de contenido.

    :param pdf_bytes: BytesIO que contiene el PDF de entrada.
    :param output_path: Ruta para guardar el PDF modificado sin texto.
    :return: BytesIO con el PDF sin texto.
    """
    pdf_bytes.seek(0)
    pdf = pikepdf.open(pdf_bytes)

    # Patrón para identificar comandos de texto Tj y TJ
    patron_texto = re.compile(r'\((.*?)\)\s*Tj|\[(.*?)\]\s*TJ')
    # Patrón para detectar comandos de posicionamiento (Td y Tm)
    patron_tm_td = re.compile(r'([-0-9.]+)\s+([-0-9.]+)\s+Td|([-0-9.]+)\s+([-0-9.]+)\s+Tm')

    def procesar_contenido(contenido):
        """
        Elimina los comandos de texto del contenido decodificado y actualiza las coordenadas
        de los textos, si fuese necesario. Devuelve el contenido sin texto codificado en latin1.
        
        :param contenido: Cadena decodificada del contenido de una página.
        :return: Contenido procesado como bytes.
        """
        current_x, current_y = 0, 0  # Variables para almacenar la posición actual
        nuevas_lineas = []  # Lista para acumular líneas procesadas

        if Config.DECODIFICAR:
            print("Contenido decodificado de la página:")
            print(contenido[:100000])  # Muestra un fragmento del contenido para depuración

        # Procesar cada línea del contenido
        for line in contenido.split("\n"):
            # Buscar comandos de transformación (Tm, Td) para actualizar la posición
            tm_td_match = patron_tm_td.search(line)
            if tm_td_match:
                # Se actualiza la posición según grupos encontrados
                x_pos = float(tm_td_match.group(1) or tm_td_match.group(3) or 0)
                y_pos = float(tm_td_match.group(2) or tm_td_match.group(4) or 0)
                current_x, current_y = x_pos, y_pos

            # Eliminar los comandos Tj y TJ que contienen el texto
            line = re.sub(patron_texto, "", line)
            nuevas_lineas.append(line)  # Agregar la línea procesada

        # Unir todas las líneas y codificar el resultado
        return "\n".join(nuevas_lineas).encode("latin1")

    def procesar_xobjects(page):
        """
        Elimina el texto contenido en los XObjects de la página.
        
        Itera por cada XObject dentro de /Resources y, si es un flujo,
        aplica la función 'procesar_contenido'.
        
        :param page: Diccionario que representa la página.
        """
        if "/Resources" in page and "/XObject" in page["/Resources"]:
            xobjects = page["/Resources"]["/XObject"]
            if Config.DEBUG_PRINTS:
                print("XObjects detectados en la página:", list(xobjects.keys()))
            # Procesar cada XObject
            for xobj_name in list(xobjects):
                xobj = xobjects[xobj_name]
                if isinstance(xobj, pikepdf.Stream):
                    try:
                        # Leer el contenido del XObject como bytes
                        contenido_xobj = xobj.read_bytes()
                        # Decodificar para procesar el contenido
                        contenido_xobj = contenido_xobj.decode("latin1", errors="ignore")
                        if Config.DEBUG_PRINTS:
                            print(f"Contenido decodificado de XObject {xobj_name}:")
                            print(contenido_xobj[:100000])
                        # Procesar y eliminar el texto del contenido del XObject
                        nuevo_contenido_xobj = procesar_contenido(contenido_xobj)
                        xobj.write(nuevo_contenido_xobj)
                    except pikepdf.PdfError:
                        if Config.DEBUG_PRINTS:
                            print(f"No se pudo leer el contenido de XObject {xobj_name}, posiblemente codificado.")

    # Procesar cada página del PDF
    for i, page in enumerate(pdf.pages):
        if Config.DEBUG_PRINTS:
            print(f"Pagina {i+1}")
        if "/Contents" not in page:
            continue  # Ignorar páginas sin contenido

        contenido_obj = page["/Contents"]
        # Si es un array, concatenar todos los flujos; de lo contrario, leer el flujo único
        if isinstance(contenido_obj, pikepdf.Array):
            contenido_completo = b"".join(p.read_bytes() for p in contenido_obj)
        else:
            contenido_completo = contenido_obj.read_bytes()

        # Decodificar el contenido para poder procesarlo
        contenido_decodificado = contenido_completo.decode("latin1", errors="ignore")
        nuevo_contenido = procesar_contenido(contenido_decodificado)

        # Reemplazar el contenido original con el contenido procesado
        if isinstance(contenido_obj, pikepdf.Array):
            for obj in contenido_obj:
                obj.write(nuevo_contenido)
        else:
            contenido_obj.write(nuevo_contenido)

        # Procesar el texto dentro de XObjects en la página
        procesar_xobjects(page)

    # Guardar el PDF modificado en la ruta larga para evitar problemas en Windows
    ruta_larga = convertir_a_ruta_larga(output_path)
    pdf.save(ruta_larga)
    # Crear un nuevo BytesIO para retornar el PDF sin texto
    pdf_bytes_sin_texto = io.BytesIO()
    pdf.save(pdf_bytes_sin_texto)
    pdf_bytes_sin_texto.seek(0)
    return pdf_bytes_sin_texto


# =============================================================================
# 2. FUNCION PARA RECORTAR TABLAS Y GUARDAR COMO IMAGEN DE ALTA CALIDAD
# =============================================================================
def crop_and_save_image(original_pdf, page_number, coords, output_path, tabla_actual, lista_tablas):
    """
    Recorta una tabla de la página indicada del PDF y la guarda como imagen PNG de alta calidad.

    Se define un rectángulo de recorte ajustado añadiendo márgenes para asegurar que se
    incluya un ligero borde alrededor de la tabla.

    :param original_pdf: Objeto PDF abierto (por ejemplo, mediante fitz).
    :param page_number: Índice de la página (0-indexed) donde se encuentra la tabla.
    :param coords: Tuple (left, top, right, bottom) que delimita la región de la tabla.
    :param output_path: Ruta para guardar la imagen resultante.
    :param tabla_actual: Identificador o ruta para nombrar la tabla actual (para mostrar en la GUI).
    :param lista_tablas: Lista en la que se acumulan las tablas procesadas para uso posterior.
    :return: HTML generado a partir de la imagen (usando RtHTML.image_to_HTML).
    """
    left, top, right, bottom = coords
    # Ajustar el rectángulo con márgenes: se restan al inicio y se suman al final
    rect = fitz.Rect(left - 3, top - 4, right + 6, bottom + 4)

    page = original_pdf[page_number]
    # Definir factores de zoom para mejorar la calidad de la imagen
    zoom_x, zoom_y = 4.0, 4.0
    mat = fitz.Matrix(zoom_x, zoom_y)

    # Obtener el pixmap (imagen) de la página recortada según el rectángulo y el zoom
    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=True)
    # Convertir el pixmap a un objeto de imagen de PIL
    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)

    # Guardar la imagen en disco con 300 dpi para asegurar alta calidad
    img.save(output_path, format="PNG", dpi=(300, 300))
    if Config.DEBUG_PRINTS:
        print(f"Imagen de tabla guardada en: {output_path}")

    # Convertir la imagen a HTML para su visualización en una interfaz (por ejemplo, PyQt)
    return RtHTML.image_to_HTML(output_path, tabla_actual)


# =============================================================================
# 3. FUNCION PRINCIPAL: OBTENER TABLAS USANDO EL PDF ORIGINAL
# =============================================================================
def convertir_coordenadas_imagen_a_pdf(coordenadas_celdas, x0, top, x1, bottom, dimensiones_imagen,
                                       left_margin=3, top_margin=4, right_margin=6, bottom_margin=4):
    """
    Convierte las coordenadas de las celdas detectadas en la imagen recortada a la escala del PDF original.

    Se toma el área original del PDF (x0, top, x1, bottom), se le agregan márgenes,
    y se calcula un factor de escala basado en las dimensiones de la imagen recortada.
    Luego se mapean las coordenadas de las celdas (en la imagen) a coordenadas en el PDF.

    :param coordenadas_celdas: Lista de tuplas (id_celda, x, y, w, h) en la escala de la imagen.
    :param x0: Coordenada X inicial del área en el PDF.
    :param top: Coordenada Y superior del área en el PDF.
    :param x1: Coordenada X final del área en el PDF.
    :param bottom: Coordenada Y inferior del área en el PDF.
    :param dimensiones_imagen: Tuple (img_left, img_top, image_width, image_height) de la imagen recortada.
    :param left_margin: Margen a restar en el lado izquierdo del área.
    :param top_margin: Margen a restar en el lado superior.
    :param right_margin: Margen a sumar en el lado derecho.
    :param bottom_margin: Margen a sumar en el lado inferior.
    :return: Tuple de:
             - coordenadas_ajustadas: Lista de tuplas (id_celda, x_pdf, y_pdf, w_pdf, h_pdf).
             - effective_pdf_rect: Tuple (pdf_left, pdf_top, pdf_right, pdf_bottom) que define el área total mapeada.
    """
    # Se asume que la imagen recortada inicia en (0, 0); se extraen las dimensiones de la imagen.
    _, _, image_width, image_height = dimensiones_imagen

    # Calcular el área en el PDF incluyendo los márgenes
    pdf_left = x0 - left_margin
    pdf_top = top - top_margin
    pdf_right = x1 + right_margin
    pdf_bottom = bottom + bottom_margin

    # Calcular anchura y altura del área efectiva en el PDF
    effective_pdf_width = pdf_right - pdf_left
    effective_pdf_height = pdf_bottom - pdf_top

    # Factores de escala de la imagen a las coordenadas del PDF
    scale_x = effective_pdf_width / image_width
    scale_y = effective_pdf_height / image_height

    if Config.DEBUG_PRINTS:
        print("Scale factors:", scale_x, scale_y)
        print("Effective PDF rect:", pdf_left, pdf_top, pdf_right, pdf_bottom)

    # Transformar cada conjunto de coordenadas de celda a la escala del PDF
    coordenadas_ajustadas = []
    for id_celda, x, y, w, h in coordenadas_celdas:
        x_pdf = pdf_left + x * scale_x
        y_pdf = pdf_top + y * scale_y
        w_pdf = w * scale_x
        h_pdf = h * scale_y
        if Config.DEBUG_PRINTS:
            print(f"Celda {id_celda} -> x: {x_pdf}, y: {y_pdf}, ancho: {w_pdf}, alto: {h_pdf}")
        coordenadas_ajustadas.append((id_celda, x_pdf, y_pdf, w_pdf, h_pdf))

    effective_pdf_rect = (pdf_left, pdf_top, pdf_right, pdf_bottom)
    return coordenadas_ajustadas, effective_pdf_rect


# =============================================================================
# 4. FUNCION ASIGNAR TEXTO: ASIGNA EL TEXTO SEGÚN LA COORDENADA MÁS CERCANA
# =============================================================================
def asignar_texto_a_estructura(tabla_estructura, coordenadas_celdas_convertidas, textos_pdf):
    """
    Asigna el contenido textual extraído de la página (almacenado en textos_pdf)
    a cada celda de la estructura de la tabla, basándose en si el centro del texto se encuentra
    dentro del bounding box de la celda.

    :param tabla_estructura: Estructura de la tabla (lista de listas, cada celda es un diccionario).
    :param coordenadas_celdas_convertidas: Lista de tuplas (id_celda, x_pdf, y_pdf, w_pdf, h_pdf).
    :param textos_pdf: Lista de tuplas (texto, x_texto, y_texto) con las posiciones extraídas.
    :return: Tabla estructurada con el contenido asignado a cada celda.
    """
    # Diccionario para acumular los textos asignados por id de celda
    contenido_por_celda = {id_celda: [] for id_celda, _, _, _, _ in coordenadas_celdas_convertidas}

    # Recorrer cada fragmento de texto y determinar a qué celda pertenece
    for texto, x_texto, y_texto in textos_pdf:
        for id_celda, x_original, y_original, w_original, h_original in coordenadas_celdas_convertidas:
            # Calcular límites del bounding box
            x_min, x_max = x_original, x_original + w_original
            y_min, y_max = y_original, y_original + h_original
            # Verificar si el centro del texto cae dentro del bounding box de la celda
            if x_min <= x_texto <= x_max and y_min <= y_texto <= y_max:
                contenido_por_celda[id_celda].append((y_texto, x_texto, texto))
                break

    # Ordenar los textos de cada celda primero por su coordenada Y, luego por X
    for id_celda in contenido_por_celda:
        contenido_por_celda[id_celda].sort(key=lambda t: (t[0], t[1]))
        # Combinar los textos en una única cadena
        contenido_por_celda[id_celda] = " ".join(txt for _, _, txt in contenido_por_celda[id_celda]).strip()

    # Asignar el contenido combinado a cada celda en la estructura
    for fila in tabla_estructura:
        for celda in fila:
            if celda["rowspan"] > 0 and celda["colspan"] > 0:
                if "id_celda" not in celda:
                    celda["id_celda"] = None  # Para evitar errores si falta el identificador
                id_celda = celda["id_celda"]
                celda["contenido"] = contenido_por_celda.get(id_celda, "")

    return tabla_estructura


def asignar_texto_a_estructura_new(tabla_estructura, coordenadas_celdas_convertidas, palabras_pdf):
    """
    Variante de asignar texto que une palabras extraídas (con sus posiciones)
    en líneas de lectura ordenadas (de arriba a abajo y de izquierda a derecha).

    Se agrupan palabras que estén muy cercanas (considerando una tolerancia) para formar líneas,
    y luego se concatenan para formar el contenido de cada celda.

    :param tabla_estructura: Estructura de la tabla en formato lista de listas.
    :param coordenadas_celdas_convertidas: Lista de tuplas (id_celda, x_pdf, y_pdf, w_pdf, h_pdf).
    :param palabras_pdf: Lista de diccionarios, cada uno con claves 'text', 'x0', 'x1', 'top', 'bottom'.
    :return: Tabla actualizada con el contenido textual asignado a cada celda.
    """
    # Inicializar el diccionario para acumular palabras por celda
    contenido_por_celda = {id_celda: [] for id_celda, _, _, _, _ in coordenadas_celdas_convertidas}

    # Asignar cada palabra a la celda cuyo bounding box la contenga, usando el centro de la palabra
    for w in palabras_pdf:
        x_center = (w['x0'] + w['x1']) / 2
        y_center = (w['top'] + w['bottom']) / 2
        texto = w['text']
        for id_celda, x_original, y_original, w_original, h_original in coordenadas_celdas_convertidas:
            x_min, x_max = x_original, x_original + w_original
            y_min, y_max = y_original, y_original + h_original
            if x_min <= x_center <= x_max and y_min <= y_center <= y_max:
                contenido_por_celda[id_celda].append((y_center, x_center, texto))
                break

    # Agrupar palabras en líneas, considerando una tolerancia vertical
    for id_celda in contenido_por_celda:
        contenido_por_celda[id_celda].sort(key=lambda t: (t[0], t[1]))
        tolerancia = 5  # Tolerancia en píxeles para agrupar palabras en la misma línea
        grupos = []
        grupo_actual = []
        for (y, x, palabra) in contenido_por_celda[id_celda]:
            if not grupo_actual:
                grupo_actual.append((y, x, palabra))
            else:
                if abs(y - grupo_actual[-1][0]) <= tolerancia:
                    grupo_actual.append((y, x, palabra))
                else:
                    grupos.append(grupo_actual)
                    grupo_actual = [(y, x, palabra)]
        if grupo_actual:
            grupos.append(grupo_actual)
        # Concatenar cada grupo en una línea separada por saltos de línea
        texto_concatenado = "\n".join(" ".join(p for _, _, p in grupo) for grupo in grupos).strip()
        contenido_por_celda[id_celda] = {
            "texto": texto_concatenado,
            "detalles": contenido_por_celda[id_celda]
        }

    # Asignar el contenido generado a cada celda en la estructura de la tabla
    for fila in tabla_estructura:
        for celda in fila:
            if celda["rowspan"] > 0 and celda["colspan"] > 0:
                if "id_celda" not in celda:
                    celda["id_celda"] = None
                id_celda = celda["id_celda"]
                celda["contenido"] = contenido_por_celda.get(id_celda, {"texto": "", "detalles": []})["texto"]

    return tabla_estructura


# =============================================================================
# 4. FUNCION PRINCIPAL: OBTENER TABLAS USANDO EL PDF ORIGINAL
# =============================================================================
def show_pdfplumber_tables_with_buttons(pdf_bytes, folder_path, fig, ax, bprev, bnext, pdf_xobjects, come_from):
    """
    Función principal para visualizar y procesar las tablas detectadas en un PDF.

    Se realiza lo siguiente:
    - Se prepara un PDF "sin texto" para realizar los recortes.
    - Se muestran las páginas en una interfaz gráfica con Matplotlib.
    - Se detectan las tablas en cada página usando pdfplumber y también se consideran los XObjects.
    - Se extrae la estructura de cada tabla, se asigna el texto a cada celda y se dibujan recuadros.
    - Se permite la navegación entre páginas mediante botones.
    
    :param pdf_bytes: BytesIO que contiene el PDF original.
    :param folder_path: Carpeta donde se guardarán archivos temporales y resultados.
    :param fig: Objeto figura de Matplotlib.
    :param ax: Objeto eje de Matplotlib.
    :param bprev: Botón para navegar a la página anterior.
    :param bnext: Botón para navegar a la página siguiente.
    :param pdf_xobjects: PDF modificado con XObjects (resultado del módulo InyectarXObjects).
    :param come_from: Flag para controlar comportamientos particulares (p.ej., modo depuración).
    """
    # Preparar el PDF con XObjects
    pdf_bytes_xobjects = io.BytesIO()
    pdf_xobjects.save(pdf_bytes_xobjects)
    pdf_xobjects.close()
    pdf_bytes_xobjects.seek(0)
    pdf_copy_xobjects = io.BytesIO(pdf_bytes_xobjects.getvalue())
    pdf_modificado_xobjects = pdfplumber.open(pdf_copy_xobjects)

    # Preparar un PDF sin texto para recortes (esto facilita la detección de tablas)
    pdf_bytes.seek(0)
    pdf_copy = io.BytesIO(pdf_bytes.getvalue())
    pdf_sin_texto_path = os.path.join(folder_path, "documento_temporal_sin_texto.pdf")
    pdf_bytes_sin_texto = eliminar_texto_preciso(pdf_bytes, pdf_sin_texto_path)

    # Abrir el PDF original y el PDF sin texto
    pdf_original = pdfplumber.open(pdf_copy)
    pdf_sin_texto = fitz.open(stream=pdf_bytes_sin_texto, filetype="pdf")
    total_pages = len(pdf_original.pages)
    
    if Config.DEBUG_PRINTS:
        print(total_pages)
    current_page_idx = 0

    output_folder = os.path.join(folder_path, "tablas_recortadas")
    ax.clear()
    plt.subplots_adjust(bottom=0.15)

    lista_tablas = []   # Almacena las tablas generadas para uso posterior
    crop_data = []      # Almacena datos de recorte de cada tabla

    def display_page(page_idx):
        """
        Muestra la página del PDF indicada, detecta las tablas presentes,
        dibuja recuadros alrededor de ellas y procesa los contenidos.

        :param page_idx: Índice de la página a mostrar.
        """
        ax.clear()
        ax.axis("off")
        page = pdf_original.pages[page_idx]
        # Usar XObjects si están disponibles para mejorar detección
        page_xobjects = pdf_modificado_xobjects.pages[page_idx] if pdf_modificado_xobjects else pdf_original.pages[page_idx]
        
        # Convertir la página en una imagen para visualizarla
        page_image = page.to_image(resolution=72)
        pil_img = page_image.original
        img_array = np.array(pil_img)
        ax.imshow(img_array)

        # Detectar tablas en la página mediante ambos métodos
        tables = page.find_tables()
        xtables = page_xobjects.find_tables()
        tables = tables + xtables
        
        if Config.DEBUG_PRINTS:
            print(f"\n=== Página {page_idx + 1} ===")
            print(tables)
            plt.waitforbuttonpress()  # Pausa para revisión de depuración

        def is_inside(inner_bbox, outer_bbox):
            """
            Verifica si el recuadro (inner_bbox) está completamente dentro de outer_bbox.
            """
            x0_inner, top_inner, x1_inner, bottom_inner = inner_bbox
            x0_outer, top_outer, x1_outer, bottom_outer = outer_bbox
            return (x0_outer <= x0_inner <= x1_inner <= x1_outer) and (top_outer <= top_inner <= bottom_inner <= bottom_outer)

        contained_tables = set()
        # Comparar todas las tablas detectadas para eliminar aquellas que están contenidas en otras
        for i, table_a in enumerate(tables):
            bbox_a = table_a.bbox
            for j, table_b in enumerate(tables):
                if i != j:
                    bbox_b = table_b.bbox
                    if is_inside(bbox_a, bbox_b):
                        contained_tables.add(i)
        filtered_tables = [table for idx, table in enumerate(tables) if idx not in contained_tables]
        tables = filtered_tables

        if not tables:
            if Config.DEBUG_PRINTS:
                print("  No se han encontrado tablas en esta página.")
        elif not Config.MOVIL and page_idx < 2:
            if Config.DEBUG_PRINTS:
                print(f" Página {page_idx}, se ignora")
        else:
            path_tablas = os.path.join(folder_path, "tablas_html")
            if not os.path.exists(path_tablas):
                os.mkdir(path_tablas)
                if Config.DEBUG_PRINTS:
                    print(f"Carpeta '{path_tablas}' creada con éxito.")
            else:
                if Config.DEBUG_PRINTS:
                    print(f"La carpeta '{path_tablas}' ya existe.")
            # Procesar cada tabla encontrada
            for table_idx, table in enumerate(tables):
                x0, top, x1, bottom = table.bbox
                if Config.DEBUG_PRINTS:
                    print(f"  - Tabla {table_idx + 1} | BBox = ({x0:.2f}, {top:.2f}) - ({x1:.2f}, {bottom:.2f})")
                
                # Extraer la estructura de la tabla (encabezados y filas)
                data = table.extract()
                if not data:
                    if Config.DEBUG_PRINTS:
                        print("    (Tabla vacía o sin contenido extraído)")
                else:
                    headers = data[0]
                    rows = data[1:] if len(data) > 1 else []
                    tabla_formateada = tabulate(rows, headers=headers, tablefmt="fancy_grid")
                    if Config.DEBUG_PRINTS:
                        print("    Contenido de la tabla:\n", tabla_formateada)
                    # Extraer palabras presentes en el área de la tabla
                    words = page.extract_words(x_tolerance=3, y_tolerance=1)
                    words_in_table = [
                        w for w in words
                        if w['x0'] >= x0 and w['top'] >= top and w['x1'] <= x1 and w['bottom'] <= bottom
                    ]

                # Procesar encabezados y celdas para asignar el texto extraído
                textos_pdf = []
                procesadas = {}
                for col_idx, header_text in enumerate(headers):
                    if col_idx < len(table.rows[0].cells):
                        header_cell = table.rows[0].cells[col_idx]
                        if header_cell is None:
                            continue
                        cell_x0, cell_top, cell_x1, cell_bottom = header_cell
                        centro_x = (cell_x0 + cell_x1) / 2
                        centro_y = (cell_top + cell_bottom) / 2
                        if Config.DEBUG_PRINTS:
                            print(f"    - Encabezado ({col_idx}) | BBox: ({cell_x0:.2f}, {cell_top:.2f}) - ({cell_x1:.2f}, {cell_bottom:.2f})")
                            print(f"      - Contenido: {header_text}")
                        if (0, col_idx) in procesadas:
                            continue
                        textos_pdf.append((header_text, centro_x, centro_y))
                        procesadas[(0, col_idx)] = True

                for row_idx, row_data in enumerate(data[1:]):  # Saltar la fila de encabezados
                    for col_idx, texto_celda in enumerate(row_data):
                        try:
                            cell = table.rows[row_idx + 1].cells[col_idx]
                        except IndexError:
                            continue
                        if cell is None:
                            continue
                        cell_x0, cell_top, cell_x1, cell_bottom = cell
                        if texto_celda is None:
                            texto_celda = ""
                        if Config.DEBUG_PRINTS:
                            print(f"      Celda ({row_idx+1}, {col_idx}) | BBox: ({cell_x0:.2f}, {cell_top:.2f}) - ({cell_x1:.2f}, {cell_bottom:.2f})")
                            print(f"        - Contenido: {texto_celda}")
                        if texto_celda.strip():
                            centro_x = (cell_x0 + cell_x1) / 2
                            centro_y = (cell_top + cell_bottom) / 2
                            textos_pdf.append((texto_celda, centro_x, centro_y))

                # Definir la ruta temporal para guardar la imagen de la tabla
                output_img_path = os.path.join(folder_path, "imagenTemporal.png")
                tabla_actual = os.path.join(output_folder, f"tabla_{page_idx + 1}_{table_idx + 1}.png")
                # Recortar la tabla y obtener datos: imagen generada, coordenadas, dimensiones, etc.
                (tabla_generada, coordenadas_celdas, centros_celdas, image_width,
                 image_height, dimensiones_tabla) = crop_and_save_image(pdf_sin_texto, page_idx, (x0, top, x1, bottom), output_img_path, tabla_actual, lista_tablas)
                if Config.DEBUG_PRINTS:
                    RtHTML.mostrar_html_pyqt(tabla_generada, tabla_actual)
                # Si se detectaron celdas, convertir sus coordenadas a la escala del PDF
                if len(coordenadas_celdas) > 0:
                    dimensiones_imagen = (0, 0, image_width, image_height)
                    (coordenadas_celdas_convertidas, effective_pdf_rect) = convertir_coordenadas_imagen_a_pdf(
                        coordenadas_celdas, x0, top, x1, bottom, dimensiones_imagen,
                        left_margin=3, top_margin=5, right_margin=4, bottom_margin=4
                    )
                    # Mostrar el rectángulo efectivo (en azul) sobre la imagen para depuración
                    if Config.DEBUG_PRINTS:
                        print("effective_pdf_rect", effective_pdf_rect)
                    pdf_x0, pdf_y0, pdf_x1, pdf_y1 = effective_pdf_rect
                    width_effective_pdf = pdf_x1 - pdf_x0
                    height_effective_pdf = pdf_y1 - pdf_y0
                    rect_effective = Rectangle((pdf_x0, pdf_y0), width_effective_pdf, height_effective_pdf,
                                               edgecolor="blue", facecolor="none", linewidth=1.5)
                    ax.add_patch(rect_effective)
                    if Config.DEBUG_PRINTS:
                        print("Centros de celdas:", centros_celdas)
                        print("Centros convertidos:", coordenadas_celdas_convertidas)
                    # Dibujar los recuadros de cada celda en verde
                    for id_celda, x_original, y_original, w_original, h_original in coordenadas_celdas_convertidas:
                        rect = Rectangle((x_original, y_original), w_original, h_original,
                                         edgecolor="green", facecolor="none", linewidth=0.5)
                        ax.add_patch(rect)
                    # Asignar el texto a cada celda usando la variante nueva y guardar la estructura en HTML
                    nueva_estructura_tabla = asignar_texto_a_estructura_new(tabla_generada, coordenadas_celdas_convertidas, words_in_table)
                    if Config.DEBUG_PRINTS:
                        print("Nueva estructura generada:", nueva_estructura_tabla)
                    RtHTML.guardar_tabla(nueva_estructura_tabla, tabla_actual, folder_path, path_tablas)
                    if Config.DEBUG_PRINTS:
                        RtHTML.mostrar_html_pyqt(nueva_estructura_tabla, tabla_actual)
                    lista_tablas.append(tabla_generada)
                    # Agregar datos de recorte a crop_data para procesamiento posterior
                    crop_data.append((page_idx, (table_idx, x0 - 3, top - 4, x1 + 6, bottom + 4)))

        # Dibujar un recuadro rojo para cada tabla detectada (para visualización)
        for t in tables:
            x0, top, x1, bottom = t.bbox
            rect_w, rect_h = x1 - x0, bottom - top
            rect = Rectangle((x0, top), rect_w, rect_h, edgecolor="red", facecolor="none", linewidth=2)
            ax.add_patch(rect)

        # Configurar límites del eje para que coincidan con las dimensiones de la página
        ax.set_xlim([0, page.width])
        ax.set_ylim([page.height, 0])
        ax.set_title(f"Página {page_idx + 1} / {total_pages}")
        # Si no está en modo depuración, navegar automáticamente (opcional)
        if not Config.DEBUG_PRINTS:
            next_page(0)
        if Config.DEBUG_PRINTS and page_idx == 0 and not come_from:
            plt.show()
        fig.canvas.draw()

    def next_page(event):
        """
        Callback para pasar a la siguiente página del PDF.
        """
        nonlocal current_page_idx
        if current_page_idx < total_pages - 1:
            current_page_idx += 1
            display_page(current_page_idx)
        else:
            # Cuando se llega a la última página, se procesa el PDF final
            pdf_bytes_llaves_tabla_escrita = pdf_bytes
            if len(crop_data) > 0:
                pdf_bytes_llaves_tabla_escrita = EYELDT.eliminar_elementos_area(crop_data, pdf_bytes, folder_path)
                crop_data.clear()
                print("TABLAS OBTENIDAS CON ÉXITO.")
            print("INICIANDO LA OBTENCIÓN DE IMÁGENES.")
            Extraer_Imagenes.extraer_imagenes(pdf_bytes_llaves_tabla_escrita, folder_path)
            pdf_bytes_llaves_tabla_imagenes = EliminarYEscribirImagenes.eliminar_imagenes_y_agregar_llaves(pdf_bytes_llaves_tabla_escrita, folder_path)
            string_tablas_remplazadas = PasarTextoPlanoAMarkdown.main(pdf_bytes_llaves_tabla_imagenes, folder_path)
            EnviarImagenesAChatGPT.enviar_Imagenes_A_GPT(os.path.join(folder_path, "imagenes_extraidas"))
            RemplazarImagenesDeMarkdown.remplazar_imagenes_en_md(string_tablas_remplazadas, folder_path)
            print("PROCESO TERMINADO!")
            os.startfile(os.path.abspath(folder_path))
            exit()

    def prev_page(event):
        """
        Callback para retroceder a la página anterior.
        """
        nonlocal current_page_idx
        if current_page_idx > 0:
            current_page_idx -= 1
            display_page(current_page_idx)

    # Asignar callbacks a los botones de navegación
    bprev.on_clicked(prev_page)
    bnext.on_clicked(next_page)

    # Mostrar la primera página
    display_page(current_page_idx)
    fig.canvas.draw()


# =============================================================================
# Funciones de integración y conversión de PDF
# =============================================================================
def main(pdf_bytes, folder_path, fig, ax, bprev, bnext, pdf_xobjects, come_from=False):
    """
    Función principal que inicia el proceso de extracción de tablas a partir de un PDF.
    
    Se encarga de llamar a la función que muestra las tablas con la interfaz gráfica.
    
    :param pdf_bytes: BytesIO del PDF a procesar.
    :param folder_path: Ruta de la carpeta donde se guardarán resultados.
    :param fig: Objeto figura de Matplotlib.
    :param ax: Objeto eje de Matplotlib.
    :param bprev: Botón para ir a la página anterior.
    :param bnext: Botón para ir a la página siguiente.
    :param pdf_xobjects: PDF con XObjects inyectados.
    :param come_from: Flag opcional para ajustar el comportamiento (por ejemplo, en depuración).
    """
    show_pdfplumber_tables_with_buttons(pdf_bytes, folder_path, fig, ax, bprev, bnext, pdf_xobjects, come_from)


def pdfplumber_to_fitz(pdf):
    """
    Convierte un objeto PDF de pdfplumber a un objeto BytesIO para poder trabajar con PyMuPDF.
    
    :param pdf: Objeto PDF abierto con pdfplumber.
    :return: BytesIO con el contenido del PDF.
    """
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)  # Asegurar que se lee desde el inicio
    pdf_bytes.write(pdf.stream.read())
    pdf_bytes.seek(0)
    return pdf_bytes


# =============================================================================
# Ejecución principal si se invoca el script directamente
# =============================================================================
if __name__ == "__main__":
    """
    Punto de entrada principal del script.

    Este bloque se ejecuta solo si el archivo es ejecutado directamente. 
    Realiza las siguientes tareas:
    1. Verifica si se ha pasado un archivo PDF como argumento por línea de comandos.
    2. Si no se proporciona un argumento, utiliza un archivo PDF por defecto.
    3. Crea una carpeta de salida basada en el nombre del archivo PDF si no existe.
    4. Abre el PDF usando pdfplumber y lo convierte a un objeto BytesIO compatible con PyMuPDF.
    5. Configura la interfaz gráfica con botones "Anterior" y "Siguiente".
    6. Llama al método InyectarXObjects.main para procesar el PDF.
    7. Ejecuta la función `main` con todos los objetos inicializados.
    """

    if len(sys.argv) > 1:
        # Si se proporciona un argumento desde la línea de comandos, se utiliza como contenido PDF
        pdf_bytes = sys.argv[1]
    else:
        # Nombre del archivo PDF por defecto
        pdf_path = "documento_verticalizado copy.pdf"

        # Carpeta de salida basada en el nombre del archivo PDF (sin extensión)
        folder_path = "Curacion_" + pdf_path.split(".pdf")[0]

        # Verifica si la carpeta ya existe, si no, la crea
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
            if Config.DEBUG_PRINTS:
                print(f"Carpeta '{folder_path}' creada con éxito.")
        else:
            if Config.DEBUG_PRINTS:
                print(f"La carpeta '{folder_path}' ya existe.")

        # Abre el PDF usando pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            # Convierte el objeto pdfplumber a BytesIO compatible con PyMuPDF
            pdf_bytes = pdfplumber_to_fitz(pdf)
            # Coloca el cursor al inicio del stream de bytes
            pdf_bytes.seek(0)

        # Crea una figura y un eje principal para mostrar contenido en matplotlib
        fig, ax = plt.subplots(figsize=(12, 7), dpi=125)

        # Crea dos ejes adicionales que serán usados para los botones de navegación
        ax_prev = plt.axes([0.3, 0.02, 0.15, 0.07])  # Posición y tamaño del botón "Anterior"
        ax_next = plt.axes([0.55, 0.02, 0.15, 0.07])  # Posición y tamaño del botón "Siguiente"

        # Crea los botones usando los ejes anteriores
        bprev = Button(ax_prev, 'Anterior')
        bnext = Button(ax_next, 'Siguiente')

        # Procesa el PDF usando una función externa para inyectar XObjects, guardando el resultado
        pdf_xobjects = InyectarXObjects.main(pdf_bytes, folder_path)

    # Llama a la función principal pasando todos los objetos necesarios
    main(pdf_bytes, folder_path, fig, ax, bprev, bnext, pdf_xobjects)

