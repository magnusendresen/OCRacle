#pragma once

#include "AnimationWindow.h"
#include "Point.h"
#include <filesystem>
#include <fstream>
#include <windows.h>

extern int nextFrame;
extern double progress;
extern double progress2;

class ProgressBar {
public:
    ProgressBar(TDT4102::AnimationWindow& win, int xPos, int yPos, std::string Title);

    // Tegner grønn fremdriftsindikator
    void setCount(double percent);

    std::string Title;
    int xPos;
    int yPos;

private:
    TDT4102::AnimationWindow& window;
    const int width  = 800;
    const int height = 40;
};
