#include "animationwindow.h"
#include "progress.h"

int main() {
    TDT4102::AnimationWindow window(100, 100, 600, 400, "Progress Window");

    Progress progress(window); // Send window som referanse
    progress.draw_progress_bar(); // Tegner 75% fylt bar

    window.wait_for_close();
    return 0;
}
