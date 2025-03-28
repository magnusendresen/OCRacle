#include "App.h"
#include "widgets/Button.h"
#include "widgets/TextBox.h"

#include <iostream>
#include <fstream>
#include <filesystem>
#include <synchapi.h>
#include <windows.h>
#include <commdlg.h>
#include <thread>

// Definisjon av statiske variabler
unsigned int App::buttonWidth = 200;
unsigned int App::buttonHeight = 100;
int App::pad = 20;

App::App(const std::string& windowName)
    : TDT4102::AnimationWindow{
        calculateWindowPosX(),
        calculateWindowPosY(),
        calculateWindowWidth(),
        calculateWindowHeight(),
        windowName
    } {
    GUI();
}

int App::calculateMonitorWidth() { return GetSystemMetrics(SM_CXSCREEN); }
int App::calculateMonitorHeight() { return GetSystemMetrics(SM_CYSCREEN); }
int App::calculateWindowWidth() { return calculateMonitorWidth() * 3 / 4; }
int App::calculateWindowHeight() { return calculateMonitorHeight() * 3 / 4; }
int App::calculateWindowPosX() { return (calculateMonitorWidth() - calculateWindowWidth()) / 2; }
int App::calculateWindowPosY() { return (calculateMonitorHeight() - calculateWindowHeight()) / 2; }

void App::GUI() {
    setBackgroundColor(TDT4102::Color::light_gray);

    auto* pdfButton = new TDT4102::Button({pad, pad}, buttonWidth, buttonHeight, "Select File");
    pdfButton->setCallback([this]() {
        pdfHandling();
    });

    add(*pdfButton);
}

void App::pdfHandling() {
    SetConsoleOutputCP(CP_UTF8);

    auto* deepseek = new TDT4102::TextBox({pad, pad * 6}, buttonWidth, buttonHeight, "   DeepSeek");
    auto* googlevision = new TDT4102::TextBox({pad, pad * 11}, buttonWidth, buttonHeight, "   Google Vision");
    add(*deepseek);
    add(*googlevision);

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

    int utf8_len = WideCharToMultiByte(CP_UTF8, 0, filePath, -1, nullptr, 0, nullptr, nullptr);
    std::string selectedFile(static_cast<size_t>(utf8_len), 0);
    WideCharToMultiByte(CP_UTF8, 0, filePath, -1, &selectedFile[0], utf8_len, nullptr, nullptr);
    selectedFile.pop_back();  // Fjern null-terminator

    std::cout << "Valgt fil: " << selectedFile << std::endl;

    // Finn script-mappe
    char buffer[MAX_PATH];
    GetModuleFileNameA(NULL, buffer, MAX_PATH);
    std::filesystem::path exePath = buffer;
    std::filesystem::path exeDir = exePath.parent_path();
    std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
    std::filesystem::current_path(scriptDir);

    std::cout << "scriptDir: " << scriptDir << std::endl;

    // Skriv filsti til dir.txt
    std::ofstream dirFile(scriptDir / "dir.txt", std::ios::binary);
    dirFile << selectedFile;
    dirFile.close();

    // Start Python-script
    std::thread([]() {
        std::system("py main.py");
    }).detach();
}
