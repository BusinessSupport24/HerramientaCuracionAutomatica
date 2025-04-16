import base64
import os
from openai import OpenAI

def enviar_Imagenes_A_GPT(folder_path):
    """
    Envía todas las imágenes de una carpeta a la API de ChatGPT para que sean procesadas
    y se extraiga el texto de cada imagen. El texto extraído se guarda en un archivo .txt
    con el mismo nombre de la imagen.

    Procedimiento:
      1. Se configura la API de OpenAI definiendo la clave de la API y otros parámetros.
      2. Se define una función interna para codificar imágenes a Base64.
      3. Se itera sobre cada archivo en la carpeta indicada; para cada imagen (archivos .jpg, .jpeg o .png):
         a. Se codifica la imagen a Base64.
         b. Se envía una solicitud a la API con un mensaje que incluye el texto y la imagen codificada (en data URI).
         c. Se extrae la respuesta de la API y se guarda en un archivo .txt en la misma carpeta.
    
    :param folder_path: Ruta a la carpeta que contiene las imágenes a enviar.
    """
    
    # Configuración de la clave API (debe configurarse la clave correspondiente)
    os.environ["OPENAI_API_KEY"] = ""

    # Crear el cliente de OpenAI. Se deben especificar organización y proyecto según configuración.
    client = OpenAI(
        organization="",
        project=""
    )

    def encode_image(image_path):
        """
        Codifica una imagen a Base64.

        :param image_path: Ruta de la imagen a codificar.
        :return: Cadena con la imagen codificada en Base64.
        """
        with open(image_path, "rb") as image_file:
            # Leer los bytes de la imagen y codificarlos en Base64, luego decodificar a UTF-8 para obtener un string
            return base64.b64encode(image_file.read()).decode("utf-8")

    # Se recorre la carpeta para procesar cada archivo de imagen (extensiones jpg, jpeg, png)
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Obtener la ruta completa de la imagen
            image_path = os.path.join(folder_path, file_name)
            # Codificar la imagen a Base64
            base64_image = encode_image(image_path)
            
            # Enviar la imagen a la API de ChatGPT utilizando el modelo especificado (gpt-4o-mini)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Lee y entiende por completo el texto de la siguiente imagen, "
                                    "y devuelve el texto tal cual como está, solo que organizado "
                                    "para una mejor lectura, en formato **TEXTO**"
                                ),
                            },
                            {
                                "type": "image_url",
                                # Utiliza una URI de datos para la imagen codificada en Base64
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
            )
            
            # Extraer el contenido textual de la respuesta recibida de la API
            output_text = response.choices[0].message.content
            
            # Construir la ruta para el archivo de salida, utilizando el mismo nombre base de la imagen
            base_name = os.path.splitext(file_name)[0]
            txt_file_path = os.path.join(folder_path, f"{base_name}.txt")
            
            # Guardar el texto extraído en un archivo de texto (.txt) con codificación UTF-8
            with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(output_text)
                
            # Imprimir en la consola la ruta donde se ha guardado la respuesta
            print(f"Respuesta guardada en: {txt_file_path}")
