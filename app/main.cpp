#include "AnimationWindow.h"
#include <windows.h>
#include <iostream>
#include <cstdlib>
#include <locale>
#include <codecvt>

#include "App.h"


int main() {

    App window(App::calculateWindowPosX(), App::calculateWindowPosY(), App::calculateWindowWidth(), App::calculateWindowHeight());
    window.wait_for_close();

    return 0;
}
