import cv2
import easyocr
from rapidfuzz import fuzz

# Initialize OCR Reader
reader = easyocr.Reader(['en'])

def locate_book_by_text(book_name, image_path):

    print("\n==============================")
    print("Searching For:", book_name)
    print("==============================")

    image = cv2.imread(image_path)

    if image is None:
        print("Error: Image not found")
        return None

    rotations = [
        ("Original", image),
        ("90 Clockwise",
         cv2.rotate(
             image,
             cv2.ROTATE_90_CLOCKWISE
         )),
        ("90 CounterClockwise",
         cv2.rotate(
             image,
             cv2.ROTATE_90_COUNTERCLOCKWISE
         ))
    ]

    for rotation_name, img in rotations:

        print(f"\nChecking: {rotation_name}")

        results = reader.readtext(img)

        for detection in results:

            bbox, text, score = detection

            text = str(text)

            similarity = fuzz.ratio(
                book_name.lower(),
                text.lower()
            )

            print(
                f"Detected: {text} | "
                f"Confidence: {round(score*100,2)}% | "
                f"Similarity: {similarity}"
            )

            # Match book name
            if similarity > 60:

                print("\nBOOK FOUND!")

                top_left = tuple(
                    map(int, bbox[0])
                )

                bottom_right = tuple(
                    map(int, bbox[2])
                )

                # Draw rectangle
                cv2.rectangle(
                    img,
                    top_left,
                    bottom_right,
                    (0, 255, 0),
                    3
                )

                # Add text
                cv2.putText(
                    img,
                    f"{book_name}",
                    (
                        top_left[0],
                        top_left[1] - 10
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                output_path = "static/result.jpg"

                cv2.imwrite(
                    output_path,
                    img
                )

                confidence = int(score * 100)

                return (
                    output_path,
                    confidence
                )

    print("\nBook Not Found")

    return None