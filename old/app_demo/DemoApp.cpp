#include "App.h"
#include <windows.h>
#include <commdlg.h>
#include <winuser.h>
#include <synchapi.h>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <map>
#include <thread>
#include <string>
#include <chrono>
#include <cctype>

#include "widgets/TextBox.h"
#include "widgets/Button.h"


App::App(const std::string& windowName)
    : TDT4102::AnimationWindow{

        // Sentrering av vinduet på skjermen
        ((GetSystemMetrics(SM_CXSCREEN)) - (GetSystemMetrics(SM_CXSCREEN)) * 3 / 4) / 2,
        ((GetSystemMetrics(SM_CYSCREEN)) - (GetSystemMetrics(SM_CYSCREEN)) * 3 / 4) / 2,

        // Setter vindusstørrelsen til 3/4 av høyden og bredden til skjermen
        GetSystemMetrics(SM_CXSCREEN) * 3 / 4,
        GetSystemMetrics(SM_CYSCREEN) * 3 / 4,
        windowName
    }
{
    setBackgroundColor(TDT4102::Color::light_gray);
    GUI();
}




void App::GUI() {
    pdfButton = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Select File");
    googlevision = new TDT4102::TextBox({pad, pad * 6}, buttonWidth, buttonHeight, "   Google Vision");
    deepseek = new TDT4102::TextBox({pad, pad * 11}, buttonWidth, buttonHeight, "   DeepSeek");
    
    examSubject = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad}, buttonWidth*3/2, buttonHeight / 2, "Subject: ");
    examVersion = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad*3}, buttonWidth*3/2, buttonHeight/2, "Version: ");
    examAmount = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad*5}, buttonWidth*3/2, buttonHeight/2, "Tasks: ");

    ProgressBar1 = new ProgressBar(*this, App::pad*2 + static_cast<int>(App::buttonWidth), App::pad*8, "PDF processing");
    ProgressBar2 = new ProgressBar(*this, App::pad*2 + static_cast<int>(App::buttonWidth), App::pad*12, "Task processing");

    pdfButton->setLabelColor(TDT4102::Color::white);
    pdfButton->setCallback([this]() {
        pdfHandling();
    });

    timerBox = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth) + ProgressBar1->width - static_cast<int>(buttonWidth), pad}, buttonWidth, buttonHeight / 2, "Tid: ");

    add(*pdfButton);
    add(*googlevision);
    add(*deepseek);

    add(*examSubject);
    add(*examVersion);
    add(*examAmount);

    add(*timerBox);

}

void App::update() {
    ProgressBar1->setCount();
    ProgressBar2->setCount();
}

void App::startTimer() {
    startTime = std::chrono::steady_clock::now();
    timerRunning = true;

    timerThread = std::thread([this]() {
        while (timerRunning) {
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - startTime).count();

            int minutes = static_cast<int>(elapsed / 60);
            int seconds = static_cast<int>(elapsed % 60);

            if (timerBox) {
                timerBox->setText("Tid: " + std::to_string(minutes) + " min " + std::to_string(seconds) + " sek");
            }

            Sleep(1000);
        }
    });
}

void App::stopTimer() {
    timerRunning = false;
    if (timerThread.joinable()) {
        timerThread.join();
    }
}

void App::pdfHandling() {
    try {
        std::cout << "Handling PDF..." << std::endl;

        calculateProgress();

        // For å kunne skrive æøå i console
        SetConsoleOutputCP(CP_UTF8);

        // Finn path til kjørende .exe og gå én mappe opp til src/
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path buildDir = exePath.parent_path();
        std::filesystem::path sourceDir = buildDir.parent_path();  // én mappe opp

        std::filesystem::current_path(sourceDir);  // Sett working dir til src/

        std::cout << "[INFO] Kjører demo.py fra: " << sourceDir << std::endl;

        // Start demo.py i bakgrunn (minimert PowerShell)
        std::thread([]() {
            std::system("start /min powershell -Command \"python demo.py; pause\"");
        }).detach();

        startTimer();
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Exception i håndtering av PDF: " << e.what() << std::endl;
    }
}



// Map for lesing av tekstfilen
std::string ocrLine, taskLine, googlevisionLine, deepseekLine, examSubjectLine, examVersionLine, examAmountLine;
const std::map<int, std::string*> ProgressLineMap = {
    {1, &googlevisionLine},
    {2, &ocrLine},
    {3, &deepseekLine},
    {4, &taskLine},
    {5, &examSubjectLine},
    {6, &examVersionLine},
    {7, &examAmountLine}
};

void App::calculateProgress() {
    std::cout << "\n\n\n Starting progress calculation... \n\n\n" << std::endl;
    std::thread([this]() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path progressPath = exeDir.parent_path() / "progress.txt";  // ← én mappe opp!

        std::ofstream ofs(progressPath, std::ios::trunc);
        ofs.close();
        std::cout << "Cleared progress.txt at startup." << std::endl;

        FILETIME lastWriteTime = {0, 0};
        
        try {
            while (true) {
                WIN32_FILE_ATTRIBUTE_DATA fileInfo;
                if (GetFileAttributesExA(progressPath.string().c_str(), GetFileExInfoStandard, &fileInfo)) {
                    if (CompareFileTime(&fileInfo.ftLastWriteTime, &lastWriteTime) != 0) {
                        lastWriteTime = fileInfo.ftLastWriteTime;
                        std::cout << "File progress.txt has been updated." << std::endl;
            
                        std::ifstream file(progressPath);
                        if (file.is_open()) {
                            std::string line;
                            for (int i = 1; i <= static_cast<int>(ProgressLineMap.size()); i++) {
                                std::getline(file, line);
                                if (ProgressLineMap.find(i) != ProgressLineMap.end()) {
                                    *ProgressLineMap.at(i) = line;
                                }
                            }

                            // Resterende kode uendret...
                            if (!googlevisionLine.empty()) {
                                for (char c : googlevisionLine) {
                                    if (c == '1') {
                                        googlevision->setBoxColor(TDT4102::Color::green);
                                        googlevision->setTextColor(TDT4102::Color::white);
                                        break;
                                    }
                                }
                            }

                            if (!deepseekLine.empty()) {
                                for (char c : deepseekLine) {
                                    if (c == '1') {
                                        deepseek->setBoxColor(TDT4102::Color::green);
                                        deepseek->setTextColor(TDT4102::Color::white);
                                        break;
                                    }
                                }
                            }

                            if (!examSubjectLine.empty()) {
                                examSubject->setBoxColor(TDT4102::Color::green);
                                examSubject->setText("Subject: " + examSubjectLine);
                                examSubject->setTextColor(TDT4102::Color::white);
                            }

                            if (!examVersionLine.empty()) {
                                examVersion->setBoxColor(TDT4102::Color::green);
                                examVersion->setText("Version: " + examVersionLine);
                                examVersion->setTextColor(TDT4102::Color::white);
                            }

                            if (!examAmountLine.empty()) {
                                examAmount->setBoxColor(TDT4102::Color::green);
                                examAmount->setText("Tasks: " + examAmountLine);
                                examAmount->setTextColor(TDT4102::Color::white);
                            }

                            if (!ocrLine.empty()) {
                                int sum = 0;
                                int count = 0;
                                for (char c : ocrLine) {
                                    if (isdigit(c)) {
                                        sum += c - '0';
                                        count++;
                                    }
                                }
                                if (count > 0) {
                                    ProgressBar1->progress = static_cast<double>(sum) / count;
                                }
                                std::cout << "OCR Progress: " << ProgressBar1->progress << std::endl;
                            }

                            if (ProgressBar1->progress >= 1.0 && !taskLine.empty()) {
                                int sum = 0;
                                int count = 0;
                                for (char c : taskLine) {
                                    if (isdigit(c)) {
                                        sum += c - '0';
                                        count++;
                                    }
                                }
                                count *= 5;
                                if (count > 0) {
                                    ProgressBar2->progress = static_cast<double>(sum) / count;
                                }
                                std::cout << "Task Progress: " << ProgressBar2->progress << std::endl;
                            }

                            if (ProgressBar2->progress >= 1.0) {
                                stopTimer();
                            }
                        }
                    }
                    Sleep(200);
                } else {
                    std::cerr << "Failed to access progress.txt. Retrying..." << std::endl;
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] Exception oppstod i lesing av progress.txt: " << e.what() << std::endl;
        }
    }).detach();
}



