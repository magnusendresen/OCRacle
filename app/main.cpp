#include "App.h"
#include "ProgressBar.h"
#include <iostream>
#include <thread>
#include "windows.h"
// #include <thread>
ProgressBar* progressBar_ptr = nullptr;

int main() {
    App myApp("OCRacle - med ProgressBar");
    ProgressBar progressBar(myApp);
    progressBar_ptr = &progressBar;

    progressBar.init();

    // progressBar.calculateProgress();

    // progressBar.setCount(0.4);
    
    myApp.wait_for_close();

    return 0;
}
