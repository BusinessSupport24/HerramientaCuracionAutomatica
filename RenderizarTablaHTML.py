import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QEventLoop
import os
import cv2
import DetectarCentroidesDeCeldas as dcdc
import ExtraerEstructuraDeTabla as eedt
import Config

class HTMLViewer(QMainWindow):
    """
    Ventana principal para mostrar contenido HTML usando un visor web (QWebEngineView).
    
    Esta clase crea una ventana PyQt que muestra el HTML recibido (generalmente el render
    de una tabla) y utiliza un event loop para pausar la ejecución hasta que el usuario cierre la ventana.
    """
    def __init__(self, html_content, event_loop, tabla_actual):
        """
        Inicializa la ventana de visualización con el HTML proporcionado.
        
        :param html_content: String con el contenido HTML a mostrar.
        :param event_loop: QEventLoop que permite esperar hasta que la ventana se cierre.
        :param tabla_actual: Identificador o título de la tabla, utilizado para el título de la ventana.
        """
        super().__init__()
        self.setWindowTitle(tabla_actual)
        self.setGeometry(100, 100, 800, 600)

        # Crear el widget del navegador y cargar el HTML
        self.browser = QWebEngineView()
        self.browser.setHtml(html_content)

        # Configurar el layout de la ventana
        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Guardar la referencia al event loop para poder detenerlo al cerrar la ventana
        self.event_loop = event_loop

    def closeEvent(self, event):
        """
        Método sobrescrito que se llama cuando la ventana se está cerrando.
        Detiene el event loop para permitir que la ejecución del programa continúe.
        
        :param event: Evento de cierre.
        """
        self.event_loop.quit()
        event.accept()

def generar_html_tabla(tabla):
    """
    Genera una cadena HTML que representa una tabla a partir de una estructura de datos.
    
    La estructura de 'tabla' se espera que sea una matriz (lista de listas) donde cada elemento
    es un diccionario que contiene, al menos, los siguientes campos:
      - "contenido": Texto a mostrar en la celda.
      - "rowspan": Número de filas que la celda abarca (1 si no se fusiona con otras).
      - "colspan": Número de columnas que la celda abarca (1 si no se fusiona con otras).
      
    Se respetan los atributos rowspan y colspan. Se define un estilo básico con borde y alineación central.

    :param tabla: Lista de listas que representa la estructura de la tabla.
    :return: Cadena de texto con el HTML generado.
    """
    html = "<html><body>"
    html += "<table border='1' style='border-collapse: collapse; text-align: center; width: 100%;'>\n"

    # Procesar cada fila de la tabla
    for fila in tabla:
        html += "  <tr>\n"
        # Procesar cada celda de la fila
        for celda in fila:
            # Solo se generan celdas que tengan valores positivos para rowspan y colspan
            if celda["rowspan"] > 0 and celda["colspan"] > 0:
                html += f"    <td rowspan='{celda['rowspan']}' colspan='{celda['colspan']}' style='white-space: pre-line;'>{celda['contenido']}</td>\n"
        html += "  </tr>\n"

    html += "</table>"
    html += "</body></html>"
    
    return html

def guardar_tabla(tabla, tabla_actual, folder_path, path_tablas):
    """
    Guarda la tabla renderizada en formato HTML en un archivo.

    Procedimiento:
      - Se genera el contenido HTML de la tabla a partir de la estructura.
      - Se determina la ruta de salida, tomando como nombre el identificador 'tabla_actual'.
      - Se crea la carpeta de salida si no existe.
      - Se guarda el contenido HTML en el archivo especificado.
    
    :param tabla: Estructura de la tabla (lista de listas de celdas).
    :param tabla_actual: Cadena o identificador utilizado como parte del nombre de archivo.
    :param folder_path: Ruta de la carpeta principal.
    :param path_tablas: Subcarpeta o ruta para guardar los archivos HTML de tablas.
    """
    html_content = generar_html_tabla(tabla)
    # Se determina el nombre del archivo a partir de la clave de la tabla
    output_file = os.path.join(path_tablas, tabla_actual.split("\\")[-1].split(".")[0] + ".html")

    # Crear la carpeta si no existe
    os.makedirs(folder_path, exist_ok=True)

    # Guardar el contenido HTML en el archivo
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(html_content)

    if Config.DEBUG_PRINTS:
        print(f"Archivo guardado en: {output_file}")

def mostrar_html_pyqt(tabla, tabla_actual):
    """
    Muestra el HTML generado a partir de la tabla en una ventana PyQt.
    
    Se crea un event loop para pausar la ejecución del programa hasta que el usuario
    cierre la ventana del visualizador de HTML.

    :param tabla: Estructura de la tabla (lista de listas de celdas).
    :param tabla_actual: Identificador o título de la tabla, utilizado como título de la ventana.
    """
    global app  # Se reutiliza una única instancia de QApplication

    html_content = generar_html_tabla(tabla)
    if Config.DEBUG_PRINTS:
        print("Contenido HTML\n", html_content)
    event_loop = QEventLoop()  # Crear un event loop para esperar el cierre de la ventana
    viewer = HTMLViewer(html_content, event_loop, tabla_actual)
    viewer.show()

    # Esperar a que el usuario cierre la ventana
    event_loop.exec_()

def mostrar_html_todas_las_tablas(lista_de_tablas):
    """
    Muestra todas las tablas (una lista de estructuras de tabla) en una sola ventana PyQt.
    
    Se concatena el HTML de todas las tablas, se crea un event loop para pausar la ejecución
    hasta que el usuario cierre la ventana, y se muestra el resultado en un QWebEngineView.

    :param lista_de_tablas: Lista de estructuras de tabla (cada una es una lista de listas).
    """
    app = QApplication.instance()  # Obtener la instancia existente de QApplication, si la hay
    if not app:
        app = QApplication(sys.argv)

    # Construir el HTML concatenado de todas las tablas
    html_content = "<html><body><h1>Tablas Detectadas</h1>"
    for tabla in lista_de_tablas:
        html_content += generar_html_tabla(tabla)
    html_content += "</body></html>"

    event_loop = QEventLoop()  # Crear un event loop para pausar la ejecución
    viewer = HTMLViewer(html_content, event_loop, "")
    viewer.show()
    event_loop.exec_()
    # Nota: La línea app.exec_() se comenta para mantener el control en este event loop

def image_to_HTML(path_image, tabla_actual):
    """
    Procesa una imagen que contiene una tabla y devuelve la estructura de la tabla en HTML.
    
    Procedimiento:
      - Se detectan las celdas en la imagen utilizando la función detectar_celdas del módulo dcdc.
      - Se genera una malla (cuadrícula) sobre la imagen basándose en las coordenadas detectadas.
      - Se construye la estructura de la tabla (con atributos como rowspan y colspan) usando la función
        generar_estructura_tabla_new del módulo eedt.
      - Se retorna la estructura de la tabla, junto con información adicional (coordenadas de celdas, centros, etc.)
    
    :param path_image: Ruta del archivo de imagen que contiene la tabla.
    :param tabla_actual: Identificador o título para la tabla, utilizado para depuración o visualización.
    :return: Una tupla con la estructura de la tabla, lista de coordenadas de celdas, centros de celdas, ancho y alto de la imagen, y las dimensiones de la tabla.
    """
    # Detectar celdas y obtener información sobre sus coordenadas y centroides
    imagenes_celdas, coordenadas_celdas, centros_celdas, imagen_width, imagen_height, dimensiones_tabla = dcdc.detectar_celdas(path_image)

    if Config.DEBUG_PRINTS:
        print("\nCantidad de celdas encontradas:\n", len(imagenes_celdas), "\n")

    # Generar la malla (cuadrícula) a partir de las coordenadas de las celdas detectadas
    lineas_x, lineas_y, max_filas, max_columnas, imagen_malla, umbral_x, umbral_y = eedt.generar_malla(coordenadas_celdas, imagen_width, imagen_height)

    # Construir la cuadrícula con las coordenadas de cada celda de la malla
    cuadricula = []
    for i in range(len(lineas_y)):
        fila = []
        for j in range(len(lineas_x)):
            x = lineas_x[j]
            y = lineas_y[i]
            w = lineas_x[j+1] - x if j < len(lineas_x) - 1 else imagen_width - x
            h = lineas_y[i+1] - y if i < len(lineas_y) - 1 else imagen_height - y
            fila.append({"x": x, "y": y, "w": w, "h": h})
        cuadricula.append(fila)

    # Generar la estructura de la tabla a partir de la cuadricula y las celdas detectadas
    tabla_generada = eedt.generar_estructura_tabla_new(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, tabla_actual)

    if Config.DEBUG_PRINTS:
        print("Tabla generada:")
        for fila in tabla_generada:
            print(fila)

    # La ventana con la tabla renderizada se puede mostrar llamando a mostrar_html_pyqt() (comentado aquí)
    return tabla_generada, coordenadas_celdas, centros_celdas, imagen_width, imagen_height, dimensiones_tabla
