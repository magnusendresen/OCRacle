#pragma once
#include "AnimationWindow.h"
#include <Python.h>
#include <string>

class OCRacleApp : public TDT4102::AnimationWindow {
public:
    OCRacleApp(int w, int h, const std::string& title);
    void openFileDialog(); // Åpner en filvelger for PDF
    void runOCR();         // Kaller Python OCR-modulen

private:
    std::string selectedPDF;
};
