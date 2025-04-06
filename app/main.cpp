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

bool DeepSeek = false;
bool GoogleVision = false;

int main() {
    App myApp("OCRacle - med ProgressBar");
    progressBar_ptr = new ProgressBar(myApp); 
    progressBar_ptr2 = new ProgressBar(myApp);
    
    std::cout << "Starting while loop..." << std::endl;
    while (!myApp.should_close()) {
        progressBar_ptr->setCount(progress, App::pad*14, App::pad*7);
        progressBar_ptr2->setCount(progress2, App::pad*14,App::pad*12);
        myApp.next_frame();
    }
    return 0;
}