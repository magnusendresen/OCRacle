#pragma once

#include "AnimationWindow.h"
#include <string>


class ProgressBar {
public:
ProgressBar(TDT4102::AnimationWindow& win, int xPos, int yPos, std::string Title);

    void setCount();
    double progress;

    std::string Title;
    int xPos;
    int yPos;
    int width  = 800;
    int height = 40;

private:
    TDT4102::AnimationWindow& window;
};
