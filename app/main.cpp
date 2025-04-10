#include "App.h"
#include "ProgressBar.h"
#include <iostream>
#include <thread>
#include "windows.h"
#include <map>
#include <atomic>
#include <thread>

int main() {
    App myApp("OCRacle");
    
    while (!myApp.should_close()) {
        myApp.update();
        myApp.next_frame();
    }
    return 0;
}