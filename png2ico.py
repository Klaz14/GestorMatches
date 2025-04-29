from PIL import Image
import os

png_path = os.path.join("assets", "62838.png")
ico_path = os.path.join("assets", "62838.ico")

img = Image.open(png_path)
# Genera un .ico a 256×256
img.save(ico_path, format="ICO", sizes=[(256,256)])
print("Creado:", ico_path)
