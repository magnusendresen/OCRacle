#pragma once

#include "AnimationWindow.h"
#include "App.h"
#include <string>



class ProgressBar {
public:
ProgressBar(TDT4102::AnimationWindow& win, int xPos, int yPos, std::string Title);

    void setCount();
    double progress = 0.0;

    std::string Title;
    int xPos;
    int yPos;
    int width  = App::buttonWidth * 4 + App::pad * 3 - 18;
    int height = App::buttonHeight / 3;

private:
    TDT4102::AnimationWindow& window;
};
