"""
CortarPDFEnColumnas.py

Este módulo permite interactuar con un PDF para recortar y extraer
áreas específicas (como encabezados, columnas, pie de página, etc.) mediante
una interfaz gráfica basada en Matplotlib y Tkinter.
Se utiliza pdfplumber para leer el PDF y fitz (PyMuPDF) para generar imágenes
y realizar el recorte, junto con varios módulos propios para procesamiento adicional.
"""

import pdfplumber
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, Button, CheckButtons
import fitz  # PyMuPDF
import EliminarDatosInternosFisicos as EDIF
import ExtraerTablasSinTextoPDF
import InyectarXObjects
from PIL import Image
import numpy as np
import io
import functools
import os
import Config
import re
import unicodedata
import tkinter as tk
from tkinter import filedialog

def limpiar_nombre_carpeta(nombre):
    """
    Limpia el nombre de una carpeta reemplazando caracteres no permitidos en Windows,
    normalizando acentos y reemplazando la 'ñ'. Además, elimina espacios y puntos al final,
    y evita usar nombres reservados.

    :param nombre: Nombre original (string) a limpiar.
    :return: Nombre limpio, limitado a 255 caracteres.
    """
    # Eliminar caracteres no permitidos
    nombre = re.sub(r'[\\/:*?"<>|]', '_', nombre)
    
    # Reemplazar ñ por n y quitar tildes
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))
    nombre = nombre.replace('ñ', 'n').replace('Ñ', 'N')

    # Quitar espacios y puntos finales
    nombre = nombre.rstrip(" .")

    # Evitar nombres reservados de Windows
    nombres_reservados = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", 
                          "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", 
                          "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if nombre.upper() in nombres_reservados:
        nombre += "_safe"
    
    return nombre[:255]


# Inicializar la interfaz de Tkinter para seleccionar el PDF
root = tk.Tk()
root.withdraw()  # Oculta la ventana principal de Tkinter

# Mostrar diálogo para seleccionar archivo PDF
full_pdf_path = filedialog.askopenfilename(
    title="Selecciona un archivo PDF",
    filetypes=[("Archivos PDF", "*.pdf")]
)

# Verificar que se haya seleccionado un archivo, de lo contrario terminar
if not full_pdf_path:
    print("No se seleccionó ningún archivo. Terminando ejecución.")
    exit()

# Convertir la ruta a relativa desde el directorio del script
script_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.relpath(full_pdf_path, start=script_dir)

# Limpiar el nombre para crear la carpeta destino y asignar folder_path
nombre_limpio = limpiar_nombre_carpeta(pdf_path.split(".pdf")[0])
print(nombre_limpio)
folder_path = f"Curacion_{nombre_limpio}"

# Variables globales para almacenar estados y coordenadas de selección
paginas_omitidas = set()      # Páginas en las que se omite la colisión
checkbox_updating = False     # Bandera para evitar bucles en actualización de checkbox

# Diccionario para almacenar los recuadros o áreas definidas
rectangles = {
    'Encabezado': {
        'left': {'coords': None, 'color': 'r'},   # Primera mitad del encabezado
        'right': {'coords': None, 'color': 'r'}   # Segunda mitad del encabezado
    },
    'Pie de página': {'coords': None, 'color': 'g'},
    'Columna izquierda': {'coords': None, 'color': 'b'},
    'Columna derecha': {'coords': None, 'color': 'm'},
    'Excepción': {},  # Áreas de excepción definidas por página
    
    # Para el modo móvil
    'Encabezado_movil': {},
    'Pie_de_pagina_movil': {'coords': None, 'color': 'g'},
    'Columna_movil': {'coords': None, 'color': 'b'}
}

perimeter_issue_detected = False   # Bandera para marcar problemas con perímetros

current_page_index = 0             # Página actual mostrada
current_selector_key = 'Encabezado'  # Área a editar actualmente
crop_data = []                     # Lista para almacenar (página, coordenadas) de recortes


def pdfplumber_to_fitz(pdf):
    """
    Convierte un objeto PDF abierto con pdfplumber en un objeto BytesIO
    compatible con fitz (PyMuPDF).

    :param pdf: Objeto PDF abierto con pdfplumber.
    :return: BytesIO con el contenido del PDF.
    """
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)
    pdf_bytes.write(pdf.stream.read())
    pdf_bytes.seek(0)
    return pdf_bytes


def check_if_encabezado_half(coords):
    """
    Verifica si las coordenadas dadas corresponden a una de las mitades
    del área de encabezado ya definida en el diccionario rectangles.

    :param coords: Tuple (left, top, right, bottom) de la selección.
    :return: Tuple (es_encabezado, is_left_half, is_right_half)
             donde es_encabezado indica si es parte del encabezado y
             is_left_half, is_right_half indican cuál mitad se definió.
    """
    encabezado = rectangles.get("Encabezado", {})
    if "left" in encabezado and "right" in encabezado:
        left_coords = encabezado["left"].get("coords")
        right_coords = encabezado["right"].get("coords")
        if left_coords and right_coords:
            left, top, right, bottom = coords
            is_left_half = (left_coords[0] == left and left_coords[1] == top and
                            left_coords[2] == right and left_coords[3] == bottom)
            is_right_half = (right_coords[0] == left and right_coords[1] == top and
                             right_coords[2] == right and right_coords[3] == bottom)
            return True, is_left_half, is_right_half
    return False, False, False


def is_region_white(image, rect, threshold=250):
    """
    Determina si la región definida por rect en la imagen es completamente blanca
    (todos los píxeles mayores o iguales al umbral).

    :param image: Imagen (array NumPy).
    :param rect: Tuple (left, top, right, bottom) que define la región a analizar.
    :param threshold: Valor de umbral (por defecto 250).
    :return: True si la región es completamente blanca, False de lo contrario.
    """
    left, top, right, bottom = map(int, rect)
    region = image[top:bottom, left:right]
    return np.all(region >= threshold)


def is_pixel_in_exception(x, y, page_number, exceptions):
    """
    Verifica si un píxel (x,y) se encuentra dentro de la región de excepción
    para la página actual.

    :param x: Coordenada X del píxel.
    :param y: Coordenada Y del píxel.
    :param page_number: Número de la página.
    :param exceptions: Diccionario de excepciones por página.
    :return: True si el píxel está en excepción, False en caso contrario.
    """
    if page_number in exceptions:
        ex_left, ex_top, ex_right, ex_bottom = exceptions[page_number]
        return ex_left <= x < ex_right and ex_top <= y < ex_bottom
    return False


def check_perimeter(image, rect, page_number, exceptions):
    """
    Revisa si el perímetro de una región en la imagen contiene píxeles
    que no sean blancos, ignorando aquellos que caen dentro de áreas de excepción.
    Se excluyen los bordes internos si el rectángulo coincide con un encabezado.

    :param image: Imagen (array NumPy).
    :param rect: Tuple (left, top, right, bottom) de la región.
    :param page_number: Número de la página.
    :param exceptions: Diccionario de excepciones.
    :return: True si se encuentra al menos un píxel no blanco en el perímetro,
             False si el perímetro es completamente blanco o está en excepción.
    """
    # Omitir colisión si la página está en la lista de páginas omitidas
    if page_number in paginas_omitidas:
        if Config.DEBUG_PRINTS:
            print(f"[INFO] Omitiendo colisión en página {page_number}")
        return False

    # Ajustar coordenadas para excluir bordes
    left, top, right, bottom = [int(i) if i >= 0 else 0 for i in rect]
    left += 1; top += 1; right -= 1; bottom -= 1

    # Obtener límites de áreas especiales
    encabezado_left = rectangles.get("Encabezado", {}).get("left", {}).get("coords")
    encabezado_right = rectangles.get("Encabezado", {}).get("right", {}).get("coords")
    pie_de_pagina_movil = rectangles.get("Pie_de_pagina_movil", {}).get("coords")

    is_left_encabezado = encabezado_left is not None and rect == encabezado_left
    is_right_encabezado = encabezado_right is not None and rect == encabezado_right
    is_pie_de_pagina_movil = pie_de_pagina_movil is not None and rect == pie_de_pagina_movil

    # Extraer píxeles en cada borde de la región
    top_row = [(x, top) for x in range(left, right)]
    bottom_row = [] if is_pie_de_pagina_movil else [(x, bottom + 1) for x in range(left, right)]
    left_col = [] if is_right_encabezado or is_pie_de_pagina_movil else [(left, y) for y in range(top, bottom)]
    right_col = [] if is_left_encabezado or is_pie_de_pagina_movil else [(right, y) for y in range(top, bottom)]

    if Config.DEBUG_PRINTS:
        if is_left_encabezado:
            print(f"[DEBUG] Omitiendo borde derecho del encabezado izquierdo en {rect}")
        if is_right_encabezado:
            print(f"[DEBUG] Omitiendo borde izquierdo del encabezado derecho en {rect}")
        if is_pie_de_pagina_movil:
            print(f"[DEBUG] Omitiendo bordes izquierdo, derecho e inferior de Pie_de_pagina_movil en {rect}")

    # Revisar cada píxel en el perímetro que no esté en excepción
    for x, y in top_row + bottom_row + left_col + right_col:
        if not is_pixel_in_exception(x, y, page_number, exceptions):
            pixel_value = image[y, x]
            if isinstance(pixel_value, np.ndarray):
                pixel_value = pixel_value.mean()
            if pixel_value != 255:
                return True
    return False


def crop_and_add_to_pdf(page_number, coords, pdf_bytes):
    """
    Recorta una región de una página del PDF y, si la región no es completamente blanca
    y su perímetro es válido, la agrega a la lista global crop_data para su posterior procesamiento.

    :param page_number: Número de la página (0-indexed). Si es -1, se aplica a la última página.
    :param coords: Tuple (left, top, right, bottom) que define la región a recortar.
    :param pdf_bytes: Objeto BytesIO que contiene el PDF.
    """
    global perimeter_issue_detected
    if not coords:
        return

    # Abrir PDF en memoria con fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number]
    
    # Obtener imagen de la página en buena calidad
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Convertir a escala de grises
    img_gray = img.convert("L")
    img_np = np.array(img)  # También se usa la imagen en color para algunas validaciones

    exceptions = rectangles["Excepción"] if "Excepción" in rectangles else {}
    if Config.MOVIL:
        exceptions = rectangles["Encabezado_movil"] if "Encabezado_movil" in rectangles else {}

    # Verificar si la región es completamente blanca
    if is_region_white(img_np, coords):
        if Config.DEBUG_PRINTS:
            print(f"[INFO] Página {page_number}, Región {coords} es completamente blanca. No se agrega.")
        return

    # Revisar el perímetro de la región
    if check_perimeter(img_np, coords, page_number, exceptions):
        if Config.DEBUG_PRINTS:
            print(f"[ALERTA] Página {page_number}, Perímetro en {coords} contiene píxeles no blancos.")
        perimeter_issue_detected = True
        # Mostrar la región en cuestión para depuración
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(img_gray, cmap="gray")
        rect_disp = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                                  linewidth=2, edgecolor='red', facecolor='none')
        ax.add_patch(rect_disp)
        plt.title(f"Página {page_number}: Perímetro problemático")
        plt.show()
        return

    # Agregar la región a la lista global crop_data
    crop_data.append((page_number, coords))
    if Config.DEBUG_PRINTS:
        print(f"[INFO] Región {coords} en página {page_number+1} agregada correctamente.")


def apply_crop_with_pikepdf(pdf_bytes):
    """
    Procesa el PDF eliminando elementos internos dentro de las áreas recortadas (usando EDIF)
    y luego llama a otros módulos (InyectarXObjects, ExtraerTablasSinTextoPDF) para continuar el procesamiento.
    Además, se actualizan y eliminan widgets y eventos de la interfaz gráfica para proceder.
    
    :param pdf_bytes: Objeto BytesIO con el PDF original.
    """
    global buttons, fig, ax, ax_checkbox, ax_checkbox_omitir, axprev, bprev, axnext, bnext, axconfirm, bconfirm, toggle_selector, event_id

    # Crear la carpeta destino si no existe
    if not os.path.exists(folder_path):
        os.mkdir(folder_path)
        if Config.DEBUG_PRINTS:
            print(f"Carpeta '{folder_path}' creada con éxito.")
    else:
        if Config.DEBUG_PRINTS:
            print(f"La carpeta '{folder_path}' ya existe.")

    print("PDF GENERADO CON EXITO")
    pdf_bytes = EDIF.eliminar_elementos_area(crop_data, pdf_bytes, folder_path)
    print("INICIANDO LA OBTENICION DE TABLAS...")

    # Desconectar y eliminar eventos de botones y checkboxes
    for btn in buttons:
        btn.disconnect_events()
        btn.ax.remove()
    buttons.clear()
    checkbox.disconnect_events()
    checkbox_omitir.disconnect_events()
    bconfirm.disconnect_events()
    checkbox.ax.remove()
    checkbox_omitir.ax.remove()
    bconfirm.ax.remove()
    toggle_selector.disconnect_events()
    fig.canvas.mpl_disconnect(event_id)

    # Llamar a otros módulos para continuar procesamiento
    pdf_xobjects = InyectarXObjects.main(pdf_bytes, folder_path)
    ExtraerTablasSinTextoPDF.main(pdf_bytes, folder_path, fig, ax, bprev, bnext, pdf_xobjects, True)


def draw_rectangles(ax):
    """
    Dibuja en el eje (ax) los recuadros definidos en el diccionario rectangles.
    Se utiliza para visualizar áreas como encabezados, columnas, pie de página y excepciones.
    
    :param ax: Objeto de eje de Matplotlib.
    """
    for key, value in rectangles.items():
        # Si la clave es 'Excepción' o 'Encabezado_movil', se dibujan para la página actual
        if key == 'Excepción' or key == "Encabezado_movil":
            for page, coords in value.items():
                if page == current_page_index and coords:
                    rect = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                                         linewidth=2, edgecolor='orange', facecolor='none')
                    ax.add_patch(rect)
        elif key == 'Encabezado':
            # Dibujar ambas mitades del encabezado
            if 'left' in value and 'right' in value:
                left_coords = value['left'].get('coords')
                right_coords = value['right'].get('coords')
                fig_xmax = ax.get_xlim()[1]
                if left_coords is not None:
                    rect_left = plt.Rectangle((left_coords[0], left_coords[1]),
                                              left_coords[2] - left_coords[0],
                                              left_coords[3] - left_coords[1],
                                              linewidth=2, edgecolor='r', facecolor='none')
                    ax.add_patch(rect_left)
                if right_coords is not None:
                    rect_right = plt.Rectangle((right_coords[0], right_coords[1]),
                                               fig_xmax - right_coords[0],
                                               right_coords[3] - right_coords[1],
                                               linewidth=2, edgecolor='r', facecolor='none')
                    ax.add_patch(rect_right)
                # Dibujar línea divisoria entre ambas mitades
                if left_coords is not None and right_coords is not None:
                    ax.plot([left_coords[2], left_coords[2]], [left_coords[1], left_coords[3]],
                            color='b', linestyle='--')
        elif key in ['Columna izquierda', 'Columna derecha', 'Pie de página', 'Columna_movil']:
            coords = value['coords']
            color = value['color']
            if coords:
                rect = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                                     linewidth=2, edgecolor=color, facecolor='none')
                ax.add_patch(rect)
        elif key == 'Pie_de_pagina_movil':
            coords = value.get('coords')
            if coords:
                rect = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                                     linewidth=2, edgecolor='g', facecolor='none')
                ax.add_patch(rect)


def show_page():
    """
    Muestra la página actual del PDF en el eje de Matplotlib,
    dibuja los recuadros definidos y actualiza el estado de los checkboxes.
    """
    global current_page_index, checkbox_updating
    ax.clear()
    page = pdf.pages[current_page_index]
    im = page.to_image()
    ax.imshow(im.original)
    draw_rectangles(ax)
    checkbox_updating = True
    if checkbox_omitir.ax.figure is not None:
        if current_page_index in paginas_omitidas:
            checkbox_omitir.set_active(0)
        else:
            checkbox_omitir.set_active(0)
            checkbox_omitir.set_active(False)
    checkbox_updating = False
    fig.canvas.draw_idle()


def onselect(eclick, erelease):
    """
    Función de callback para el RectangleSelector.
    Captura las coordenadas de la selección y las asigna a la variable global
    correspondiente según el área que se esté editando.
    
    :param eclick: Evento de clic (coordenadas iniciales).
    :param erelease: Evento al soltar (coordenadas finales).
    """
    global current_selector_key
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    
    fig_xmax = ax.get_xlim()[1]
    fig_ymin = ax.get_ylim()[0]
    try:
        if current_selector_key == 'Excepción':
            rectangles['Excepción'][current_page_index] = coords
        elif current_selector_key == 'Encabezado_movil':
            rectangles['Encabezado_movil'][current_page_index] = coords
        elif current_selector_key == 'Encabezado':
            # Dividir el área en dos mitades: la izquierda se define según la selección y la derecha se extiende hasta el borde
            left_rect = (coords[0], coords[1], coords[2], coords[3])
            right_rect = (coords[2], coords[1], fig_xmax, coords[3])
            rectangles['Encabezado']['left']['coords'] = left_rect
            rectangles['Encabezado']['right']['coords'] = right_rect
            if Config.DEBUG_PRINTS:
                print(f"Encabezado dividido: Izquierda: {left_rect}, Derecha: {right_rect}")
        elif current_selector_key == 'Columna izquierda':
            left_col_rect = (coords[0], coords[1], coords[2], coords[3])
            right_col_rect = (coords[2], coords[1], fig_xmax, coords[3])
            footer_rect = (ax.get_xlim()[0], coords[3], fig_xmax, fig_ymin)
            rectangles['Columna izquierda']['coords'] = left_col_rect
            rectangles['Columna derecha']['coords'] = right_col_rect
            rectangles['Pie de página']['coords'] = footer_rect
            if Config.DEBUG_PRINTS:
                print(f"Columna izquierda: {left_col_rect}, Columna derecha: {right_col_rect}, Pie de página: {footer_rect}")
        else:
            rectangles[current_selector_key]['coords'] = coords
            if Config.DEBUG_PRINTS:
                print(f"{current_selector_key} definido en: {coords}")
    except Exception:
        print("Botón no seleccionado")
    show_page()


def on_click(event):
    """
    Callback para manejar clics individuales en la interfaz, utilizado para definir el área
    de "Pie_de_pagina_movil" cuando se hace clic sin arrastrar.
    
    :param event: Evento de clic de Matplotlib.
    """
    global current_selector_key
    if current_selector_key == 'Pie_de_pagina_movil' and event.xdata is not None and event.ydata is not None:
        # Restablecer la vista original
        ax.set_xlim(ax.dataLim.x0, ax.dataLim.x1)
        ax.set_ylim(ax.dataLim.y0, ax.dataLim.y1)
        fig.canvas.draw_idle()
        # Obtener límites de 'Columna_movil'
        columna_movil_coords = rectangles.get('Columna_movil', {}).get('coords')
        if columna_movil_coords:
            col_left, _, col_right, col_bottom = columna_movil_coords
        else:
            col_left = ax.get_xlim()[0]
            col_right = ax.get_xlim()[1]
            col_bottom = ax.get_ylim()[0]
        # Generar el rectángulo desde el clic hasta los límites
        footer_rect = (col_left, event.ydata, col_right, col_bottom)
        rectangles['Pie_de_pagina_movil']['coords'] = footer_rect
        if Config.DEBUG_PRINTS:
            print(f"Pie de página móvil: {footer_rect}")
        current_selector_key = None
        show_page()


def set_selector_key(area):
    """
    Actualiza la variable global current_selector_key para definir qué área se editará.
    
    :param area: String que identifica el área (ej. 'Encabezado', 'Columna izquierda', etc.).
    """
    global current_selector_key
    current_selector_key = area
    if Config.DEBUG_PRINTS:
        print(f"Ahora editando: {current_selector_key}")


def next_page(event):
    """
    Navega a la siguiente página del PDF.
    
    :param event: Evento del botón "Siguiente".
    """
    global current_page_index
    if current_page_index < len(pdf.pages) - 1:
        current_page_index += 1
        show_page()


def prev_page(event):
    """
    Navega a la página anterior del PDF.
    
    :param event: Evento del botón "Anterior".
    """
    global current_page_index
    if current_page_index > 0:
        current_page_index -= 1
        show_page()


def toggle_omitir_colision(event):
    """
    Alterna el estado (añadiendo o removiendo) de la omisión de colisión para la página actual.
    
    :param event: Evento del checkbox "Omitir colisión".
    """
    global checkbox_updating
    if checkbox_updating:
        return
    if current_page_index in paginas_omitidas:
        paginas_omitidas.remove(current_page_index)
    else:
        paginas_omitidas.add(current_page_index)
    if Config.DEBUG_PRINTS:
        print(f"[INFO] Páginas omitidas: {paginas_omitidas}")


def toggle_modo_movil(event):
    """
    Alterna el modo móvil modificando la variable Config.MOVIL y actualiza los botones.
    
    :param event: Evento del checkbox "Modo Móvil".
    """
    Config.MOVIL = not Config.MOVIL
    actualizar_botones()
    if Config.DEBUG_PRINTS:
        print(f"[INFO] Modo móvil: {Config.MOVIL}")


def actualizar_botones():
    """
    Actualiza la interfaz de botones en función del modo (móvil o normal). Elimina los botones existentes
    y crea nuevos botones con posiciones y colores adecuados para cada área.
    """
    global buttons, areas
    for btn in buttons:
        btn.ax.remove()
    buttons = []
    if Config.MOVIL:
        areas = ['Encabezado_movil', 'Pie_de_pagina_movil', 'Columna_movil']
        colors = ['r', 'g', 'b']
        positions = [0.3, 0.45, 0.6]
    else:
        areas = ['Encabezado', 'Pie de página', 'Columna izquierda', 'Columna derecha', 'Excepción']
        colors = ['r', 'g', 'b', 'm', 'orange']
        positions = [0.26, 0.37, 0.48, 0.59, 0.70]
    for i, area in enumerate(areas):
        axarea = plt.axes([positions[i], 0.9, 0.1, 0.05])
        btn = Button(axarea, area, color=colors[i])
        btn.on_clicked(lambda event, a=area: set_selector_key(a))
        buttons.append(btn)
    fig.canvas.draw_idle()


def confirm_and_process(pdf_bytes, event=None):
    """
    Función de confirmación que valida las áreas definidas (verifica problemas en perímetro)
    y luego procesa el PDF. Si se detectan problemas con el perímetro, no se genera el PDF final.
    
    :param pdf_bytes: BytesIO del PDF original.
    :param event: Evento opcional (del botón Confirmar).
    """
    global perimeter_issue_detected
    print("[INFO] Detectando problemas en el perímetro...")
    perimeter_issue_detected = False
    if Config.MOVIL:
        encabezado_movil_definido = (
            0 in rectangles.get('Encabezado_movil', {}) and
            rectangles['Encabezado_movil'].get(0) is not None
        )
        areas_movil_definidas = (
            encabezado_movil_definido and
            rectangles.get('Columna_movil', {}).get('coords') is not None
        )
        if areas_movil_definidas:
            process_pdf(pdf_bytes)
            if perimeter_issue_detected:
                print("[AVISO] Problemas en el perímetro detectados. No se generará el PDF.")
                crop_data.clear()
            else:
                print("[INFO] Generando PDF en modo móvil...")
                apply_crop_with_pikepdf(pdf_bytes)
        else:
            print("[INFO] Modo móvil activo. No se requieren todas las áreas.")
    else:
        encabezado_definido = ('left' in rectangles['Encabezado'] and 'right' in rectangles['Encabezado'] and
                           rectangles['Encabezado']['left'].get('coords') is not None and
                           rectangles['Encabezado']['right'].get('coords') is not None)
        if (encabezado_definido and
            all(rect.get('coords') is not None for key, rect in rectangles.items() 
                if key not in ['Encabezado', 'Excepción', 'Encabezado_movil', 'Pie_de_pagina_movil', 'Columna_movil'])):
            process_pdf(pdf_bytes)
            if perimeter_issue_detected:
                print("[AVISO] Problemas en el perímetro detectados. No se generará el PDF.")
                crop_data.clear()
            else:
                print("[INFO] Generando PDF...")
                apply_crop_with_pikepdf(pdf_bytes)
        else:
            print("Error: Áreas obligatorias no definidas.")
            crop_data.clear()


def process_pdf(pdf_bytes):
    """
    Procesa el PDF original, recortando las regiones definidas y agregándolas al nuevo documento.
    Este procesamiento varía según si el modo es móvil o normal, aplicando recortes específicos
    en cada caso.
    
    :param pdf_bytes: BytesIO del PDF original.
    """
    new_doc = fitz.open()  # Documento destino (no se usa directamente en este fragmento)
    original_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    if Config.MOVIL:
        encabezado_movil_coords = rectangles.get('Encabezado_movil', {}).get(0)
        columna_movil_coords = rectangles.get('Columna_movil', {}).get('coords')
        pie_pagina_movil_coords = rectangles.get('Pie_de_pagina_movil', {}).get('coords')
        crop_and_add_to_pdf(0, encabezado_movil_coords, pdf_bytes)
        for page_number in range(len(original_pdf)):
            if page_number in paginas_omitidas and columna_movil_coords and pie_pagina_movil_coords:
                col_left, col_top, col_right, _ = columna_movil_coords
                _, bottom_click, _, pie_bottom = pie_pagina_movil_coords
                new_coords = (col_left, col_top, col_right, bottom_click)
                crop_and_add_to_pdf(page_number, new_coords, pdf_bytes)
                if Config.DEBUG_PRINTS:
                    print(f"[INFO] Página {page_number} omitida; recorte: {new_coords}")
            elif page_number == 0 and encabezado_movil_coords and columna_movil_coords:
                col_left, col_top, col_right, col_bottom = columna_movil_coords
                enc_left, enc_top, enc_right, enc_bottom = encabezado_movil_coords
                if col_bottom > enc_bottom:
                    crop_and_add_to_pdf(page_number, (col_left, enc_bottom, col_right, col_bottom), pdf_bytes)
            else:
                if columna_movil_coords:
                    crop_and_add_to_pdf(page_number, columna_movil_coords, pdf_bytes)
            if page_number == len(original_pdf) - 1 and pie_pagina_movil_coords:
                crop_and_add_to_pdf(page_number, pie_pagina_movil_coords, pdf_bytes)
    else:
        if ('left' in rectangles['Encabezado'] and 'right' in rectangles['Encabezado'] and
            rectangles['Encabezado']['left']['coords'] is not None and
            rectangles['Encabezado']['right']['coords'] is not None):
            left_coords = rectangles['Encabezado']['left']['coords']
            right_coords = rectangles['Encabezado']['right']['coords']
            crop_and_add_to_pdf(0, left_coords, pdf_bytes)
            crop_and_add_to_pdf(0, right_coords, pdf_bytes)
        else:
            print("[ERROR] Encabezado no definido correctamente.")
        for page_number in range(len(original_pdf)):
            if page_number in rectangles['Excepción']:
                exception_coords = rectangles['Excepción'][page_number]
                for col in ['Columna izquierda', 'Columna derecha']:
                    col_coords = rectangles[col]['coords']
                    if col_coords:
                        left, top, right, bottom = col_coords
                        ex_left, ex_top, ex_right, ex_bottom = exception_coords
                        if top < ex_top:
                            crop_and_add_to_pdf(page_number, (left, top, right, ex_top), pdf_bytes)
                crop_and_add_to_pdf(page_number, exception_coords, pdf_bytes)
                for col in ['Columna izquierda', 'Columna derecha']:
                    col_coords = rectangles[col]['coords']
                    if col_coords:
                        left, top, right, bottom = col_coords
                        ex_left, ex_top, ex_right, ex_bottom = exception_coords
                        if bottom > ex_bottom:
                            crop_and_add_to_pdf(page_number, (left, ex_bottom, right, bottom), pdf_bytes)
            else:
                crop_and_add_to_pdf(page_number, rectangles['Columna izquierda']['coords'], pdf_bytes)
                crop_and_add_to_pdf(page_number, rectangles['Columna derecha']['coords'], pdf_bytes)
        crop_and_add_to_pdf(-1, rectangles['Pie de página']['coords'], pdf_bytes)
    new_doc.close()


# Configuración de la interfaz gráfica con Matplotlib
with pdfplumber.open(pdf_path) as pdf:
    pdf_bytes = pdfplumber_to_fitz(pdf)
    pdf_bytes.seek(0)

fig, ax = plt.subplots(figsize=(14, 9))

# Crear checkbox para "Modo Móvil"
ax_checkbox = plt.axes([0.1, 0.9, 0.1, 0.05])
checkbox = CheckButtons(ax_checkbox, ['Modo Móvil'], [False])
checkbox.on_clicked(toggle_modo_movil)

# Crear checkbox para "Omitir colisión"
ax_checkbox_omitir = plt.axes([0.05, 0.05, 0.15, 0.05])
checkbox_omitir = CheckButtons(ax_checkbox_omitir, ['Omitir colisión'], [False])
checkbox_omitir.on_clicked(toggle_omitir_colision)

# Botones de navegación y confirmación
axprev = plt.axes([0.2, 0.05, 0.1, 0.05])
axnext = plt.axes([0.35, 0.05, 0.1, 0.05])
axconfirm = plt.axes([0.7, 0.05, 0.15, 0.05])
bprev = Button(axprev, 'Anterior')
bprev.on_clicked(prev_page)
bnext = Button(axnext, 'Siguiente')
bnext.on_clicked(next_page)
bconfirm = Button(axconfirm, 'Confirmar')
bconfirm.on_clicked(functools.partial(confirm_and_process, pdf_bytes))

# Inicializar botones con la configuración actual
buttons = []
actualizar_botones()

# Habilitar la selección de recuadros
toggle_selector = RectangleSelector(
    ax, onselect, useblit=True,
    button=[1],
    minspanx=5, minspany=5, spancoords='pixels', interactive=True
)
event_id = fig.canvas.mpl_connect("button_press_event", on_click)
show_page()
plt.show()
