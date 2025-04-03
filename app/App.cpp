#include "App.h"
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

void App::GUI() {
    // Knapp for å velge fil
    auto* pdfButton = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Select File");
    pdfButton->setCallback([this]() {
        pdfHandling();
    });
    add(*pdfButton);
}

void App::pdfHandling() {

    Sleep(1000);

    std::cout << "Handling PDF..." << std::endl;

    progressBar_ptr->calculateProgress();


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

// void App::animate(window) {
//     while (true) {
//         if (progressBar_ptr->progress != progressBar_ptr->prevProgress) {
//             progressBar_ptr->setCount(progressBar_ptr->progress);
//             progressBar_ptr->prevProgress = progressBar_ptr->progress;
//             window.next_frame();
//         }
//     }
// }
