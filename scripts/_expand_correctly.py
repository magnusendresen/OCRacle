import cv2
import numpy as np
import matplotlib.pyplot as plt
from tkinter import filedialog, Tk, messagebox

# --- Konstanter ---
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
IOU_THRESHOLD = 0.3
EXPAND_MARGIN = 100

# --- Funksjoner ---
def velg_bilde():
    root = Tk()
    root.withdraw()
    filsti = filedialog.askopenfilename()
    bilde = cv2.imread(filsti)
    if bilde is None:
        messagebox.showerror("Feil", "Kunne ikke laste bildet.")
        exit(1)
    return bilde

def finn_crop_omrader(bilde):
    grattone = cv2.cvtColor(bilde, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(grattone, (5, 5), 0)
    kanter = cv2.Canny(blur, 50, 150)
    utvidet = cv2.dilate(kanter, np.ones((5, 5), np.uint8), iterations=2)
    konturer, _ = cv2.findContours(utvidet, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bokser = []
    for c in konturer:
        x, y, w, h = cv2.boundingRect(c)
        if w * h >= MIN_CONTOUR_AREA and h >= MIN_CONTOUR_HEIGHT:
            bokser.append((x, y, w, h))
    return filtrer_bokser(bokser)

def iou(b1, b2):
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    xa, ya = max(x1, x2), max(y1, y2)
    xb, yb = min(x1+w1, x2+w2), min(y1+h1, y2+h2)
    inter = max(0, xb - xa) * max(0, yb - ya)
    union = w1*h1 + w2*h2 - inter
    return inter / union if union > 0 else 0

def filtrer_bokser(bokser):
    bokser.sort(key=lambda b: b[2] * b[3], reverse=True)
    filtrert = []
    for b in bokser:
        hvis_overlapping = any(iou(b, f) > IOU_THRESHOLD for f in filtrert)
        if not hvis_overlapping:
            filtrert.append(b)
    return filtrert

def utvid_boks(boks, bilde_shape, margin):
    x, y, w, h = boks
    h_bilde, w_bilde = bilde_shape[:2]
    x2 = max(0, x - margin)
    y2 = max(0, y - margin)
    x3 = min(w_bilde, x + w + margin)
    y3 = min(h_bilde, y + h + margin)
    return (x2, y2, x3 - x2, y3 - y2)

def kontrastverdi(region):
    reshaped = region.reshape(-1, 3)
    unik = np.unique(reshaped, axis=0)
    return 0 if len(unik) <= 1 else len(unik)

def gjennomsnittlig_fargeverdi(region):
    return np.mean(region.reshape(-1, 3), axis=0).mean()

def beregn_kantkontraster_og_farger(bilde, boks, maks_avstand):
    x, y, w, h = boks
    topp, bunn, venstre, hoyre = [], [], [], []
    farger_topp, farger_bunn, farger_venstre, farger_hoyre = [], [], [], []
    for i in range(maks_avstand):
        if y - i - 1 >= 0:
            stripe = bilde[y - i - 1, x:x+w]
            topp.append(kontrastverdi(stripe))
            farger_topp.append(gjennomsnittlig_fargeverdi(stripe))
        if y + h + i < bilde.shape[0]:
            stripe = bilde[y + h + i, x:x+w]
            bunn.append(kontrastverdi(stripe))
            farger_bunn.append(gjennomsnittlig_fargeverdi(stripe))
        if x - i - 1 >= 0:
            stripe = bilde[y:y+h, x - i - 1]
            venstre.append(kontrastverdi(stripe))
            farger_venstre.append(gjennomsnittlig_fargeverdi(stripe))
        if x + w + i < bilde.shape[1]:
            stripe = bilde[y:y+h, x + w + i]
            hoyre.append(kontrastverdi(stripe))
            farger_hoyre.append(gjennomsnittlig_fargeverdi(stripe))
    return topp, bunn, venstre, hoyre, farger_topp, farger_bunn, farger_venstre, farger_hoyre

def tegn_bokser_og_vis(bilde, boks1, boks2):
    visning = bilde.copy()
    cv2.rectangle(visning, (boks1[0], boks1[1]), (boks1[0]+boks1[2], boks1[1]+boks1[3]), (255, 0, 0), 2)
    cv2.rectangle(visning, (boks2[0], boks2[1]), (boks2[0]+boks2[2], boks2[1]+boks2[3]), (0, 255, 0), 2)
    visning_rgb = cv2.cvtColor(visning, cv2.COLOR_BGR2RGB)
    plt.figure(figsize=(24, 6))
    plt.subplot(1, 4, 1)
    plt.imshow(visning_rgb)
    plt.title("Bilde med bokser")
    plt.axis("off")

def plott_kontraster_og_farge(topp, bunn, venstre, hoyre, farger_topp, farger_bunn, farger_venstre, farger_hoyre):
    plt.subplot(1, 4, 2)
    plt.plot(topp, label="Topp")
    plt.plot(bunn, label="Bunn")
    plt.plot(venstre, label="Venstre")
    plt.plot(hoyre, label="Høyre")
    plt.title("Kontrastprofiler rundt boksen")
    plt.xlabel("Avstand fra boks")
    plt.ylabel("Kontrastverdi")
    plt.legend()
    plt.grid(True)

    plt.subplot(1, 4, 3)
    plt.plot(farger_topp, label="Topp")
    plt.plot(farger_bunn, label="Bunn")
    plt.plot(farger_venstre, label="Venstre")
    plt.plot(farger_hoyre, label="Høyre")
    plt.title("Gjennomsnittlig fargeverdi")
    plt.xlabel("Avstand fra boks")
    plt.ylabel("Verdi (0-255)")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

# --- Hovedprogram ---
bilde = velg_bilde()
bokser = finn_crop_omrader(bilde)
if not bokser:
    print("Fant ingen relevante områder.")
    exit(0)

boks = bokser[0]
utvidet_boks = utvid_boks(boks, bilde.shape, EXPAND_MARGIN)
topp, bunn, venstre, hoyre, farger_topp, farger_bunn, farger_venstre, farger_hoyre = beregn_kantkontraster_og_farger(bilde, boks, maks_avstand=EXPAND_MARGIN)
tegn_bokser_og_vis(bilde, boks, utvidet_boks)
plott_kontraster_og_farge(topp, bunn, venstre, hoyre, farger_topp, farger_bunn, farger_venstre, farger_hoyre)
input("Trykk Enter for å lukke...")
