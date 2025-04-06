#pragma once

#include "AnimationWindow.h"
#include <windows.h>
#include <commdlg.h>
#include <string>
#include <iostream>
#include <locale>
#include <codecvt>

extern int nextFrame;
extern double progress;

class App : public TDT4102::AnimationWindow {
public:
    // Konstruktør
    App(const std::string& windowName);

    // Oppsett av GUI (knapper, etc.)
    void GUI();

    // Velg PDF og start Python-script i bakgrunnstråd
    void pdfHandling();

    void calculateProgress();

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
