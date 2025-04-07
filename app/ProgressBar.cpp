#include "ProgressBar.h"
#include <iostream>
#include <thread>

ProgressBar::ProgressBar(TDT4102::AnimationWindow& win, int xPos, int yPos, std::string Title)
    : Title(Title), xPos(xPos), yPos(yPos), window(win) {}

void ProgressBar::setCount(double percent) {
    window.draw_rectangle({xPos, yPos}, width, height, TDT4102::Color::gray);
    int filled = static_cast<int>(width * percent);
    window.draw_rectangle({xPos, yPos}, filled, height, TDT4102::Color::green);
    window.draw_text({xPos, yPos}, Title + ": " + std::to_string(static_cast<int>(percent * 100)) + "%", TDT4102::Color::black);
}
