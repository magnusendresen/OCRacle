#pragma once
#include "animationwindow.h"

class Progress {
public:
    Progress(TDT4102::AnimationWindow& win);

    void draw_progress_bar();

private:
    TDT4102::AnimationWindow& window;
};
