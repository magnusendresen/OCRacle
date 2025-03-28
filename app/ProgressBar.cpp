#include "ProgressBar.h"
#include <iostream>
#include <thread>
#include <windows.h>

ProgressBar::ProgressBar(TDT4102::AnimationWindow& win)
    : progressPercent(0.0), progressDone(false), window(win) {}

void ProgressBar::init() {
    // Grå bakgrunn for hele baren (startverdi)
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);
}

void ProgressBar::setCount(double percent) {
    // Tegn bakgrunn først (grå stripe)
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);

    // Tegn grønn del basert på 'percent'
    int filled = static_cast<int>(width * percent);
    window.draw_rectangle(Pos, filled, height, TDT4102::Color::green);
}

void ProgressBar::calculateProgress() {
    // Start en bakgrunnstråd
    std::thread([this]() {
        // Finn path til progress.txt i scripts-mappen
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
        std::filesystem::path progressPath = scriptDir / "progress.txt";

        while (true) {
            // Les 1 tegn fra progress.txt (f.eks. '0' .. '9')
            std::ifstream progressFile(progressPath);
            if (progressFile.is_open()) {
                char levelChar = '0';
                progressFile.get(levelChar);
                if (levelChar >= '0' && levelChar <= '9') {
                    int level = levelChar - '0';  // 0..9
                    progressPercent = level / 9.0; // 0.0..1.0
                }
            }

            // Hvis vi nådde 1.0 => 100%
            if (progressPercent >= 1.0) {
                progressDone = true;
                break;
            }
            // Sov litt før neste sjekk
            Sleep(200);
        }
    }).detach();
}
