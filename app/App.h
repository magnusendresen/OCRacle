#pragma once

#include "AnimationWindow.h"
#include "Color.h"
#include "widgets/Button.h"   // Fra TDT4102-biblioteket
#include "widgets/TextBox.h"  // Fra TDT4102-biblioteket
#include "ProgressBar.h"
#include <windows.h>
#include <commdlg.h>
#include <string>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <locale>
#include <codecvt>
#include <synchapi.h>  // Sleep / SleepEx
#include <thread>

extern int nextFrame;
extern double progress;
extern double progress2;

class App : public TDT4102::AnimationWindow {
public:
    // Konstruktør
    App(const std::string& windowName);

    // Oppsett av GUI (knapper, etc.)
    void GUI();
    void pdfHandling();
    void calculateProgress();

    TDT4102::Button *pdfButton;
    TDT4102::TextBox *googlevision;
    TDT4102::TextBox *deepseek;

    TDT4102::TextBox *examSubject;
    TDT4102::TextBox *examVersion;
    TDT4102::TextBox *examAmount;

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
