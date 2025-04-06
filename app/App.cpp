#include "App.h"
#include "Color.h"
#include "widgets/Button.h"   // Fra TDT4102-biblioteket
#include "widgets/TextBox.h"  // Fra TDT4102-biblioteket

#include <iostream>
#include <fstream>
#include <filesystem>
#include <synchapi.h>  // Sleep / SleepEx
#include <windows.h>
#include <commdlg.h>
#include <thread>
#include "ProgressBar.h"

// Definisjon av statiske variabler
unsigned int App::buttonWidth = 200;
unsigned int App::buttonHeight = 100;
int App::pad = 20;

extern ProgressBar* progressBar_ptr;  // Ingen ny definisjon!

App::App(const std::string& windowName)
    : TDT4102::AnimationWindow{
        calculateWindowPosX(),
        calculateWindowPosY(),
        calculateWindowWidth(),
        calculateWindowHeight(),
        windowName
    }
{
    // Sett bakgrunnsfarge og kall GUI-setup
    setBackgroundColor(TDT4102::Color::light_gray);
    GUI();
}

int App::calculateMonitorWidth()  { return GetSystemMetrics(SM_CXSCREEN); }
int App::calculateMonitorHeight() { return GetSystemMetrics(SM_CYSCREEN); }
int App::calculateWindowWidth()   { return calculateMonitorWidth() * 3 / 4; }
int App::calculateWindowHeight()  { return calculateMonitorHeight() * 3 / 4; }
int App::calculateWindowPosX()    { return (calculateMonitorWidth() - calculateWindowWidth()) / 2; }
int App::calculateWindowPosY()    { return (calculateMonitorHeight() - calculateWindowHeight()) / 2; }

/*
-----------------------------------------------------------------------
*/

void App::GUI() {
    // Knapp for å velge fil
    auto* pdfButton = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Select File");
    pdfButton->setCallback([this]() {
        pdfHandling();
    });
    add(*pdfButton);
}

/*
-----------------------------------------------------------------------
*/

void App::pdfHandling() {

    Sleep(1000);

    std::cout << "Handling PDF..." << std::endl;

    calculateProgress();


    // For å kunne skrive æøå i console
    SetConsoleOutputCP(CP_UTF8);

    // Legg til to 'TextBox'-widgets for illustrasjon
    auto* deepseek = new TDT4102::TextBox({pad, pad * 6}, buttonWidth, buttonHeight, "   DeepSeek");
    auto* googlevision = new TDT4102::TextBox({pad, pad * 11}, buttonWidth, buttonHeight, "   Google Vision");
    add(*deepseek);
    add(*googlevision);

    

    // Dialog for å velge PDF
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
        selectedFile.pop_back(); // Fjern null-terminator om nødvendig
    }

    std::cout << "[INFO] Valgt fil: " << selectedFile << std::endl;

    // Finn /scripts-mappe (for Python)
    char buffer[MAX_PATH];
    GetModuleFileNameA(NULL, buffer, MAX_PATH);
    std::filesystem::path exePath = buffer;
    std::filesystem::path exeDir = exePath.parent_path();
    std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
    std::filesystem::current_path(scriptDir);

    std::cout << "[INFO] scriptDir: " << scriptDir << std::endl;

    // Skriv filsti til dir.txt
    {
        std::ofstream dirFile(scriptDir / "dir.txt", std::ios::binary);
        dirFile << selectedFile;
    }

    // Start Python-script i en bakgrunnstråd
    std::thread([]() {
        // Kall Python. Evt. "python main.py" eller "py main.py"
        std::system("start powershell -Command \"python main.py\""); 
    }).detach();    
}

/*
-----------------------------------------------------------------------
*/

void App::calculateProgress() {
    std::cout << "\n\n\n Starting progress calculation... \n\n\n" << std::endl;

    std::thread([]() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        std::filesystem::path exePath = buffer;
        std::filesystem::path exeDir = exePath.parent_path();
        std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
        std::filesystem::path progressPath = scriptDir / "progress.txt";

        // Tømmer progress.txt ved oppstart
        {
            std::ofstream ofs(progressPath, std::ios::trunc);
            ofs.close();
            std::cout << "Cleared progress.txt at startup." << std::endl;
        }

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
                        std::string ocrLine, taskLine;
                        int currentLine = 1;
                        // Les filen linje for linje og lagre linje 2 og 4
                        while (std::getline(file, line)) {
                            if (currentLine == 2) {
                                ocrLine = line;
                                // googlevision.setColor()
                            } else if (currentLine == 4) {
                                taskLine = line;
                            }
                            currentLine++;
                        }
        
                        double progressFraction = 0.0;
                        // Beregn OCR-progresjonen fra linje 2
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
                                progressFraction = static_cast<double>(sum) / static_cast<double>(count);
                            }
                        }
        
                        // Dersom OCR-prosessen er fullført, bytt til oppgaveprogresjonen fra linje 4
                        if (progressFraction >= 1.0 && !taskLine.empty()) {
                            int sum = 0;
                            int count = 0;
                            for (char c : taskLine) {
                                if (isdigit(c)) {
                                    sum += c - '0';
                                    count++;
                                }
                            }
                            if (count > 0) {
                                progressFraction = static_cast<double>(sum) / static_cast<double>(count);
                            }
                        }
                        progress = progressFraction;
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

