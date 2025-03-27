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
    App(int x, int y, int width, int height)
        : TDT4102::AnimationWindow{x, y, width, height, "App"} {
            // GUI();
            GUI();
        }

    static int calculateMonitorWidth() { return GetSystemMetrics(SM_CXSCREEN); }

    static int calculateMonitorHeight() { return GetSystemMetrics(SM_CYSCREEN); }

    static int calculateWindowWidth() { return calculateMonitorWidth() * 3/4; }

    static int calculateWindowHeight() { return calculateMonitorHeight() * 3/4; }

    static int calculateWindowPosX() { return (calculateMonitorWidth() - calculateWindowWidth()) / 2; }

    static int calculateWindowPosY() { return (calculateMonitorHeight() - calculateWindowHeight()) / 2; }

    void GUI();

    void pdfHandling();
};