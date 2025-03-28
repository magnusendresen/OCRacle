#include "ProgressBar.h"
#include <iostream>

ProgressBar::ProgressBar(TDT4102::AnimationWindow& win)
    : progressPercent(0.0), progressDone(false), window(win) {}

void ProgressBar::init() {
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);
}

void ProgressBar::setCount(double percent) {
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);
    int filled = static_cast<int>(width * percent);
    window.draw_rectangle(Pos, filled, height, TDT4102::Color::green);
}
/*
void ProgressBar::calculateProgress() {
    std::thread([this]() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
        std::filesystem::path progressPath = scriptDir / "progress.txt";

        while (true) {
            std::ifstream progressFile(progressPath);
            std::string progressString;
            SIZE_T val = 0, max = 1, len = 0;

            if (progressFile.is_open()) {
                std::getline(progressFile, progressString);
                len = progressString.length();
                val = 0;
                for (char c : progressString) {
                    if (c >= '1' && c <= '4') {
                        val += static_cast<SIZE_T>(c - '0');
                    }
                }
                max = len * 4;
                if (max > 0) {
                    progressPercent = static_cast<double>(val) / static_cast<double>(max);
                }
            }

            if (val >= max && max > 0) {
                progressDone = true;
                break;
            }

            Sleep(1000);
        }
    }).detach();
}
*/