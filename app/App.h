#pragma once

#include "AnimationWindow.h"
#include "ProgressBar.h"
#include <string>
#include <chrono>
#include <thread>

#include "widgets/TextBox.h"
#include "widgets/Button.h"
#include "widgets/TextInput.h"


class App : public TDT4102::AnimationWindow {
public:
    App(const std::string& windowName);

    void GUI();
    void pdfHandling();
    void calculateProgress();
    void startTimer();
    void stopTimer();
    void update();
    
    static constexpr int buttonWidth = 200;
    static constexpr int buttonHeight = 100;
    static constexpr int pad = 20;

    TDT4102::Button *pdfButton;
    TDT4102::TextBox *googlevision;
    TDT4102::TextBox *deepseek;

    TDT4102::TextBox *examSubject;
    TDT4102::TextInput *examSubjectInput;
    TDT4102::TextBox *examVersion;
    TDT4102::TextBox *examAmount;

    ProgressBar *ProgressBar1 = nullptr;
    ProgressBar *ProgressBar2 = nullptr;

    TDT4102::TextBox *timerBox;
    std::thread timerThread;
    std::chrono::time_point<std::chrono::steady_clock> startTime;
    bool timerRunning = false;
private:

};
