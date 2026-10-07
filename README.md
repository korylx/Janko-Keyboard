

# Linear QWERTY MIDI controller (Windows)

Turns a US QWERTY keyboard into a MIDI controller. Three layouts: **janko** (shipped in `config.json`), **diatonic**, and **column**. MIDI is sent to a [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) virtual port.

**Run this with Windows and Python.** The hook and MIDI APIs are Win32-only.

AI-Disclosure: this project was built in collaboration with AI

## Setup

1. Install [Python 3](https://www.python.org/downloads/) for Windows (the `py` launcher is fine).
2. Install loopMIDI, create a port named **`loopMIDI Port`** (or change `port` in `config.json` to match).
3. In your DAW, set MIDI input to that loopMIDI port.
4. Double-click `run.bat`, or from this folder: `py -3 main.py`.

To **prove MIDI is leaving this app** (does not need Caps+Alt): `py -3 main.py --send-test` or `send-test.bat`. You should see a printed CC 11/12 sweep. In Ableton, that only shows up in MIDI Map if the loopMIDI input has **Track** and **Remote** checked (Preferences → Link, Tempo & MIDI). Track alone is enough for notes, not for mapping CCs.

No pip packages are required (stdlib + ctypes only).

## Playing

- **Caps Lock + either Alt** (together) arms or disarms the controller. Caps Lock is swallowed while this app runs so Windows does not toggle caps.
- When **OFF**, keys type normally except that toggle chord.
- When **ON**, note keys, Space, both Alts, both Shifts, and arrow keys are swallowed so they do not type into the DAW.
- **Space** = sustain (CC 64).
- **Left Alt** = quieter velocity while held.
- **Right Alt** = louder velocity while held.
- **Arrow keys:** left/right = transpose ±1 semitone, up/down = ±1 octave (new notes only; keys already down keep their pitch).
- **Mouse, while ON:** **Up/down** → CC 11 expression if `mouse_cc_y` is set (`null` disables). **Left/right** → pitch bend if `mouse_pitch_bend` is true. **Scroll wheel** → `mouse_wheel_cc` (default 1); `null` disables. Currently expression and pitch bend are off in `config.json`; wheel still works.

On disarm or quit, sustain is released and all notes are panicked.

## Keymaps

Set `"layout"` in `config.json` to `"janko"`, `"diatonic"`, or `"column"`. `root_note` is the MIDI number for key `1`. Shipped config is **janko** with **48 (C3)**.

### diatonic (C major)

C major: **`1`=C … `7`=B, `8`=C** an octave up. **`q` is that same C as `8`**. Each lower row starts on the previous row’s 8th key (another repeated C).

```
Number:  1 2 3 4 5 6 7 8 9 0 - =     C  D  E  F  G  A  B  C  D  E  F  G
Q:       q w e r t y u i o p [ ]     C  D  E  F  G  A  B  C  D  E  F  G   (q = same C as 8)
A:       a s d f g h j k l ; '       C  D  E  F  G  A  B  C  D  E  F
Z:       z x c v b n m , . /         C  D  E  F  G  A  B  C  D  E
```

**Bends** (chromatic ±1 MIDI note, not pitch-bend). Left Shift = down, Right Shift = up:

- **One or more keys already down:** the next key while Shift is held plays bent; already-held notes unbend back to natural.
- **Exactly one key down:** Shift note-offs that pitch and plays the neighbor on the same key.
- **No keys down:** hold Shift, then play; new notes are bent.
- **Shift released:** any sounding bent notes snap back to their natural pitches.

Caps+Alt still toggles and is not a bend.

### column

Physical columns `1qaz`, `2wsx`, `3edc`, … **Down = +1 semitone. Right = +4 (major third).** One octave is three columns: with `root_note` 48, `1` = C3 and `4` = C4.

Major scale: **`1 a 2 w x e c 4`**. Major triad: `1 2 x`. Same shapes slide down-right.

```
     1    2    3    4    5    6    7    8    9    0    -    =
     q    w    e    r    t    y    u    i    o    p    [    ]
     a    s    d    f    g    h    j    k    l    ;    '
     z    x    c    v    b    n    m    ,    .    /

     C3   E3   G#3  C4   E4   G#4  C5   E5   G#5  C6   E6   G#6
     C#3  F3   A3   C#4  F4   A4   C#5  F5   A5   C#6  F6   A6
     D3   F#3  A#3  D4   F#4  A#4  D5   F#5  A#5  D6   F#6
     D#3  G3   B3   D#4  G4   B4   D#5  G5   B5   D#6  G6
```

### janko (current `config.json`)

Same row, one key right = **+2 semitones**. Number vs Q (and A vs Z) = **+1 semitone**. A/Z are **two octaves above** number/Q. With `root_note` **48**, `1` is **C3** and `a` is **C5**.

```
Number:  1 2 3 4 5 6 7 8 9 0 - =     C3  D3  E3  F#3 G#3 A#3 C4  D4  E4  F#4 G#4 A#4
Q:       q w e r t y u i o p [ ]     C#3 D#3 F3  G3  A3  B3  C#4 D#4 F4  G4  A4  B4
A:       a s d f g h j k l ; '       C5  D5  E5  F#5 G#5 A#5 C6  D6  E6  F#6 G6
Z:       z x c v b n m , . /         C#5 D#5 F5  G5  A5  B5  C#6 D#6 F6  G6
```

`+` / `}` / `"` are the shifted labels for `=` / `]` / `'`.

## Config (`config.json`)

| Field | Meaning |
| --- | --- |
| `port` | loopMIDI port name (exact match, or a unique substring) |
| `layout` | `"janko"` (shipped), `"diatonic"`, or `"column"` |
| `root_note` | MIDI note number for `1` (C1 = 24, C2 = 36, C3 = 48). Shipped: **48** |
| `channel` | MIDI channel 0–15 (0 = channel 1) |
| `mouse_cc_y` | CC for vertical mouse (11 = Expression); `null` to disable |
| `mouse_pitch_bend` | If `true`, horizontal mouse is pitch bend |
| `mouse_sensitivity` | CC units per vertical mouse count (default **0.4**) |
| `mouse_pitch_sensitivity` | Pitch-bend units per horizontal mouse count (default **24**; center 8192) |
| `mouse_wheel_cc` | CC for scroll wheel (default **1** = mod wheel); `null` to disable |
| `mouse_wheel_sensitivity` | CC units per wheel notch (default **8**; one notch ≈ 120 raw) |
| `velocity.default` | Velocity with no Alt held (1–127). Default **80** |
| `velocity.left_alt` | Velocity while Left Alt is held. Default **16** |
| `velocity.right_alt` | Velocity while Right Alt is held (wins if both Alts are down). Default **127** |

| `debug` | If `true`, log every note-key down/up. Leave **false** while playing — console I/O adds latency. |

Startup prints every WinMM output so you can fix a name mismatch.

## 3–4 key chords and ghosting

The app sends a note-on as soon as Windows reports a keydown. It does not wait for keyup. If a third or fourth note only sounds when you *release* fingers, Windows probably never saw that keydown — typical **keyboard matrix ghosting** (2-key or partial 3-key rollover), not a MIDI queue.

`1+w+r` is a common ghost on membrane/laptop boards (keys on the same matrix rectangle). Adjacent keys on one row (`1+2+3`) often work; diagonals often do not.

**Confirm without this app:** disable the controller (or quit it), open Notepad, hold `1` and `w`, then press `r`. If `r` does not type until you lift a key, the hardware cannot report that combo. A full-NKRO keyboard (many mechanical boards, or a dedicated MIDI controller) will.

With `"debug": true` in `config.json`, a real chord prints three `key down` lines *while fingers are still down*. A ghost prints two downs, then `r`'s down only after another key's `up`.

## Quit

Ctrl+C in the console window, or close it.
