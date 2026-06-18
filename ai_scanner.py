import easyocr

reader = easyocr.Reader(['en'])

def detect_books(image_path):
    results = reader.readtext(image_path)

    detected_texts = []

    for result in results:
        detected_texts.append(result[1])

    return detected_texts