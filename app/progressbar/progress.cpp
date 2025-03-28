#include "progress.h"
#include <cstddef>
#include <windows.h>

Progress::Progress(TDT4102::AnimationWindow& win) : window(win) {}

void Progress::draw_progress_bar() {
    // Eksempel: tegner en enkel rektangulær fremdriftsindikator
    int width = 200;
    int height = 20;
    double percent;
    
    
    for (int i = 0; i < 100; i++) {
        percent = static_cast<double>(i) / 100;
        int filled = static_cast<int>(width * percent);
        window.draw_rectangle({100, 100}, width, height, TDT4102::Color::gray);
        window.draw_rectangle({100, 100}, filled, height, TDT4102::Color::green);
        Sleep(10);
        window.next_frame();
    }
}
