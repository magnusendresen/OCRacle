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
#include "widgets/TextInput.h"


constexpr int WINDOW_WIDTH  = 1280;
constexpr int WINDOW_HEIGHT = 720;

App::App(const std::string& windowName)
    : TDT4102::AnimationWindow{
        // Beregn senterposisjon
        640,
        360,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
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


    examSubject = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad}, buttonWidth, buttonHeight / 2, "Subject: ");
    examSubjectInput = new TDT4102::TextInput({2*pad + static_cast<int>(buttonWidth), pad}, buttonWidth, buttonHeight / 2, "Subject: ");

    // ignoredTopics = new TDT4102::TextInput({2*pad + static_cast<int>(buttonWidth), pad*3}, buttonWidth*4, buttonHeight / 2, "Ignored topics: ");
    
    examVersion = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad*5}, buttonWidth, buttonHeight/2, "Version: ");

    examAmount = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad*7}, buttonWidth*4, buttonHeight/2, "Tasks: ");


    ProgressBar1 = new ProgressBar(*this, App::pad*2 + static_cast<int>(App::buttonWidth), App::pad*10, "PDF processing");
    ProgressBar2 = new ProgressBar(*this, App::pad*2 + static_cast<int>(App::buttonWidth), App::pad*18, "Task processing");
    ProgressBar3 = new ProgressBar(*this, App::pad*2 + static_cast<int>(App::buttonWidth), App::pad*14, "Image extraction");

    ntnuLogo = new TDT4102::Image("ntnu_logo.png");
    ntnuLogoScale = new int(8);

    pdfButton->setLabelColor(TDT4102::Color::white);
    pdfButton->setCallback([this]() {
        pdfHandling();
    });

    timerBox = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth) + ProgressBar1->width - static_cast<int>(buttonWidth), pad}, buttonWidth, buttonHeight / 2, "Tid: ");

    add(*pdfButton);
    add(*googlevision);
    add(*deepseek);

    add(*examSubjectInput);
    add(*examVersion);
    add(*examAmount);

    // add(*ignoredTopics);

    add(*timerBox);

}

void App::update() {
    ProgressBar1->setCount();
    ProgressBar2->setCount();
    ProgressBar3->setCount();
    this->draw_image({WINDOW_WIDTH - ntnuLogo->width/ *ntnuLogoScale - pad, pad}, *ntnuLogo, ntnuLogo->width/ *ntnuLogoScale, ntnuLogo->height/ *ntnuLogoScale);
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

        // Finn script-mappen
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path rootDir = exeDir.parent_path().parent_path();
        std::filesystem::path dataDir = rootDir / "icp_data";
        std::filesystem::path scriptDir = rootDir / "scripts";

        std::filesystem::create_directories(dataDir);

        std::ofstream subjectFile(dataDir / "subject.txt", std::ios::binary);
        std::string userinp1;
        if (examSubjectInput->getText() != "Subject: ") {
            userinp1 = examSubjectInput->getText().substr(9);
            std::cout << "User input subject: " << userinp1 << std::endl;
        } else {
            add(*examSubject);
            userinp1 = "";
            examSubjectInput->setVisible(0);
        }
        // std::ofstream ignoredFile(scriptDir / "ignored.txt", std::ios::binary);
        // std::string userinp2;
        // if (ignoredTopics->getText() != "Ignored topics: ") {
        //     userinp2 = ignoredTopics->getText().substr(16);
        //     std::cout << "User input ignored topics: " << userinp2 << std::endl;
        // } else {
        //     userinp2 = "";
        // }

        subjectFile << userinp1;
        // ignoredFile << userinp2;

        // For å kunne skrive æøå i console
        SetConsoleOutputCP(CP_UTF8);    

        // Popup for å velge PDF
        wchar_t filePath[MAX_PATH] = L"";
        OPENFILENAMEW ofn = {};
        ofn.lStructSize = sizeof(ofn);
        ofn.lpstrFile = filePath;
        ofn.nMaxFile = MAX_PATH;
        ofn.lpstrFilter = L"PDF Files\0*.pdf\0";

        if (!GetOpenFileNameW(&ofn)) {
            std::wcout << L"Ingen fil ble valgt." << std::endl;
            return;
        }

        // Konverter til UTF-8
        int utf8_len = WideCharToMultiByte(CP_UTF8, 0, filePath, -1, nullptr, 0, nullptr, nullptr);
        std::string selectedFile(static_cast<size_t>(utf8_len), '\0');
        WideCharToMultiByte(CP_UTF8, 0, filePath, -1, &selectedFile[0], utf8_len, nullptr, nullptr);
        if (!selectedFile.empty() && selectedFile.back() == '\0') {
            selectedFile.pop_back();
        }

        std::cout << "[INFO] Valgt fil: " << selectedFile << std::endl;

        std::filesystem::current_path(scriptDir);

        std::cout << "[INFO] scriptDir: " << scriptDir << std::endl;

        std::ofstream dirFile(dataDir / "dir.txt", std::ios::binary);
        dirFile << selectedFile;

        // Start Python-script i en bakgrunnstråd
        std::thread([]() {
            std::system("start /min powershell -Command \"python main.py; pause\"");
                 }).detach();
        startTimer();
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Exception i håndtering av PDF: " << e.what() << std::endl;
    }
}

// Map for lesing av tekstfilen
std::string ocrLine, taskLine, googlevisionLine, deepseekLine, examSubjectLine, examVersionLine, examAmountLine, imageExtractionLine;
const std::map<int, std::string*> ProgressLineMap = {
    {1, &googlevisionLine},
    {2, &ocrLine},
    {3, &deepseekLine},
    {4, &taskLine},
    {5, &examSubjectLine},
    {6, &examVersionLine},
    {7, &examAmountLine},
    {8, &imageExtractionLine}
};

void App::calculateProgress() {
    std::cout << "\n\n\n Starting progress calculation... \n\n\n" << std::endl;
    std::thread([this]() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path rootDir = exeDir.parent_path().parent_path();
        std::filesystem::path scriptDir = rootDir / "scripts";
        std::filesystem::path dataDir = rootDir / "icp_data";
        std::filesystem::create_directories(dataDir);
        std::filesystem::path progressPath = dataDir / "progress.txt";

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
                            
                            // Iterering over hver linje av fila knytta opp mot map-et med pekere
                            for (int i = 1; i <= static_cast<int>(ProgressLineMap.size()); i++) {
                                std::getline(file, line);
                                if (ProgressLineMap.find(i) != ProgressLineMap.end()) {
                                    *ProgressLineMap.at(i) = line;
                                }
                            }

                            // Oppdatering av Google Vision knapp
                            if (!googlevisionLine.empty()) {
                                for (char c : googlevisionLine) {
                                    if (c == '1') {
                                        googlevision->setBoxColor(TDT4102::Color::green);
                                        googlevision->setTextColor(TDT4102::Color::white);
                                        break;
                                    }
                                }
                            }

                            // Oppdatering av DeepSeek knapp
                            if (!deepseekLine.empty()) {
                                for (char c : deepseekLine) {
                                    if (c == '1') {
                                        deepseek->setBoxColor(TDT4102::Color::green);
                                        deepseek->setTextColor(TDT4102::Color::white);

                                        break;
                                    }
                                }
                            }

                            // Oppdatering av emnebeholder
                            if (!examSubjectLine.empty()) {
                                examSubject->setBoxColor(TDT4102::Color::green);
                                examSubject->setText("Subject: "+examSubjectLine);
                                examSubject->setTextColor(TDT4102::Color::white);
                            }

                            // Oppdatering av utgivelsebeholder
                            if (!examVersionLine.empty()) {
                                examVersion->setBoxColor(TDT4102::Color::green);
                                examVersion->setText("Version: "+examVersionLine);
                                examVersion->setTextColor(TDT4102::Color::white);

                            }

                            // Oppdatering av antallbeholder
                            if (!examAmountLine.empty()) {
                                examAmount->setBoxColor(TDT4102::Color::green);
                                examAmount->setText("Tasks: "+examAmountLine);
                                examAmount->setTextColor(TDT4102::Color::white);

                            }
            
                            // Beregn OCR-progresjonen til progressbar
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

                            // Beregn bildeuthenting-progresjon til progressbar
                            if (!imageExtractionLine.empty()) {
                                int sum = 0;
                                int count = 0;
                                for (char c : imageExtractionLine) {
                                    if (isdigit(c)) {
                                        sum += c - '0';
                                        count++;
                                    }
                                }
                                if (count > 0) {
                                    ProgressBar3->progress = static_cast<double>(sum) / count;
                                }
                                std::cout << "Image Extraction Progress: " << ProgressBar3->progress << std::endl;
                            }

                            // Beregn AI-behandling-progresjon til progressbar
                            if (ProgressBar1->progress >= 1.0 && !taskLine.empty()) {
                                int sum = 0;
                                int count = 0;
                                for (char c : taskLine) {
                                    if (isdigit(c)) {
                                        sum += c - '0';
                                        count++;
                                    }
                                }
                                count *= 8;
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
            std::cerr << "[ERROR] Exception oppstod i lesing av progress.txt" << e.what() << std::endl;
        }
    }).detach();
}


