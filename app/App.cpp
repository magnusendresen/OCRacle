#include "App.h"
#include "widgets/Button.h"
#include "widgets/TextBox.h"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <windows.h>
#include <commdlg.h> // For GetOpenFileNameW

void App::GUI() {
    setBackgroundColor(TDT4102::Color::dim_gray);

    int windowWidth = calculateWindowWidth();
    int windowHeight = calculateWindowHeight();

    auto* pdfButton = new TDT4102::Button({windowHeight / 100, windowWidth / 100}, 200, 100, "Select File");
    pdfButton->setCallback([this]() {
        pdfHandling();
    });

    add(*pdfButton);
}

void App::pdfHandling() {
    // Sett konsoll til UTF-8 for riktig visning av æøå
    SetConsoleOutputCP(CP_UTF8);

    // Bruk wchar_t-buffer for å støtte Unicode
    wchar_t filePath[MAX_PATH] = L"";

    // Konfigurer dialog
    OPENFILENAMEW ofn = {};
    ofn.lStructSize = sizeof(ofn);
    ofn.lpstrFile = filePath;
    ofn.nMaxFile = MAX_PATH;
    ofn.lpstrFilter = L"PDF Files\0*.pdf\0";

    // Vis dialog og hent valgt fil
    if (!GetOpenFileNameW(&ofn)) {
        std::wcout << L"Ingen fil ble valgt." << std::endl;
        return;
    }

    // Konverter UTF-16 (wchar_t) → UTF-8 (std::string)
    int utf8_len = WideCharToMultiByte(CP_UTF8, 0, filePath, -1, nullptr, 0, nullptr, nullptr);
    std::string selectedFile(static_cast<size_t>(utf8_len), 0);
    WideCharToMultiByte(CP_UTF8, 0, filePath, -1, &selectedFile[0], utf8_len, nullptr, nullptr);
    selectedFile.pop_back(); // Fjern nullterminator

    std::cout << "Valgt fil: " << selectedFile << std::endl;

    // Finn scripts-mappe (samme som python.py og dir.txt)
    char buffer[MAX_PATH];
    GetModuleFileNameA(NULL, buffer, MAX_PATH);
    std::filesystem::path exePath = buffer;
    std::filesystem::path exeDir = exePath.parent_path();
    std::filesystem::path scriptDir = exeDir.parent_path().parent_path() / "scripts";
    std::filesystem::current_path(scriptDir);

    std::cout << "scriptDir: " << scriptDir << std::endl;

    // Skriv UTF-8-streng til dir.txt
    std::ofstream dirFile(scriptDir / "dir.txt", std::ios::binary);
    dirFile << selectedFile;
    dirFile.close();

    // Kjør Python-script
    std::system("py main.py");
}
