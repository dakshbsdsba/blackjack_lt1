# Presentation

Open `blackjack_presentation.html` in a browser. It is a single self-contained file: CSS, JavaScript, charts and a snapshot of the simulator data are embedded, so it works offline and needs no server.

Controls:

- `←` / `→` or `Space`: move between slides
- `O`: overview of every slide
- `N`: speaker notes for the current slide
- `T`: start or pause the 15-minute timer
- `F`: fullscreen
- `L`: light or dark theme
- `?`: controls

The demos are live: the mini table, ace builder, dealer policy, payout calculator, split walkthrough, strategy explorer, shoe, counter, Monte Carlo chart and risk tabs all run in the browser.

`build_data.py` regenerates the data snapshot from the simulator. The committed HTML already contains the data, so you only need it if you change the simulation.
