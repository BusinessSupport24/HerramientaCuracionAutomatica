
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
  - `openai`
  - `matplotlib`
  - `pandas`
  - `cv2` (OpenCV)
  - `pdfplumber`
  - `beautifulsoup4`
  - `pypandoc`
  - `numpy`
  - `re`
  - `dateparser`
  - `os`
  - `requests`

Puedes instalar las dependencias necesarias ejecutando:

```bash
pip install -r requirements.txt
```

---

## Instalación

1. **Clonar el repositorio**: Primero, clona el repositorio en tu máquina local.

   ```bash
   git clone https://github.com/tuusuario/convertir-ofertas-claro-markdown.git
   cd convertir-ofertas-claro-markdown
   ```

2. **Instalar las dependencias**: Si no lo has hecho aún, instala las dependencias necesarias:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar API Key de OpenAI**: Para enviar imágenes a la API de OpenAI, necesitas tener una clave de API de OpenAI configurada en tu entorno. Asegúrate de establecer la variable de entorno `OPENAI_API_KEY` con tu clave.

   ```bash
   export OPENAI_API_KEY="tu-clave-api"
   ```

---

## Uso

1. **Ejecutar el script**: Para comenzar, ejecuta el script principal en tu terminal. El script abrirá una ventana donde podrás seleccionar el archivo PDF a convertir.

   ```bash
   python convertir_pdf_a_markdown.py
   ```

2. **Delimitar áreas de interés**: Tras seleccionar el PDF, se abrirá una figura interactiva en `matplotlib` donde podrás delimitar las áreas del PDF (columnas, encabezados, pies de página) que deseas procesar. Haz clic y arrastra el ratón para crear los rectángulos de delimitación.

3. **Verificación y edición de tablas**: Las tablas extraídas se mostrarán en formato HTML para su verificación. Asegúrate de que se han extraído correctamente.

4. **Proceso de extracción de imágenes**: Las imágenes se enviarán automáticamente a la API de ChatGPT para extraer el texto.

5. **Reemplazo de llaves**: Una vez el texto, tablas e imágenes estén procesados, las llaves de tabla e imagen se reemplazarán por su contenido correspondiente en formato Markdown.

6. **Revisión final**: El programa abrirá la carpeta con todos los recursos generados (imágenes, tablas HTML, PDFs) para su revisión.

---

## Estructura del Proyecto

El proyecto tiene la siguiente estructura de directorios:

```
convertir-ofertas-claro-markdown/
│
├── convertir_pdf_a_markdown.py       # Script principal para convertir el PDF a Markdown
├── recursos/                         # Carpeta donde se almacenan los archivos generados
│   ├── imagenes/                     # Carpeta con imágenes extraídas
│   ├── tablas_html/                  # Carpeta con tablas en formato HTML
│   └── pdfs_generados/               # Carpeta con PDFs generados
├── requirements.txt                  # Archivo con las dependencias necesarias
└── README.md                         # Este archivo
```

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
