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
    ProgressBar(TDT4102::AnimationWindow& win);

    // Tegner grønn fremdriftsindikator
    void setCount(double percent, int xPos, int yPos);

    // Leser progress.txt i bakgrunnstråd og oppdaterer global progress
    void calculateProgress();

private:
    TDT4102::AnimationWindow& window;
    const int width  = 800;
    const int height = 40;
    const TDT4102::Point Pos = {280, 40};
};
