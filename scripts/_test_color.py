import numpy as np
import cv2
from tkinter import Tk, filedialog

def is_clearly_different(c1, c2, gap):
    return np.linalg.norm(c1 - c2) >= gap

def main():
    root = Tk()
    root.withdraw()
    img_path = filedialog.askopenfilename(title="Select PNG Image", filetypes=[("PNG files", "*.png")])
    if not img_path:
        print("No file selected.")
        return

    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    color_gap = 50

    max_pixels_x = 100  # max horizontal samples
    max_pixels_y = 100  # max vertical samples

    h, w = img.shape[:2]
    step_x = max(1, w // max_pixels_x)
    step_y = max(1, h // max_pixels_y)

    sampled_colors = []
    for y in range(0, h, step_y):
        for x in range(0, w, step_x):
            sampled_colors.append(img[y, x])

    sampled_colors = np.array(sampled_colors)
    unique_colors = np.unique(sampled_colors, axis=0)

    filtered = []
    for color in unique_colors:
        if all(is_clearly_different(color, c, color_gap) for c in filtered):
            filtered.append(color)

    print(len(filtered))

if __name__ == "__main__":
    main()
