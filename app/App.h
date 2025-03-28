#pragma once

#include "AnimationWindow.h"
#include <windows.h>
#include <commdlg.h>
#include <string>
#include <iostream>
#include <locale>
#include <codecvt>

class App : public TDT4102::AnimationWindow {
public:
    // Konstruktør
    App(const std::string& windowName);

    // Oppsett av GUI
    void GUI();

    // Filvalg og Python-kall
    void pdfHandling();

    // Globale GUI-konstanter for layout
    static unsigned int buttonWidth;
    static unsigned int buttonHeight;
    static int pad;

private:
    // Hjelpefunksjoner for vindusstørrelse og posisjon
    static int calculateMonitorWidth();
    static int calculateMonitorHeight();
    static int calculateWindowWidth();
    static int calculateWindowHeight();
    static int calculateWindowPosX();
    static int calculateWindowPosY();
};
