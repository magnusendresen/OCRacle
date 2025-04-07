#include "App.h"
#include "ProgressBar.h"
#include <iostream>
#include <thread>
#include "windows.h"
#include <atomic>
#include <thread>

ProgressBar* progressBar_ptr = nullptr;
ProgressBar* progressBar_ptr2 = nullptr;

double progress = 0.0;
double progress2 = 0.0;
int fileSum = 0;
int fileSum2 = 0;
std::size_t fileLen = 0;
std::atomic<bool> progressDone = false;

int main() {
    App myApp("OCRacle - med ProgressBar");
    std::cout << "Starting while loop..." << std::endl;
    
    while (!myApp.should_close()) {
        progressBar_ptr->setCount(progress);
        progressBar_ptr2->setCount(progress2);
        myApp.next_frame();
    }
    return 0;
}