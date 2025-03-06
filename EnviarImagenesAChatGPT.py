import base64
import os
from openai import OpenAI

def enviar_Imagenes_A_GPT(folder_path):
    # Configuración de la API
    os.environ["OPENAI_API_KEY"] = ""

    client = OpenAI(
        organization="org-oHZFTVwB9LqBmATCIuqBbMHq",
        project="proj_jNvsFykTfzr8vTF8ULyY4rwa"
    )

    # Función para codificar la imagen a Base64
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    # Ruta de la carpeta que contiene las imágenes
    folder_path

    # Iterar sobre los archivos de la carpeta
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(folder_path, file_name)
            base64_image = encode_image(image_path)
            
            # Enviar la imagen a la API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": ("Lee y entiende por completo el texto de la siguiente imagen, "
                                        "y devuelve el texto tal cual como está, solo que organizado "
                                        "para una mejor lectura, en formato **TEXTO**"),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
            )
            
            # Extraer el contenido de la respuesta
            output_text = response.choices[0].message.content
            
            # Guardar la respuesta en un archivo .txt con el mismo nombre de la imagen
            base_name = os.path.splitext(file_name)[0]
            txt_file_path = os.path.join(folder_path, f"{base_name}.txt")
            with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(output_text)
                
            print(f"Respuesta guardada en: {txt_file_path}")