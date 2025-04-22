import cv2
import numpy as np

# Filstier
BIG_IMAGE = 'big_image.png'
TEMPLATE  = 'small_image.png'

# Les inn bilder (kan ha alfa)
big = cv2.imread(BIG_IMAGE, cv2.IMREAD_UNCHANGED)
tpl = cv2.imread(TEMPLATE, cv2.IMREAD_UNCHANGED)

# Klargjør RGB (dropp alfa)
def to_rgb(img):
    return img[..., :3] if img.shape[2] == 4 else img.copy()

big_rgb = to_rgb(big)
tpl_rgb = to_rgb(tpl)

# Lag maske på malen: ekskluder kun rent svart/hvitt
mask_full = np.logical_and(
    np.any(tpl_rgb != [0,0,0], axis=2),
    np.any(tpl_rgb != [255,255,255], axis=2)
).astype(np.uint8) * 255

# Multiskala matching: skaler template fra 50% til 150%
best_val = float('inf')
best_loc = None
best_scale = 1.0
method = cv2.TM_SQDIFF_NORMED

for scale in np.linspace(0.5, 1.5, 21):  # 21 steg
    h0, w0 = tpl_rgb.shape[:2]
    new_size = (int(w0*scale), int(h0*scale))
    if new_size[0] < 1 or new_size[1] < 1:
        continue
    tpl_s = cv2.resize(tpl_rgb, new_size, interpolation=cv2.INTER_AREA)
    mask_s = cv2.resize(mask_full, new_size, interpolation=cv2.INTER_NEAREST)

    if tpl_s.shape[0] > big_rgb.shape[0] or tpl_s.shape[1] > big_rgb.shape[1]:
        continue

    res = cv2.matchTemplate(big_rgb, tpl_s, method, mask=mask_s)
    min_val, _, min_loc, _ = cv2.minMaxLoc(res)

    if min_val < best_val:
        best_val = min_val
        best_loc = min_loc
        best_scale = scale

if best_loc is None:
    print("Fant ingen match innen skala-intervallet.")
else:
    x, y = best_loc
    w_t = int(tpl_rgb.shape[1] * best_scale)
    h_t = int(tpl_rgb.shape[0] * best_scale)
    print(f"Beste match ved skala {best_scale:.2f}, topp-venstre = {(x, y)}")

    # Tegn rektangel rundt funnet for verifisering
    out = big_rgb.copy()
    cv2.rectangle(out, (x, y), (x + w_t, y + h_t), (0,255,0), 2)
    cv2.imwrite('matched_scaled.png', out)
    print("Resultat lagret som 'matched_scaled.png'.")

    # Beskjær det funne området fra originalbildet og lagre som eget bilde
    cropped = big_rgb[y:y + h_t, x:x + w_t]
    cv2.imwrite('cropped_match.png', cropped)
    print("Uttak av funnet område lagret som 'cropped_match.png'.")