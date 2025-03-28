#pragma once

#include "AnimationWindow.h"
#include "Point.h"
#include <atomic>
#include <filesystem>
#include <fstream>
#include <windows.h>

class ProgressBar {
public:
    ProgressBar(TDT4102::AnimationWindow& win);

    // Tegner opp "rammen" (bakgrunnen) én gang
    void init();

    // Setter hvor mye av baren som skal fylles (0.0 til 1.0)
    void setCount(double percent);

    // Starter bakgrunnstråd som jevnlig leser progress.txt og oppdaterer progressPercent
    void calculateProgress();

    // Disse er offentlige slik at main() enkelt kan sjekke status
    std::atomic<double> progressPercent;
    std::atomic<bool>   progressDone;

private:
    TDT4102::AnimationWindow& window;
    const int width  = 800;
    const int height = 40;
    const TDT4102::Point Pos = {280, 40};  // Lar den stå litt inn på skjermen
};
