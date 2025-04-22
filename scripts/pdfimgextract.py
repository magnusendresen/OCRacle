#!/usr/bin/env python3
import os
import shutil
import fitz  # PyMuPDF
import cv2
import numpy as np

def extract_images_from_pdf(pdf_path,
                            output_folder,
                            black_threshold=0.4,
                            dark_tol=10,
                            white_tol=245,
                            zoom_x=2.0,
                            zoom_y=2.0,
                            scale_min=0.4,
                            scale_max=4.0,
                            scale_steps=50,
                            max_pad_px=20):
    """
    Ekstraherer alle bilder fra PDF-en og lagrer dem i output_folder.
    - Render siden med oppløsnings‑faktor zoom_x, zoom_y for høyere DPI.
    - For hvert bilde med >= black_threshold andel mørke piksler (< dark_tol),
      gjør multiskala-template-matching i [scale_min, scale_max] over scale_steps.
    - Når beste match er funnet, beskjæres området og utvides med pad_px piksler,
      der pad_px = int(best_val * max_pad_px), altså 0…max_pad_px uavhengig av oppløsning.
    - output-filer navngis som:
        page-<n>_img-<i>_matched_s<s>_pad<p>px.png
    """
    doc = fitz.open(pdf_path)

    # (Re)lag output-folder
    if os.path.exists(output_folder):
        for fn in os.listdir(output_folder):
            fp = os.path.join(output_folder, fn)
            try:
                if os.path.isfile(fp) or os.path.islink(fp):
                    os.remove(fp)
                else:
                    shutil.rmtree(fp)
            except Exception as e:
                print(f"Kunne ikke slette {fp}: {e}")
    else:
        os.makedirs(output_folder, exist_ok=True)

    img_count = 0
    scales = np.linspace(scale_min, scale_max, scale_steps)
    mat = fitz.Matrix(zoom_x, zoom_y)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # Render siden med økt oppløsning
        pix = page.get_pixmap(matrix=mat)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = (cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR) if pix.alpha
                    else cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))

        for img_i, img_info in enumerate(page.get_images(full=True), start=1):
            xref = img_info[0]
            base = doc.extract_image(xref)
            img_bytes = base["image"]
            ext = base["ext"]

            # Lagre råbilde
            raw_name = f"page-{page_idx+1}_img-{img_i}.{ext}"
            raw_path = os.path.join(output_folder, raw_name)
            with open(raw_path, "wb") as f:
                f.write(img_bytes)
            img_count += 1
            print(f"Lagret rå bilde: {raw_name}")

            # Decode + til BGR
            tpl = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
            if tpl is None:
                continue
            tpl_bgr = (cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR) if tpl.ndim == 2
                       else tpl[..., :3] if tpl.shape[2] == 4
                       else tpl)

            # Mørke‐andel
            gray_tpl = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
            if (gray_tpl < dark_tol).mean() < black_threshold:
                continue

            # Bygg maske for matching
            mask = ((gray_tpl > dark_tol) & (gray_tpl < white_tol)).astype(np.uint8) * 255

            # Multiskala matching
            results = []
            h0, w0 = gray_tpl.shape
            for scale in scales:
                nw, nh = int(w0 * scale), int(h0 * scale)
                if nw < 1 or nh < 1 or nw > page_bgr.shape[1] or nh > page_bgr.shape[0]:
                    continue
                tpl_s  = cv2.resize(tpl_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
                mask_s = cv2.resize(mask,    (nw, nh), interpolation=cv2.INTER_NEAREST)
                res = cv2.matchTemplate(page_bgr, tpl_s, cv2.TM_SQDIFF_NORMED, mask=mask_s)
                mn, _, mn_loc, _ = cv2.minMaxLoc(res)
                results.append((scale, mn, mn_loc))

            if not results:
                print(f"Ingen gyldige skalatrinn for side {page_idx+1}, bilde {img_i}")
                continue

            # Velg beste match
            best_scale, best_val, (x, y) = min(results, key=lambda x: x[1])
            w_t, h_t = int(w0 * best_scale), int(h0 * best_scale)

            # Dynamisk padding i piksler uavhengig av oppløsning
            pad_px = int(best_val * max_pad_px)
            pad_px = min(pad_px, max_pad_px)

            # Klipp innenfor grenser
            x0 = max(0, x - pad_px)
            y0 = max(0, y - pad_px)
            x1 = min(page_bgr.shape[1], x + w_t + pad_px)
            y1 = min(page_bgr.shape[0], y + h_t + pad_px)

            crop = page_bgr[y0:y1, x0:x1]
            out_name = (f"page-{page_idx+1}_img-{img_i}"
                        f"_matched_s{best_scale:.2f}"
                        f"_pad{pad_px}px.png")
            out_path = os.path.join(output_folder, out_name)
            cv2.imwrite(out_path, crop)
            print(f"Lagret beskjært match: {out_name} "
                  f"(scale={best_scale:.2f}, pad={pad_px}px, val={best_val:.4f})")

    print(f"Total antall bilder lagret: {img_count}")


if __name__ == "__main__":
    pdf_path = "MEKT1101H24.pdf"
    output_folder = "MEKT1101H24_images"
    # zoom_x=2.0, zoom_y=2.0 gir dobbel DPI; juster scale_min/max if nødvendig
    extract_images_from_pdf(pdf_path, output_folder,
                            zoom_x=2.0,
                            zoom_y=2.0,
                            scale_min=0.4,   # tilsvarer 0.2*2.0
                            scale_max=2.0,   # tilsvarer 2.0*2.0
                            scale_steps=50,
                            max_pad_px=20)
