#pragma once

#include "AnimationWindow.h"
#include "Image.h"
#include <string>
#include <chrono>
#include <thread>

#include "widgets/TextBox.h"
#include "widgets/Button.h"
#include "widgets/TextInput.h"

class ProgressBar;


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

    TDT4102::Button *startButton;
    TDT4102::TextBox *GoogleVisionIndicator;
    TDT4102::TextBox *DeepSeekIndicator;

    TDT4102::Button *examUpload;
    TDT4102::TextBox *selectedExam;
    TDT4102::Button *solutionUpload;
    TDT4102::TextBox *selectedSolution;
    TDT4102::Button *formulaSheetUpload;
    TDT4102::TextBox *selectedFormulaSheet;

    TDT4102::TextBox *examSubject;
    TDT4102::TextInput *examSubjectInput;
    TDT4102::TextBox *examVersion;
    TDT4102::TextBox *examAmount;

    TDT4102::TextInput *ignoredTopics;

    ProgressBar *ProgressBarOCR = nullptr;
    ProgressBar *ProgressBarLLM = nullptr;
    ProgressBar *ProgressBarIMG = nullptr;

    TDT4102::Image *ntnuLogo = nullptr;
    int *ntnuLogoScale = nullptr;

    TDT4102::TextBox *timerBox;
    std::thread timerThread;
    std::chrono::time_point<std::chrono::steady_clock> startTime;
    bool timerRunning = false;
private:

};
