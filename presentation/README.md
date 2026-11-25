# Presentation

Open `blackjack_presentation.html` in a browser. It is a single self-contained file: CSS, JavaScript, charts and a snapshot of the simulator data are embedded, so it works offline and needs no server.

The deck has 22 slides, live demos, speaker notes, a 15-minute timer, light/dark themes and keyboard controls. The presenter's name is in the top-left of every slide, and the overview page shows who is presenting each slide.

## Controls

- `←` / `→` or `Space`: move between slides
- `O`: overview of every slide, with presenters
- `N`: speaker notes for the current slide
- `T`: start or pause the 15-minute timer
- `F`: fullscreen
- `L`: light or dark theme
- `?`: controls

## Editable speaker notes

Serve the folder with `serve.py` to enable shared notes:

```bash
python3 serve.py --port 8088 --root . --state /tmp/blackjack-notes
```

Open `http://localhost:8088/`. The notes panel has an **Edit notes** button. Each slide's note is limited to 200 words and 1,000 characters, saves to the server automatically, and reloads on another device. The notes live outside the deck HTML, so editing them never changes the presentation file.

In production the systemd service `blackjack-presentation.service` binds the server to `127.0.0.1:8088` and keeps notes in `/var/lib/blackjack-presentation/notes.json` through systemd's `StateDirectory`.

`build_data.py` regenerates the data snapshot from the simulator. The committed HTML already contains the data, so you only need it if you change the simulation.
