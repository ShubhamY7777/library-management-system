import os
import easyocr

reader = easyocr.Reader(['en'])

folder = "uploads/shelf_images"

files = os.listdir(folder)

print("Images Found:")
print(files)

image_path = os.path.join(folder, files[-1])

print("\nUsing:", image_path)

results = reader.readtext(image_path)

for r in results:
    print(r)