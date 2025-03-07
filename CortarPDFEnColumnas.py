import pdfplumber
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, Button
import fitz  # PyMuPDF
import EliminarDatosInternosFisicos as EDIF
import ExtraerTablasSinTextoPDF
from PIL import Image
import numpy as np
import io
import functools
import os
import Config
import re
import unicodedata

def limpiar_nombre_carpeta(nombre):
    # Eliminar caracteres no permitidos en Windows
    nombre = re.sub(r'[\\/:*?"<>|]', '_', nombre)
    
    # Reemplazar ñ por n y quitar tildes
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))  # Quitar tildes
    nombre = nombre.replace('ñ', 'n').replace('Ñ', 'N')  # Reemplazar ñ

    # Quitar espacios y puntos al final
    nombre = nombre.rstrip(" .")

    # Evitar nombres reservados de Windows
    nombres_reservados = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", 
                          "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", 
                          "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    
    if nombre.upper() in nombres_reservados:
        nombre += "_safe"  # Agregar sufijo para evitar conflictos
    
    # Limitar la longitud a 255 caracteres
    return nombre[:255]


# Ruta del PDF
pdf_path = "PCAM 1023 Campaña HBO_MAX_NTC_TC_V62_0325.pdf"  # Reemplaza esto con la ruta a tu archivo PDF
nombre_limpio = limpiar_nombre_carpeta(pdf_path.split(".pdf")[0])
print(nombre_limpio)
folder_path = f"Curacion_{nombre_limpio}"

# Variables para almacenar las coordenadas
rectangles = {
    'Encabezado': {
        'left': {'coords': None, 'color': 'r'},   # Primera mitad
        'right': {'coords': None, 'color': 'r'}   # Segunda mitad
    },
    'Pie de página': {'coords': None, 'color': 'g'},
    'Columna izquierda': {'coords': None, 'color': 'b'},
    'Columna derecha': {'coords': None, 'color': 'm'},
    'Excepción': {}  # Diccionario para excepciones por página
}

perimeter_issue_detected = False

# Variables para la navegación entre páginas
current_page_index = 0
current_selector_key = 'Encabezado'
crop_data = []  # Lista para guardar (pagina, coords)

def pdfplumber_to_fitz(pdf):
    pdf_bytes = io.BytesIO()
    
    pdf.stream.seek(0)  # Asegurar que estamos al inicio del archivo
    pdf_bytes.write(pdf.stream.read())  # Guardar el contenido en memoria
    pdf_bytes.seek(0)  # Volver al inicio para que fitz lo lea correctamente

    return pdf_bytes  # Retornar el PDF en memoria

def check_if_encabezado_half(coords):
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

    return False, False, False  # No es encabezado

# Función para recortar y agregar la región de una página al nuevo PDF
def is_region_white(image, rect, threshold=250):
    """
    Verifica si una región específica de la imagen es completamente blanca dentro de un umbral.
    
    :param image: Imagen completa en formato NumPy.
    :param rect: Coordenadas (left, top, right, bottom) de la región a analizar.
    :param threshold: Valor de umbral para considerar un píxel como blanco (0-255).
    :return: True si toda la región es blanca, False en caso contrario.
    """
    left, top, right, bottom = map(int, rect)  # Asegurar que sean enteros
    region = image[top:bottom, left:right]  # Extraer la región de la imagen
    return np.all(region >= threshold)  # Verificar si todos los píxeles son blancos

def is_pixel_in_exception(x, y, page_number, exceptions):
    """
    Verifica si un píxel (x, y) está dentro de la región de excepción de la página.

    :param x: Coordenada X del píxel.
    :param y: Coordenada Y del píxel.
    :param page_number: Número de la página actual.
    :param exceptions: Diccionario de excepciones por página.
    :return: True si el píxel está dentro de una excepción, False en caso contrario.
    """
    if page_number in exceptions:
        ex_left, ex_top, ex_right, ex_bottom = exceptions[page_number]
        return ex_left <= x < ex_right and ex_top <= y < ex_bottom  # Corrección en los límites
    return False

def check_perimeter(image, rect, page_number, exceptions):
    """
    Verifica si el perímetro de una región en la imagen pasa por un píxel que no es blanco,
    ignorando píxeles dentro de la excepción y excluyendo los bordes internos del encabezado 
    si coincide exactamente con sus coordenadas.
    """
    left, top, right, bottom = [int(i) if i >= 0 else 0 for i in rect]
    left += 1
    top += 1
    right -= 1
    bottom -= 1

    # Obtener coordenadas exactas del encabezado
    encabezado_left = rectangles.get("Encabezado", {}).get("left", {}).get("coords")
    encabezado_right = rectangles.get("Encabezado", {}).get("right", {}).get("coords")

    # Determinar si el rectángulo actual coincide con una mitad del encabezado
    is_left_encabezado = encabezado_left is not None and rect == encabezado_left
    is_right_encabezado = encabezado_right is not None and rect == encabezado_right

    # Extraer los bordes de la región
    top_row = [(x, top) for x in range(left, right)]
    bottom_row = [(x, bottom + 1) for x in range(left, right)]

    # Si es el encabezado izquierdo, no verificar el borde derecho
    left_col = [(left, y) for y in range(top, bottom)] if not is_right_encabezado else []

    # Si es el encabezado derecho, no verificar el borde izquierdo
    right_col = [(right, y) for y in range(top, bottom)] if not is_left_encabezado else []

    # Debugging: Ver qué bordes están siendo excluidos
    if Config.DEBUG_PRINTS:
        if is_left_encabezado:
            print(f"[DEBUG] Omitiendo borde derecho del encabezado izquierdo en {rect}")
        if is_right_encabezado:
            print(f"[DEBUG] Omitiendo borde izquierdo del encabezado derecho en {rect}")

    # Verificar cada píxel en el perímetro
    for x, y in top_row + bottom_row + left_col + right_col:
        if not is_pixel_in_exception(x, y, page_number, exceptions):  # Ignorar si está en excepción
            pixel_value = image[y, x]  # Obtener el valor del píxel

            # Si la imagen tiene múltiples canales (ej. RGB), tomar solo el primer canal (escala de grises)
            if isinstance(pixel_value, np.ndarray):
                pixel_value = pixel_value.mean()  # Convertir a un valor único tomando el promedio

            if pixel_value != 255:  # Verificar si el píxel no es blanco
                return True  # Se encontró un píxel no blanco en el perímetro

    return False  # Todo el perímetro es blanco (o está en excepción)


def crop_and_add_to_pdf(page_number, coords,pdf_bytes):
    global perimeter_issue_detected  # Permite modificar la variable global
    """
    Recorta una región de una página del PDF y la agrega a `crop_data` si no es completamente blanca.
    
    :param page_number: Número de la página en el PDF.
    :param coords: Coordenadas (left, top, right, bottom) de la región a recortar.
    """
    if not coords:
        return

    # Cargar el PDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number]
    
    # Obtener la imagen de la página en la mejor calidad posible
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)  # Aumentar la resolución (2x)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Convertir la imagen en un array NumPy en escala de grises
    img_gray = img.convert("L")  # Convertir a escala de grises
    img_np = np.array(img_gray)

    # Convertir la imagen en un array NumPy
    img_np = np.array(img)

    exceptions = rectangles["Excepción"] if "Excepción" in rectangles else {}

    # Verificar si la región recortada es completamente blanca
    if is_region_white(img_np, coords):
        if Config.DEBUG_PRINTS:
            print(f"[INFO] Página {page_number}, Región {coords} es completamente blanca. No se agrega.")
        return

    # Verificar si el perímetro de la región contiene algún píxel no blanco fuera de la excepción
    if check_perimeter(img_np, coords, page_number, exceptions):
        if Config.DEBUG_PRINTS:
            print(f"[ALERTA] Página {page_number}, Perímetro en {coords} pasa por un pixel que no es blanco (fuera de excepción).")
        perimeter_issue_detected = True  # Se marca que hubo un problema con el perímetro

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(img_gray, cmap="gray")
        rect = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                             linewidth=2, edgecolor='red', facecolor='none')
        ax.add_patch(rect)
        plt.title(f"Página {page_number}: Perímetro no completamente blanco (fuera de excepción)")
        plt.show()
        return  # No agregamos la región a crop_data si hay problema con el perímetro


    # Agregar la región a `crop_data`
    crop_data.append((page_number, coords))
    if Config.DEBUG_PRINTS:
        print(f"[INFO] Región {coords} en página {page_number+1} agregada correctamente.")

 

def apply_crop_with_pikepdf(pdf_bytes):

    if not os.path.exists(folder_path):  # Verifica si la carpeta no existe
        os.mkdir(folder_path)  # Crea la carpeta
        if Config.DEBUG_PRINTS:
            print(f"Carpeta '{folder_path}' creada con éxito.")
    else:
        if Config.DEBUG_PRINTS:
            print(f"La carpeta '{folder_path}' ya existe.")

    print("PDF GENERADO CON EXITO")
    pdf_bytes = EDIF.eliminar_elementos_area(crop_data, pdf_bytes,folder_path)
        
    if Config.DEBUG_PRINTS:
        # Abrir el PDF en memoria con pdfplumber
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if Config.DEBUG_PRINTS:
                    print(text)  # Aquí puedes procesar el texto sin guardar el PDF en disco
                # plt.waitforbuttonpress()

        # plt.close()
    print("INICIANDO LA OBTENICION DE TABLAS...")
    ExtraerTablasSinTextoPDF.main(pdf_bytes,folder_path)  # Llamar a la función `main()`

    
    # return pdf_bytes  # Si necesitas usarlo en otro lugar, devuélvelo
    
# Función para dibujar los recuadros en la página
def draw_rectangles(ax):
    for key, value in rectangles.items():
        if key == 'Excepción':
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

                # Obtener el límite derecho de la figura
                fig_xmax = ax.get_xlim()[1]

                if left_coords is not None:
                    rect_left = plt.Rectangle((left_coords[0], left_coords[1]),
                                            left_coords[2] - left_coords[0],
                                            left_coords[3] - left_coords[1],
                                            linewidth=2, edgecolor='r', facecolor='none')
                    ax.add_patch(rect_left)

                if right_coords is not None:
                    rect_right = plt.Rectangle((right_coords[0], right_coords[1]),
                                            fig_xmax - right_coords[0],  # Extender hasta el borde de la figura
                                            right_coords[3] - right_coords[1],
                                            linewidth=2, edgecolor='r', facecolor='none')
                    ax.add_patch(rect_right)

                # Dibujar línea divisoria entre los dos encabezados si ambas mitades están definidas
                if left_coords is not None and right_coords is not None:
                    ax.plot([left_coords[2], left_coords[2]], [left_coords[1], left_coords[3]], color='b', linestyle='--')
        
        elif key in ['Columna izquierda', 'Columna derecha', 'Pie de página']:
            coords = value['coords']
            color = value['color']
            if coords:
                rect = plt.Rectangle((coords[0], coords[1]), coords[2] - coords[0], coords[3] - coords[1],
                                     linewidth=2, edgecolor=color, facecolor='none')
                ax.add_patch(rect)


# Función para mostrar la página actual
def show_page():
    global current_page_index
    ax.clear()
    page = pdf.pages[current_page_index]
    im = page.to_image()
    ax.imshow(im.original)
    draw_rectangles(ax)
    fig.canvas.draw()

# Función para manejar la selección de recuadros
def onselect(eclick, erelease):
    global current_selector_key
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    
    fig_xmax = ax.get_xlim()[1]  # Límite derecho de la figura en Matplotlib
    fig_ymin = ax.get_ylim()[0]  # Límite inferior de la figura (parte más baja)

    if current_selector_key == 'Excepción':
        rectangles['Excepción'][current_page_index] = coords  # Guardar por página

    elif current_selector_key == 'Encabezado':
        # Obtener el ancho total del PDF
        # pdf_width = pdf.pages[current_page_index].width  # Ancho real del PDF


        # Definir la primera mitad (como lo dibujó el usuario)
        left_rect = (coords[0], coords[1], coords[2], coords[3])

        # Definir la segunda mitad (desde el borde derecho del primero hasta el ancho total del PDF)
        right_rect = (coords[2], coords[1], fig_xmax, coords[3])

        # Almacenar las coordenadas en la estructura correcta
        rectangles['Encabezado']['left']['coords'] = left_rect
        rectangles['Encabezado']['right']['coords'] = right_rect

        if Config.DEBUG_PRINTS:
            print(f"Encabezado dividido en dos mitades: \n"
                  f"Izquierda: {rectangles['Encabezado']['left']['coords']} \n"
                  f"Derecha: {rectangles['Encabezado']['right']['coords']}")
            
    elif current_selector_key == 'Columna izquierda':
        # Definir la columna izquierda (como lo dibujó el usuario)
        left_col_rect = (coords[0], coords[1], coords[2], coords[3])

        # Definir la columna derecha con la misma altura que la izquierda
        right_col_rect = (coords[2], coords[1], fig_xmax, coords[3])

        # Definir el pie de página (desde el límite inferior de la columna hasta el fondo de la figura)
        footer_rect = (ax.get_xlim()[0], coords[3], fig_xmax, fig_ymin)

        rectangles['Columna izquierda']['coords'] = left_col_rect
        rectangles['Columna derecha']['coords'] = right_col_rect
        rectangles['Pie de página']['coords'] = footer_rect

        if Config.DEBUG_PRINTS:
            print(f"Columna izquierda definida en: {left_col_rect}")
            print(f"Columna derecha generada automáticamente en: {right_col_rect}")
            print(f"Pie de página generado automáticamente en: {footer_rect}")

    else:
        rectangles[current_selector_key]['coords'] = coords
        if Config.DEBUG_PRINTS:
            print(f"{current_selector_key} definido en: {coords}")

    show_page()

# Función para cambiar directamente entre áreas
def set_selector_key(area):
    global current_selector_key
    current_selector_key = area
    if Config.DEBUG_PRINTS:
        print(f"Ahora editando: {current_selector_key}")

# Funciones para la navegación de páginas
def next_page(event):
    global current_page_index
    if current_page_index < len(pdf.pages) - 1:
        current_page_index += 1
        show_page()

def prev_page(event):
    global current_page_index
    if current_page_index > 0:
        current_page_index -= 1
        show_page()

# Función para procesar el PDF final
def confirm_and_process(pdf_bytes,event = None):
    global perimeter_issue_detected  # Usamos la variable global
    print("[INFO] detectando problemas en el perímetro. Generando PDF...")

    # Reiniciar el estado de `perimeter_issue_detected` antes de procesar
    perimeter_issue_detected = False  

    # Nueva validación para el encabezado
    encabezado_definido = ('left' in rectangles['Encabezado'] and 'right' in rectangles['Encabezado'] and
                           rectangles['Encabezado']['left'].get('coords') is not None and
                           rectangles['Encabezado']['right'].get('coords') is not None)

    # Modificar validación para verificar `left` y `right` del encabezado
    if (encabezado_definido and
        all(rect.get('coords') is not None for key, rect in rectangles.items() if key not in ['Encabezado', 'Excepción'])):
        
        process_pdf(pdf_bytes)
        if Config.DEBUG_PRINTS:
            print(f"[DEBUG] Valor de `perimeter_issue_detected` después de `process_pdf()`: {perimeter_issue_detected}")

        if perimeter_issue_detected:
            # if Config.DEBUG_PRINTS:
            print("[AVISO] Se detectaron problemas con el perímetro en al menos una región. No se generará el PDF.")
            crop_data.clear()  # Limpiar la lista de datos de recorte
        else:
            # if Config.DEBUG_PRINTS:
            print("[INFO] No se detectaron problemas en el perímetro. Generando PDF...")
            apply_crop_with_pikepdf(pdf_bytes)  # Solo se ejecuta si no hubo problemas en el perímetro
            # plt.close()
    else:
        # if Config.DEBUG_PRINTS:
        print("Error: No todas las áreas obligatorias han sido definidas.")
        crop_data.clear()  # Limpiar la lista de datos de recorte

# Procesamiento del PDF
def process_pdf(pdf_bytes):
    new_doc = fitz.open()  # Documento de destino
    original_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")  # Abrir desde memoria

    # Verificar si el encabezado está definido con ambas mitades y sus coordenadas son válidas
    if ('left' in rectangles['Encabezado'] and 'right' in rectangles['Encabezado'] and
        rectangles['Encabezado']['left']['coords'] is not None and
        rectangles['Encabezado']['right']['coords'] is not None):

        left_coords = rectangles['Encabezado']['left']['coords']
        right_coords = rectangles['Encabezado']['right']['coords']

        # Enviar ambas mitades a crop_and_add_to_pdf()
        crop_and_add_to_pdf(0, left_coords, pdf_bytes)
        crop_and_add_to_pdf(0, right_coords, pdf_bytes)

    else:
        print("[ERROR] El encabezado no está completamente definido o sus coordenadas son inválidas.")

    for page_number in range(len(original_pdf)):
        if page_number in rectangles['Excepción']:
            exception_coords = rectangles['Excepción'][page_number]
            
            # Procesar la parte superior de las columnas (antes de la excepción)
            for col in ['Columna izquierda', 'Columna derecha']:
                col_coords = rectangles[col]['coords']
                if col_coords:
                    left, top, right, bottom = col_coords
                    ex_left, ex_top, ex_right, ex_bottom = exception_coords

                    if top < ex_top:
                        crop_and_add_to_pdf( page_number, (left, top, right, ex_top),pdf_bytes)

            # Agregar la página de la excepción
            crop_and_add_to_pdf( page_number, exception_coords,pdf_bytes)

            # Procesar la parte inferior de las columnas (después de la excepción)
            for col in ['Columna izquierda', 'Columna derecha']:
                col_coords = rectangles[col]['coords']
                if col_coords:
                    left, top, right, bottom = col_coords
                    ex_left, ex_top, ex_right, ex_bottom = exception_coords

                    if bottom > ex_bottom:
                        crop_and_add_to_pdf( page_number, (left, ex_bottom, right, bottom),pdf_bytes)
        else:
            crop_and_add_to_pdf( page_number, rectangles['Columna izquierda']['coords'],pdf_bytes)
            crop_and_add_to_pdf( page_number, rectangles['Columna derecha']['coords'],pdf_bytes)
    crop_and_add_to_pdf(-1, rectangles['Pie de página']['coords'],pdf_bytes)

    # **Eliminado**: No agregamos el PDF completo al final
    # crop_and_add_to_pdf(new_doc, original_pdf, -1, rectangles['Pie de página']['coords'])
        
    # new_doc.save("nuevo_documento.pdf")
    new_doc.close()
    # print("PDF generado exitosamente como 'nuevo_documento.pdf'")

# Abrir el PDF de origen
# pdf_origen = fitz.open(pdf_path)

# Crear un nuevo PDF para el destino
# pdf_destino = fitz.open()

# Mostrar la primera página para definir áreas
with pdfplumber.open(pdf_path) as pdf:
    pdf_bytes = pdfplumber_to_fitz(pdf)  # Convertir pdfplumber a BytesIO para fitz    
    # Asegurar que el stream está en la posición correcta antes de usarlo
    pdf_bytes.seek(0)

# process_pdf(pdf_bytes)  # Pasarlo a PyMuPDF (fitz) sin abrirlo de nuevo

fig, ax = plt.subplots(figsize=(12, 7))

# Botones de navegación (abajo)
axprev = plt.axes([0.2, 0.05, 0.1, 0.05])  # Anterior (más a la izquierda)
axnext = plt.axes([0.35, 0.05, 0.1, 0.05])  # Siguiente (centrado)
axconfirm = plt.axes([0.7, 0.05, 0.15, 0.05])  # Confirmar (a la derecha)

bprev = Button(axprev, 'Anterior')
bprev.on_clicked(prev_page)

bnext = Button(axnext, 'Siguiente')
bnext.on_clicked(next_page)

bconfirm = Button(axconfirm, 'Confirmar')
bconfirm.on_clicked(functools.partial(confirm_and_process, pdf_bytes))

# Botones para seleccionar áreas (arriba)
areas = ['Encabezado', 'Pie de página', 'Columna izquierda', 'Columna derecha', 'Excepción']
colors = ['r', 'g', 'b', 'm', 'orange']
positions = [0.26, 0.37, 0.48, 0.59, 0.70]

buttons = []
for i, area in enumerate(areas):
    axarea = plt.axes([positions[i], 0.9, 0.1, 0.05])
    btn = Button(axarea, area, color=colors[i])
    btn.on_clicked(lambda event, a=area: set_selector_key(a))
    buttons.append(btn)  # Guardar referencia para evitar que se sobrescriba

toggle_selector = RectangleSelector(
    ax, onselect, useblit=True,
    button=[1],  # Botón izquierdo del mouse
    minspanx=5, minspany=5, spancoords='pixels', interactive=True
)

show_page()
plt.show()