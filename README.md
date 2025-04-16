
# Proyecto de Conversión de Ofertas Comerciales de CLARO a Markdown

## Descripción

Este proyecto tiene como objetivo convertir ofertas comerciales mensuales de la empresa CLARO, contenidas en archivos PDF, en un formato Markdown fácilmente procesable. El proceso de conversión no solo extrae el texto del PDF, sino que también maneja tablas e imágenes, convirtiéndolas en contenido accesible y organizado.

### Objetivo Principal

Dado un archivo PDF con las ofertas comerciales mensuales de CLARO, el programa realiza los siguientes pasos:

1. **Selección del archivo PDF**: El usuario selecciona el archivo PDF a convertir desde una ventana de explorador de archivos.
2. **Delimitación de columnas, encabezados y pies de página**: Mediante una figura interactiva de `matplotlib`, el usuario delimita manualmente las áreas de interés (columnas, encabezados, pies de página) para facilitar la extracción de información organizada.
3. **Extracción y procesamiento de tablas**: Las tablas del PDF se extraen, procesan y se convierten a formato HTML para su visualización y verificación. Las tablas se almacenan con una llave única.
4. **Extracción y procesamiento de imágenes**: Las imágenes del PDF se envían a la API de ChatGPT para extraer el texto contenido en ellas, el cual se reemplaza por una llave única.
5. **Conversión a Markdown**: El texto plano extraído, las tablas e imágenes reemplazadas por sus llaves, se transforman en un archivo Markdown.
6. **Reemplazo de llaves por texto**: Las llaves de tablas e imágenes se reemplazan por el contenido extraído, produciendo el archivo Markdown final.
7. **Encabezado de la oferta comercial**: Se agrega un encabezado al archivo Markdown con información sobre la oferta comercial contenida en el PDF.
8. **Revisión final**: El programa abre la carpeta con todos los recursos extraídos (imágenes, tablas HTML, PDFs generados, etc.) para que el usuario pueda revisar el contenido antes de la validación final.

Este enfoque permite una fácil integración y revisión de los datos extraídos del PDF, asegurando que el contenido esté bien organizado y listo para su uso.

---

## Características

- **Interactividad**: El usuario puede delimitar las áreas de interés de forma interactiva en una figura generada por `matplotlib`.
- **API de ChatGPT**: Las imágenes se procesan mediante la API de ChatGPT para extraer el texto que contienen.
- **Generación automática de Markdown**: El proyecto convierte automáticamente el texto, tablas e imágenes extraídas en un archivo Markdown organizado.
- **Archivos de recursos generados**: Se guardan recursos como imágenes extraídas, tablas en formato HTML, y PDFs generados para revisión.

---

## Requisitos

Para ejecutar este proyecto, necesitas tener las siguientes dependencias instaladas:

- Python 3.x
- Librerías de Python:
  - `beautifulsoup4`
  - `colorama`
  - `dateparser`
  - `markdownify`
  - `matplotlib`
  - `numpy`
  - `openai`
  - `opencv-python` (como `cv2`)
  - `pdfplumber`
  - `pikepdf`
  - `pillow`
  - `PyMuPDF`
  - `pypandoc`
  - `PyQt5`
  - `PyQt5-Qt5`
  - `PyQt5_sip`
  - `PyQtWebEngine`
  - `PyQtWebEngine-Qt5`
  - `tabulate`

Puedes instalar las dependencias necesarias ejecutando:

```bash
pip install -r requirements.txt
```

---

## Instalación

1. **Clonar el repositorio**: Primero, clona el repositorio en tu máquina local.

   ```bash
   git clone https://github.com/BusinessSupport24/HerramientaCuracionAutomatica.git
   ```

2. **Instalar las dependencias**: Si no lo has hecho aún, instala las dependencias necesarias:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar API Key de OpenAI**: Para enviar imágenes a la API de OpenAI, necesitas tener una clave de API de OpenAI configurada en tu entorno. Asegúrate de establecer la variable de entorno `OPENAI_API_KEY` con tu clave, en el archivo `EnviarImagenesAChatGPT.py`.

   ```bash
      # Configuración de la clave API (debe configurarse la clave correspondiente)
      os.environ["OPENAI_API_KEY"] = ""

      # Crear el cliente de OpenAI. Se deben especificar organización y proyecto según configuración.
      client = OpenAI(
         organization="",
         project=""
      )
   ```

---

## Ejecucion de los scripts

1. **Ejecutar el script**: Para comenzar, ejecuta el script principal  en tu terminal. El script abrirá una ventana donde podrás seleccionar el archivo PDF a convertir.

   ```bash
   python CortarPDFEnColumnas.py
   ```

2. **Delimitar áreas de interés**: Tras seleccionar el PDF, se abrirá una figura interactiva en `matplotlib` donde podrás delimitar las áreas del PDF (columnas, encabezados, pies de página) que deseas procesar. Haz clic y arrastra el ratón para crear los rectángulos de delimitación.

3. **Verificación y edición de tablas**: Las tablas extraídas se guardarán en formato HTML, en la carpeta `tablas_html` para su verificación. Asegúrate de que se han extraído correctamente.

4. **Proceso de extracción de imágenes**: Las imágenes se enviarán automáticamente a la API de ChatGPT para extraer el texto, y estas se guardarán en la carpeta `imagenes_extraidas`, junto con sus respectivas respuestas.

5. **Reemplazo de llaves**: Una vez el texto, tablas e imágenes estén procesados, las llaves unicas de tabla e imagen se reemplazarán por su contenido correspondiente en formato Markdown.

6. **Revisión final**: El programa abrirá la carpeta con todos los recursos generados (imágenes, tablas HTML, PDFs) para su respectiva revisión.

---

## Estructura del Proyecto

El proyecto tiene la siguiente estructura de directorios:

```
convertir-ofertas-claro-markdown/
│
├── README.md                         # Documentación del proyecto
├── requirements.txt                  # Archivo con las dependencias necesarias
│
├── Config.py                         # Configuración global del proyecto
│
├── CortarPDFEnColumnas.py            # Divide el PDF en columnas
├── DetectarCentroidesDeCeldas.py     # Detecta centroides de las celdas de tablas
├── DibujarContornosCuadrados.py      # Dibuja contornos rectangulares sobre las celdas detectadas
├── EliminarDatosInternosFisicos.py   # Limpia datos internos para verticalizacion y pdf sin texto
├── EliminarYEscribirImagenes.py      # Manejo de imágenes dentro del pdf verticalizado
├── EnviarImagenesAChatGPT.py         # Envío de imágenes al modelo de OpenAI
├── Extraer_Imagenes.py               # Extracción de imágenes del PDF
├── ExtraerEstructuraDeTabla.py       # Extrae estructura base de tablas basado en la imagen
├── ExtraerTablasSinTextoPDF.py       # Extrae tablas sin texto directamente del PDF
├── InyectarXObjects.py               # Inyecta objetos gráficos (XObjects) en el PDF
├── ObtenerTextoPlano.py              # Obtiene texto plano desde el PDF
├── OrganizarEncabezadoMD.py          # Organiza encabezado en archivo Markdown
├── PasarTextoPlanoAMarkdown.py       # Convierte texto plano a Markdown
├── ReemplazarImagenesDeMarkdown.py   # Reemplaza las llaves de las imágenes en el archivo Markdown
├── ReemplazarTablasDeMarkdown.py     # Reemplaza las llaves de las tablas en el archivo Markdown
├── RenderizarTablaHTML.py            # Renderiza las tablas extraidas del pdf a HTML
├── VerificarTablaCerrada.py          # Verifica si una tabla está cerrada correctamente
```
---
## Uso

A continuación se describe de forma resumida el flujo de trabajo para convertir un PDF a Markdown utilizando la interfaz gráfica:

### 1. Interfaz y botones principales

- **Visualización de la ventana de Matplotlib:**  
  Al iniciar, se abre una ventana de Matplotlib que muestra distintos botones para interactuar.  


- **Botón "Modo Móvil":**  
  Este botón es el más importante y se debe presionar antes de definir cualquier límite, dependiendo de si la oferta a convertir es para móvil o no.

- **Botones de navegación:**  
  - **Anterior**
  - **Siguiente**
  - **Confirmar**

- **Botones de delimitación:**  
  Estos botones varían según el modo seleccionado.
  
  _[Se muestra una imagen de la ventana inicial modo normal]_  

### 2. Modo Normal

En este modo se cuentan con cinco botones, pero únicamente se utilizan tres para delimitar:

- **Botón de Encabezado:**  
  - Se utiliza para delimitar el encabezado.  
  - Se debe dibujar un recuadro justo a la mitad horizontal del encabezado.  
  - Se debe verificar con los botones de siguiente y anterior que el recuadro no se sobrepone (colisiona) con ningún texto, tabla o imagen en todas las páginas.  
  _[Imagen de ejemplo de un encabezado en modo normal delimitado correctamente]_  

- **Botón de Columna Izquierda:**  
  - Se usa para delimitar las dos columnas y "verticalizar" el PDF, es decir, para que las columnas aparezcan en páginas separadas.  
  - Al definir este límite, automáticamente se asignan los límites para la columna derecha y el pie de página.  
  - Es fundamental evitar que el rectángulo delimite colisiones con otros elementos.  
  _[Imagen de ejemplo de un rectángulo de columna izquierda correctamente posicionado]_  

- **Botón de Excepción:**  
  - Muy importante para los casos en que, en un PDF con columnas, algún elemento (párrafo, tabla o imagen) ocupa el espacio de dos columnas.  
  - Se utiliza para encerrar ese elemento y asegurar que el reordenamiento de los contenidos sea correcto.  
  _[Imagen de ejemplo de un rectángulo de excepción correctamente posicionado]_  

> **Nota:**  
> Los botones de **columna derecha** y **pie de página** no se deben usar de forma manual, ya que sus límites se definen automáticamente al posicionar el rectángulo de la columna izquierda.

### 3. Modo Móvil

En este modo se recomienda usar dos botones principales:

_[Se muestra una imagen de la ventana inicial modo movil]_  

- **Botón de Encabezado Móvil:**  
  - Encierra únicamente el encabezado de información junto con su línea divisoria.  
  _[Imagen de ejemplo del botón de encabezado móvil correctamente posicionado]_  

- **Botón de Columna Móvil:**  
  - Debe encerrar prácticamente toda la página.  
  - **Importante:** En la mayoría de los casos, aunque el recuadro de la columna móvil pueda colisionar con algún elemento, el software no lo mostrará como error, pero se debe colocar con cuidado.  
  _[Imagen de ejemplo de la columna móvil correctamente posicionada]_
  _[Imagen de ejemplo de la columna móvil correctamente posicionada dos]_  

#### Manejo de casos particulares en modo móvil

- **Posicionamiento sin colisión imposible:**  
  En algunas páginas puede ser imposible posicionar el recuadro de la columna móvil sin que colisione por completo con algún elemento.  
  _[Imagen de ejemplo de un caso de colisión imposible]_  

- **Botón "Omitir Colisión":**  
  - Se utiliza junto con el botón de **Pie de Página** para casos donde el recuadro de la columna móvil colisiona.  
  - El botón de pie de página delimita el área desde el punto de click hasta el límite inferior del recuadro de columna móvil.  
  - **Importante:** No se debe usar el botón de "Pie de Página Móvil" sin haber posicionado primero el recuadro de columna móvil.  
  _[Imagen de ejemplo del botón de pie de página móvil posicionado]_  

### 4. Flujo General

- **Posicionamiento de Rectángulos:**  
  Los rectángulos se deben posicionar una única vez, y ese mismo posicionamiento se aplicará a todas las páginas. **La navegación (botones de siguiente y anterior)** sirve solo para verificar que el posicionamiento no colisione en ninguna página.

- **Confirmación Final:**  
  Una vez que todos los rectángulos estén correctamente posicionados, se presiona el botón de **Confirmar**.  
  - El sistema verifica que en ninguna página exista colisión entre los elementos delimitados.  
  - Si se detecta alguna colisión, se mostrará una nueva ventana con la página en la que se encuentra el problema.  
    _[Imagen de ejemplo del software detectando una colisión]_  
  - Si todo es correcto, el programa finaliza y genera la carpeta con el archivo Markdown, notificando al usuario la finalización del proceso.


---
## Contribuciones

Si deseas contribuir a este proyecto, por favor sigue los siguientes pasos:

1. Realiza un fork del proyecto.
2. Crea una nueva rama (`git checkout -b feature-nueva-funcionalidad`).
3. Realiza tus cambios y haz un commit de los mismos (`git commit -am 'Añadir nueva funcionalidad'`).
4. Sube tus cambios a tu fork (`git push origin feature-nueva-funcionalidad`).
5. Abre un Pull Request para que revisemos tus cambios.

---

## Licencia

Este proyecto está bajo la Licencia MIT - consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## Agradecimientos

Agradecemos el uso de herramientas como OpenAI y `matplotlib`, que han facilitado la implementación de este proyecto.
