import cv2
import numpy as np


def locate_book(cover_path, shelf_path):

    cover = cv2.imread(cover_path)
    shelf = cv2.imread(shelf_path)

    if cover is None or shelf is None:
        return None

    gray_cover = cv2.cvtColor(
        cover,
        cv2.COLOR_BGR2GRAY
    )

    gray_shelf = cv2.cvtColor(
        shelf,
        cv2.COLOR_BGR2GRAY
    )

    # More features for better matching
    orb = cv2.ORB_create(5000)

    kp1, des1 = orb.detectAndCompute(
        gray_cover,
        None
    )

    kp2, des2 = orb.detectAndCompute(
        gray_shelf,
        None
    )

    if des1 is None or des2 is None:
        return None

    bf = cv2.BFMatcher(
        cv2.NORM_HAMMING
    )

    matches = bf.knnMatch(
        des1,
        des2,
        k=2
    )

    good_matches = []

    for m, n in matches:

        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    # Calculate confidence AFTER matching
    total_matches = len(matches)

    confidence = int(
      (len(good_matches) / total_matches) * 100
    )

    confidence = min(confidence, 99)
    # Minimum matches required
    if len(good_matches) < 20:
        return None

    src_pts = np.float32(
        [kp1[m.queryIdx].pt for m in good_matches]
    ).reshape(-1, 1, 2)

    dst_pts = np.float32(
        [kp2[m.trainIdx].pt for m in good_matches]
    ).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(
        src_pts,
        dst_pts,
        cv2.RANSAC,
        5.0
    )

    if H is None:
        return None

    h, w = cover.shape[:2]

    pts = np.float32([
        [0, 0],
        [0, h - 1],
        [w - 1, h - 1],
        [w - 1, 0]
    ]).reshape(-1, 1, 2)

    dst = cv2.perspectiveTransform(
        pts,
        H
    )

    result = shelf.copy()

    # Draw green polygon around detected book
    x, y, w, h = cv2.boundingRect(
    np.int32(dst)
    )

    cv2.rectangle(
    result,
    (x, y),
    (x + w, y + h),
    (0, 255, 0),
    4
    )

    cv2.putText(
    result,
    f"Let Us C ({confidence}%)",
    (x, y - 10),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.8,
    (0, 255, 0),
    2
    )

    # Draw confidence text
    cv2.putText(
        result,
        f"Confidence: {confidence}%",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    output_path = "static/result.jpg"

    cv2.imwrite(
        output_path,
        result
    )

    return output_path, confidence