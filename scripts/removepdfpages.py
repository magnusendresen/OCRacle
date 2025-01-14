from PyPDF2 import PdfWriter, PdfReader
import os
import fitz  # For handling PDF files
import tkinter as tk
from tkinter import filedialog, simpledialog

def removepdfpages(inputfile, outputfile, first_removed_page):
    inputpdf = PdfReader(open(inputfile, "rb"))
    output = PdfWriter()
    for i in range(len(inputpdf.pages)):
        if i < first_removed_page:
            output.add_page(inputpdf.pages[i])
    with open(outputfile, "wb") as outputStream:
        output.write(outputStream)

def selectpdfpopup():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    return pdf_path

def get_first_removed_page():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    first_removed_page = simpledialog.askinteger("Input", "First removed page (numeric input):")
    return first_removed_page

pdf_path = selectpdfpopup()
first_removed_page = get_first_removed_page()
output_path = os.path.splitext(pdf_path)[0] + "_modified.pdf"
removepdfpages(pdf_path, output_path, first_removed_page)