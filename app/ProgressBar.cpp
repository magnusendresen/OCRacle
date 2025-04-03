#include "ProgressBar.h"
#include <iostream>
#include <thread>

ProgressBar::ProgressBar(TDT4102::AnimationWindow& win)
    : window(win) {}

void ProgressBar::setCount(double percent) {
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);
    int filled = static_cast<int>(width * percent);
    window.draw_rectangle(Pos, filled, height, TDT4102::Color::green);
}

void ProgressBar::calculateProgress() {
    std::cout << "\n\n\n Starting progress calculation... \n\n\n" << std::endl;

    std::thread([]() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
        std::filesystem::path progressPath = scriptDir / "progress.txt";

        FILETIME lastWriteTime = {0, 0};

        while (true) {
            WIN32_FILE_ATTRIBUTE_DATA fileInfo;
            if (GetFileAttributesExA(progressPath.string().c_str(), GetFileExInfoStandard, &fileInfo)) {
                if (CompareFileTime(&fileInfo.ftLastWriteTime, &lastWriteTime) != 0) {
                    lastWriteTime = fileInfo.ftLastWriteTime;
                    std::cout << "File progress.txt has been updated." << std::endl;

                    std::ifstream file(progressPath);
                    if (file.is_open()) {
                        std::string line;
                        while (std::getline(file, line)) {
                            int fileSum = 0;
                            std::size_t fileLen = line.length() * 4;
                            for (char& c : line) {
                                if (isdigit(c)) {
                                    fileSum += c - '0';
                                }
                            }
                            progress = static_cast<double>(fileSum) / static_cast<double>(fileLen);
                        }
                    }
                    std::cout << "Progress: " << progress << std::endl;
                }
                Sleep(200);
            } else {
                std::cerr << "Failed to access progress.txt. Retrying..." << std::endl;
            }
        }
    }).detach();
}
