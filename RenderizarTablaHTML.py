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
    """Ventana que muestra una tabla HTML usando QWebEngineView."""
    def __init__(self, html_content, event_loop,tabla_actual):
        super().__init__()
        self.setWindowTitle(tabla_actual)
        self.setGeometry(100, 100, 800, 600)

        # Crear el visor web
        self.browser = QWebEngineView()
        self.browser.setHtml(html_content)

        # Configurar el layout
        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Guardar referencia del event loop
        self.event_loop = event_loop

    def closeEvent(self, event):
        """Cierra la ventana y detiene el event loop."""
        self.event_loop.quit()
        event.accept()

def generar_html_tabla(tabla):
    """Genera el HTML de la tabla respetando rowspan y colspan."""
    html = "<html><body>"
    html += "<table border='1' style='border-collapse: collapse; text-align: center; width: 100%;'>\n"

    for fila in tabla:
        html += "  <tr>\n"
        for celda in fila:
            if celda["rowspan"] > 0 and celda["colspan"] > 0:
                html += f"    <td rowspan='{celda['rowspan']}' colspan='{celda['colspan']}'>{celda['contenido']}</td>\n"
        html += "  </tr>\n"

    html += "</table>"
    html += "</body></html>"
    
    return html

def guardar_tabla(tabla,tabla_actual,folder_path,path_tablas):
    html_content = generar_html_tabla(tabla)

    # output_folder =  tabla_actual.split("\\")[0] # Puedes cambiar la ruta
    output_file = os.path.join(path_tablas, tabla_actual.split("\\")[-1].split(".")[0]+".html")

    # Crear la carpeta si no existe
    os.makedirs(folder_path, exist_ok=True)

    # Guardar el archivo
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(html_content)

    if Config.DEBUG_PRINTS:
        print(f"Archivo guardado en: {output_file}")

def mostrar_html_pyqt(tabla,tabla_actual):
    """Muestra la tabla en una ventana PyQt y espera a que el usuario la cierre antes de continuar."""
    global app  # Reutilizar una sola instancia de QApplication

    html_content = generar_html_tabla(tabla)
    if Config.DEBUG_PRINTS:
        print("Contenido HTML\n",html_content)
    event_loop = QEventLoop()  # Crear un EventLoop para pausar la ejecución
    viewer = HTMLViewer(html_content, event_loop,tabla_actual)
    viewer.show()

    # Esperar hasta que el usuario cierre la ventana antes de continuar
    event_loop.exec_()

def mostrar_html_todas_las_tablas(lista_de_tablas):
    """Muestra todas las tablas en una sola ventana PyQt."""
    app = QApplication.instance()  # Obtener la instancia de QApplication si ya existe
    if not app:
        app = QApplication(sys.argv)

    # Generar HTML concatenado de todas las tablas
    html_content = "<html><body><h1>Tablas Detectadas</h1>"
    for tabla in lista_de_tablas:
        html_content += generar_html_tabla(tabla)
    html_content += "</body></html>"

    event_loop = QEventLoop()  # Crear un EventLoop para pausar la ejecución
    viewer = HTMLViewer(html_content,event_loop)
    viewer.show()
    event_loop.exec_()
    # app.exec_()  # Mantener la aplicación abierta hasta que se cierre


def image_to_HTML(path_image,tabla_actual):

    # Detectar celdas y obtener coordenadas directamente
    imagenes_celdas, coordenadas_celdas, centros_celdas, imagen_width, imagen_height, dimensiones_tabla = dcdc.detectar_celdas(path_image)

    if Config.DEBUG_PRINTS:
        print("\nCanitdad de celdas encontrdadas:\n",len(imagenes_celdas),"\n")

    # Generar estructura de la tabla con rowspan y colspan
    # Generar la malla
    lineas_x, lineas_y, max_filas, max_columnas, imagen_malla, umbral_x, umbral_y = eedt.generar_malla(coordenadas_celdas, imagen_width, imagen_height)

    # Crear la estructura de la cuadrícula
    cuadricula = [[{"x": x, "y": y, "w": 0, "h": 0} for x in lineas_x] for y in lineas_y]

    # Generar la estructura de la tabla con celdas unidas aplicando el umbral
    tabla_generada = eedt.generar_estructura_tabla(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, umbral_x, umbral_y)


    # Mostrar la tabla generada
    if Config.DEBUG_PRINTS:
        print("tabla generada:")
        for fila in tabla_generada:
            print(fila)

    # Ejecutar la ventana con la tabla renderizada
    # mostrar_html_pyqt(tabla_generada,tabla_actual)

    return tabla_generada, coordenadas_celdas, centros_celdas, imagen_width, imagen_height, dimensiones_tabla

# def obtener_imagenes_con_ruta(ruta_carpeta):
#     """Obtiene todas las imágenes de una carpeta y devuelve una lista de rutas completas."""
#     extensiones_validas = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}
#     imagenes_con_ruta = []

#     if not os.path.exists(ruta_carpeta):
#         print(f"Error: La carpeta '{ruta_carpeta}' no existe.")
#         return []

#     for archivo in os.listdir(ruta_carpeta):
#         ruta_completa = os.path.join(ruta_carpeta, archivo)
#         if os.path.isfile(ruta_completa) and os.path.splitext(archivo)[1].lower() in extensiones_validas:
#             imagenes_con_ruta.append(ruta_completa)

#     return imagenes_con_ruta

# def get_images_from_path(ruta_carpeta):
#     # Inicializar QApplication una sola vez al inicio
#     app = QApplication(sys.argv)

#     # Definir la carpeta con imágenes
#     # ruta_carpeta = "imagenes_De_Prueba"
#     lista_rutas_imagenes = obtener_imagenes_con_ruta(ruta_carpeta)

#     print("Rutas completas de las imágenes encontradas:")
#     for ruta in lista_rutas_imagenes:
#         print(ruta)
        
#         # Mostrar imagen con OpenCV (si es necesario, pero sin bloquear)
#         # imagen = cv2.imread(ruta)
          # if Config.DEBUG_IMAGES:
#         #     cv2.imshow("Imagen", imagen)
        
#         # Llamar a la función para procesar la imagen y mostrar HTML
#         image_to_HTML(ruta)
        
#         # Cerrar la imagen de OpenCV antes de continuar con la siguiente
#         cv2.destroyAllWindows()

#     # Salir de la aplicación cuando termine el bucle
#     app.quit()