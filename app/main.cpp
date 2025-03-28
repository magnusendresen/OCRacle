#include "App.h"
#include "ProgressBar.h"
#include <thread>
#include <windows.h>

int main() {
    // Opprett hovedvindu
    App myApp("OCRacle - med ProgressBar");

    // Hvorvidt vi vil beholde bakgrunnen mellom hver frame:
    // (false = slett gammel tegning hver runde)
    myApp.keep_previous_frame(false);

    // Opprett progressbaren
    ProgressBar progressBar(myApp);
    progressBar.init();             // Tegn første "grå ramme"

    // Start bakgrunnstråden som bare leser av progress.txt
    progressBar.calculateProgress(); 

    // Kjør «evighetsløkke» selv, i stedet for myApp.wait_for_close()
    while (!myApp.should_close()) {
        // Les av nåværende fremdrift (0.0 til 1.0)
        double p = progressBar.progressPercent.load();

        // Tegn progress (samt grå bakgrunn på nytt)
        progressBar.setCount(p);

        // Hvis vi er i mål, «låser» vi baren på 100%
        if (progressBar.progressDone.load()) {
            progressBar.setCount(1.0);
        }

        // Neste frame — tegner GUI (widgets), håndterer eventer
        myApp.next_frame();
    }

    return 0;
}
