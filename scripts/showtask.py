#!/usr/bin/env python3

import sys
import io

# Matplotlib kan settes opp til å bruke 'Agg'-backend for å generere figurer i minne
import matplotlib
matplotlib.use('Agg')  # Ingen GUI for plot; vi genererer kun en bildefil i minnet.
import matplotlib.pyplot as plt

from PIL import Image, ImageQt
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtGui import QPixmap


def main():
    # 1) Lag en figur i matplotlib og putt inn litt LaTeX-lignende matematikk.
    # Inline-math: $E = mc^2$
    # Display-math: \displaystyle \int_0^\infty ...

    plt.figure(figsize=(6, 4))

    # Her viser vi inline-matte:
    plt.text(0.5, 0.7, r'Inline: $E = mc^2$', 
             fontsize=16, ha='center')

    # Her viser vi display-matte ved å bruke \displaystyle
    plt.text(0.5, 0.3, r'Display: $\displaystyle \int_0^\infty x^n e^{-x}\,dx = n!$', 
             fontsize=16, ha='center')

    # Fjern akser:
    plt.axis('off')

    # 2) Generer figuren i minnet
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()

    # 3) Les inn bildefilen med PIL
    image = Image.open(buf)

    # 4) Start en PyQt-applikasjon
    app = QApplication(sys.argv)

    # 5) Opprett et QLabel-objekt og sett inn bildet
    label = QLabel()
    qimage = ImageQt.ImageQt(image)
    pixmap = QPixmap.fromImage(qimage)
    label.setPixmap(pixmap)
    label.setWindowTitle("Math Popup")
    label.show()

    # 6) Kjør hendelsesløkken
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
