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
    colors = img.reshape(-1, img.shape[2])
    unique_colors = np.unique(colors, axis=0)

    filtered = []
    for color in unique_colors:
        if all(is_clearly_different(color, c, color_gap) for c in filtered):
            filtered.append(color)

    print(len(filtered))

if __name__ == "__main__":
    main()
