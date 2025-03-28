#pragma once

#include "AnimationWindow.h"
#include "Point.h"
#include <atomic>
#include <thread>
#include <filesystem>
#include <fstream>
#include <windows.h>

class ProgressBar {
public:
    ProgressBar(TDT4102::AnimationWindow& win);

    void init();
    void setCount(double percent);      // Kalles fra GUI-løkken
    void calculateProgress();           // Kjører i bakgrunnstråd

    std::atomic<double> progressPercent;
    std::atomic<bool> progressDone;

private:
    TDT4102::AnimationWindow& window;
    const int width = 800;
    const int height = 40;
    const TDT4102::Point Pos = {280, 40};  // Unngår App::pad-avhengighet
};