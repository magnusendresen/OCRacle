#include "App.h"
#include "ProgressBar.h"
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
#include <regex>

#include "subprojects/animationwindow/include/Widget.h"
#include "widgets/TextBox.h"
#include "widgets/Button.h"
#include "widgets/TextInput.h"


constexpr int WINDOW_WIDTH  = 1280;
constexpr int WINDOW_HEIGHT = 720;

App::App(const std::string& windowName)
    : TDT4102::AnimationWindow{
        // Beregn senterposisjon
        100,
        100,
        WINDOW_WIDTH + 400,
        WINDOW_HEIGHT,
        windowName
    }
{
    setBackgroundColor(TDT4102::Color::light_gray);
    GUI();
}

void App::GUI() {
    startWidget = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Start Processing");
    startButton = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Start Processing");
    
    startButton->setButtonColor(TDT4102::Color::dark_seagreen);
    GoogleVisionIndicator = new TDT4102::Button({pad, pad * 6}, buttonWidth, buttonHeight, "Google Vision");
    DeepSeekIndicator = new TDT4102::Button({pad, pad * 11}, buttonWidth, buttonHeight, "DeepSeek");
    
    examUpload = new TDT4102::Button({pad * 2 + static_cast<int>(buttonWidth), pad}, buttonWidth, buttonHeight / 2, "Upload Exam");
    solutionUpload = new TDT4102::Button({pad * 3 + static_cast<int>(buttonWidth) * 2, pad}, buttonWidth, buttonHeight / 2, "Upload Solution");
    formulaSheetUpload = new TDT4102::Button({pad * 4 + static_cast<int>(buttonWidth) * 3, pad}, buttonWidth, buttonHeight / 2, "Upload Formula Sheet");
    
    selectedExam = new TDT4102::TextBox({pad * 2 + static_cast<int>(buttonWidth), pad + buttonHeight / 4 + 2}, buttonWidth, buttonHeight / 2, "No file selected.");
    selectedSolution = new TDT4102::TextBox({pad * 3 + static_cast<int>(buttonWidth) * 2, pad + buttonHeight / 4 + 2}, buttonWidth, buttonHeight / 2, "No file selected.");
    selectedFormulaSheet = new TDT4102::TextBox({pad * 4 + static_cast<int>(buttonWidth) * 3, pad + buttonHeight / 4 + 2}, buttonWidth, buttonHeight / 2, "No file selected.");
    
    for (auto* box : {selectedExam, selectedSolution, selectedFormulaSheet}) {
        // Set box color
        box->setBoxColor(TDT4102::Color::transparent);
        // Set border color
        box->setBorderColor(TDT4102::Color::transparent);
        // Set text color
        box->setTextColor(TDT4102::Color{0x323232});
        // Set size
        // box->setFontSize(20);
    }

    ignoredTopics = new TDT4102::TextInput({pad * 2 + static_cast<int>(buttonWidth), pad * 6}, pad * 2 + buttonWidth * 3, buttonHeight / 2, "Ignored topics: ");

    examSubject = new TDT4102::TextBox({2*pad + static_cast<int>(buttonWidth), pad * 11}, buttonWidth, buttonHeight / 2, "Subject: ");
    examSubjectInput = new TDT4102::TextInput({2*pad + static_cast<int>(buttonWidth), pad * 11}, buttonWidth, buttonHeight / 2, "Subject: ");

    examVersion = new TDT4102::TextBox({pad * 3 + static_cast<int>(buttonWidth) * 2, pad * 11}, buttonWidth, buttonHeight/2, "Version: ");


    examAmount = new TDT4102::TextBox({pad * 4 + static_cast<int>(buttonWidth) * 3, pad*11}, buttonWidth, buttonHeight/2, "Tasks: ");



    ProgressBarLLM = new ProgressBar(*this, App::pad + 4, App::pad*16, "LLM processing");

    ntnuLogo = new TDT4102::Image("ntnu_logo.png");
    ntnuLogoScale = new int(10);

    startButton->setLabelColor(TDT4102::Color::white);
    startButton->setCallback([this]() {
        startProcessing();
    });

    examUpload->setCallback([this]() {
        pdfHandling(selectedExam);
    });
    solutionUpload->setCallback([this]() {
        pdfHandling(selectedSolution);
    });
    formulaSheetUpload->setCallback([this]() {
        pdfHandling(selectedFormulaSheet);
    });

    timerBox = new TDT4102::TextBox({pad * 5 + static_cast<int>(buttonWidth) * 4, pad}, buttonWidth, buttonHeight / 2, "Tid: ");

    add(*startWidget);
    add(*startButton);
    startButton->setVisible(false);


    add(*GoogleVisionIndicator);
    add(*DeepSeekIndicator);

    add(*examUpload);
    add(*solutionUpload);
    add(*formulaSheetUpload);

    add(*selectedExam);
    add(*selectedSolution);
    add(*selectedFormulaSheet);

    add(*examSubjectInput);
    add(*examVersion);
    add(*examAmount);

    add(*ignoredTopics);

    add(*timerBox);

}

void App::update() {
    ProgressBarLLM->setCount();
    this->draw_image({pad * 5 + static_cast<int>(buttonWidth) * 4 + 6, pad * 2 + static_cast<int>(buttonHeight) / 3}, *ntnuLogo, ntnuLogo->width/ *ntnuLogoScale, ntnuLogo->height/ *ntnuLogoScale);
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

void App::pdfHandling(TDT4102::TextBox* chosenFile) {
    try {
        if (chosenFile == selectedExam) {
            startWidget->setVisible(false);
            startButton->setVisible(true);
            startButton->setButtonColor(TDT4102::Color::medium_sea_green);
        }

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

        std::string selectedFileName;
        for (char& c : selectedFile) {
            if (c == '\\' || c == '/') {
                selectedFileName.clear();
            } else {
                selectedFileName += c;
            }
        }
        if (chosenFile) {
            chosenFile->setText(selectedFileName);
        }

        // Update dir.json with selected file paths
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path rootDir = exePath.parent_path().parent_path();
        std::filesystem::path dataDir = rootDir / "icp_data";
        std::filesystem::create_directories(dataDir);
        std::filesystem::path dirPath = dataDir / "dir.json";

        auto escape_json = [](const std::string& in) {
            std::string out;
            for(char c : in){
                if(c == '\\' || c == '"') out += '\\';
                out += c;
            }
            return out;
        };

        std::map<std::string, std::string> data;
        if(std::ifstream ifs{dirPath}; ifs.is_open()){
            std::string content((std::istreambuf_iterator<char>(ifs)), {});
            std::regex re("\"([^\"]+)\"\\s*:\\s*\"([^\"]*)\"");
            for(auto it = std::sregex_iterator(content.begin(), content.end(), re); it != std::sregex_iterator(); ++it){
                data[(*it)[1].str()] = (*it)[2].str();
            }
        }
        if(chosenFile == selectedExam) data["exam"] = selectedFile;
        else if(chosenFile == selectedSolution) data["solution"] = selectedFile;
        else if(chosenFile == selectedFormulaSheet) data["formula"] = selectedFile;

        std::ofstream ofs(dirPath, std::ios::trunc);
        ofs << "{";
        bool first = true;
        for(const auto& [k,v] : data){
            if(!first) ofs << ",";
            ofs << "\"" << k << "\":\"" << escape_json(v) << "\"";
            first = false;
        }
        ofs << "}";
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Exception i håndtering av PDF: " << e.what() << std::endl;
    }
}

void App::startProcessing() {
    try {
        if (selectedExam->getText() == "No file selected.") {
            std::cout << "[WARN] No exam file selected." << std::endl;
            return;
        }

        startButton->setButtonColor(TDT4102::Color::green);

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
        } else {
            add(*examSubject);
            userinp1 = "";
            examSubjectInput->setVisible(0);
        }
        subjectFile << userinp1;

        std::filesystem::current_path(scriptDir);

        auto escape_json = [](const std::string& in) {
            std::string out;
            for (char c : in) {
                if (c == '\\' || c == '"') out += '\\';
                out += c;
            }
            return out;
        };

        std::ofstream dirFile(dataDir / "dir.json", std::ios::trunc);
        dirFile << "{";
        dirFile << "\"exam\":\"" << escape_json(selectedExam->getText()) << "\",";
        dirFile << "\"solution\":\"" << escape_json(selectedSolution->getText()) << "\",";
        dirFile << "\"formula\":\"" << escape_json(selectedFormulaSheet->getText()) << "\"}";

        // Start Python-script i en bakgrunnstråd
        std::thread([]() {
            std::system("start powershell -Command \"python main.py; pause\"");
        }).detach();

        startTimer();
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Exception i startProcessing: " << e.what() << std::endl;
    }
}

// Map for lesing av tekstfilen
std::string taskLine, GoogleVisionIndicatorLine, DeepSeekIndicatorLine, examSubjectLine, examVersionLine, examAmountLine;
int taskSteps = 8;
const std::map<int, std::string*> ProgressLineMap = {
    {1, &GoogleVisionIndicatorLine},
    {3, &DeepSeekIndicatorLine},
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
        std::filesystem::path rootDir = exeDir.parent_path().parent_path();
        std::filesystem::path scriptDir = rootDir / "scripts";
        std::filesystem::path dataDir = rootDir / "icp_data";
        std::filesystem::create_directories(dataDir);
        std::filesystem::path progressPath = dataDir / "progress.json";

        std::ofstream ofs(progressPath, std::ios::trunc);
        ofs << "{}";
        ofs.close();
        std::cout << "Cleared progress.json at startup." << std::endl;

        FILETIME lastWriteTime = {0, 0};
        
        try {
            while (true) {
                WIN32_FILE_ATTRIBUTE_DATA fileInfo;
                if (GetFileAttributesExA(progressPath.string().c_str(), GetFileExInfoStandard, &fileInfo)) {
                    if (CompareFileTime(&fileInfo.ftLastWriteTime, &lastWriteTime) != 0) {
                        lastWriteTime = fileInfo.ftLastWriteTime;
                        std::cout << "File progress.json has been updated." << std::endl;

                        std::ifstream file(progressPath);
                        if (file.is_open()) {
                            std::string content((std::istreambuf_iterator<char>(file)), {});
                            file.close();
                            std::regex re("\"(\\d+)\"\\s*:\\s*\"([^\"]*)\"");
                            std::map<std::string, std::string> jdata;
                            for (auto it = std::sregex_iterator(content.begin(), content.end(), re); it != std::sregex_iterator(); ++it) {
                                jdata[(*it)[1].str()] = (*it)[2].str();
                            }

                            for (const auto& [line, ptr] : ProgressLineMap) {
                                auto key = std::to_string(line);
                                if (jdata.count(key)) {
                                    *ptr = jdata[key];
                                } else {
                                    *ptr = "";
                                }
                            }
                            if (jdata.count("9")) {
                                try {
                                    taskSteps = std::stoi(jdata["9"]);
                                } catch (...) {
                                    taskSteps = 8;
                                }
                            }

                            // Oppdatering av Google Vision knapp
                            if (!GoogleVisionIndicatorLine.empty()) {
                                for (char c : GoogleVisionIndicatorLine) {
                                    if (c == '1') {
                                        GoogleVisionIndicator->setButtonColor(TDT4102::Color::green);
                                        GoogleVisionIndicator->setButtonColorActive(TDT4102::Color::green);
                                        GoogleVisionIndicator->setLabelColor(TDT4102::Color::white);
                                        break;
                                    }
                                }
                            }

                            // Oppdatering av DeepSeek knapp
                            if (!DeepSeekIndicatorLine.empty()) {
                                for (char c : DeepSeekIndicatorLine) {
                                    if (c == '1') {
                                        DeepSeekIndicator->setButtonColor(TDT4102::Color::green);
                                        DeepSeekIndicator->setButtonColorActive(TDT4102::Color::green);
                                        DeepSeekIndicator->setLabelColor(TDT4102::Color::white);

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
            
                            // Beregn AI-behandling-progresjon til progressbar
                            if (!taskLine.empty()) {
                                try {
                                    ProgressBarLLM->progress = std::stod(taskLine);
                                } catch (...) {
                                    ProgressBarLLM->progress = 0.0;
                                }
                                std::cout << "Task Progress: " << ProgressBarLLM->progress << std::endl;
                            }
                            if (ProgressBarLLM->progress >= 1.0) {
                                stopTimer();
                            }
                        }
                    }
                    Sleep(200);
                } else {
                    std::cerr << "Failed to access progress.json. Retrying..." << std::endl;
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] Exception oppstod i lesing av progress.json" << e.what() << std::endl;
        }
    }).detach();
}


