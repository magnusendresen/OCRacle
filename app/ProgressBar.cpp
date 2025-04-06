#include "ProgressBar.h"
#include <iostream>
#include <thread>

ProgressBar::ProgressBar(TDT4102::AnimationWindow& win)
    : window(win) {}

void ProgressBar::setCount(double percent) {
    window.draw_rectangle(Pos, width, height, TDT4102::Color::gray);
    int filled = static_cast<int>(width * percent);
    window.draw_rectangle(Pos, filled, height, TDT4102::Color::green);
}
