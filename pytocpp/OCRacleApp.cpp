#include "OCRacleApp.h"
#include <iostream>
#include <nfd.h>  // Native File Dialog (håndterer filvalg)

OCRacleApp::OCRacleApp(int w, int h, const std::string& title)
    : TDT4102::AnimationWindow(w, h, title) {}

// 📌 Åpner en filvelger for å velge en PDF-fil
void OCRacleApp::openFileDialog() {
    nfdchar_t* outPath = nullptr;
    nfdresult_t result = NFD_OpenDialog("pdf", nullptr, &outPath);

    if (result == NFD_OKAY) {
        selectedPDF = outPath;
        free(outPath);
        std::cout << "[INFO] Selected file: " << selectedPDF << std::endl;
    } else {
        std::cout << "[INFO] No file selected." << std::endl;
    }
}

// 📌 Kjører OCR på den valgte PDF-filen ved å kalle Python
void OCRacleApp::runOCR() {
    if (selectedPDF.empty()) {
        std::cout << "[ERROR] No PDF selected!" << std::endl;
        return;
    }

    Py_Initialize();
    PyObject* sysPath = PySys_GetObject("path");
    PyList_Append(sysPath, PyUnicode_FromString("."));

    PyObject* pModule = PyImport_ImportModule("ocrpdf");
    PyObject* pFunc = PyObject_GetAttrString(pModule, "main");

    if (pFunc && PyCallable_Check(pFunc)) {
        PyObject* pArgs = PyTuple_Pack(1, PyUnicode_FromString(selectedPDF.c_str()));
        PyObject* pResult = PyObject_CallObject(pFunc, pArgs);

        if (pResult && PyUnicode_Check(pResult)) {
            std::string ocrText = PyUnicode_AsUTF8(pResult);
            std::cout << "[INFO] OCR Result:\n" << ocrText << std::endl;
        } else {
            std::cout << "[ERROR] Failed to extract text!" << std::endl;
            PyErr_Print();
        }

        Py_XDECREF(pResult);
        Py_DECREF(pArgs);
    } else {
        std::cout << "[ERROR] Could not find 'main' function in ocrpdf.py" << std::endl;
        PyErr_Print();
    }

    Py_DECREF(pFunc);
    Py_DECREF(pModule);
    Py_Finalize();
}
