#include "App.h"
#include "ProgressBar.h"
#include <iostream>
#include <thread>
#include "windows.h"
#include <atomic>
#include <thread>

ProgressBar* progressBar_ptr = nullptr;
int nextFrame = false;

double progress = 0.0;
double prevProgress = 0.0;
int fileSum = 0;
std::size_t fileLen = 0;
std::atomic<bool> progressDone = false;

int i = 0;

int main() {
    App myApp("OCRacle - med ProgressBar");
    progressBar_ptr = new ProgressBar(myApp); 

    // Oppdater til neste bilde

    progressBar_ptr->setCount(0.0);
    
    std::cout << "Starting while loop..." << std::endl;
    while (!myApp.should_close()) {
        progressBar_ptr->setCount(progress);
        myApp.next_frame();
        if (i > 50) {
            std::cout << progress << std::endl;
            i = 0;
        }
        i++;
    }
    return 0;
}