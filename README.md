# Wirelist Convertatron

Converts a cable assembly **wire list** into a block of Cirris **`WIRE` instructions**. A `CUSTOM_LABELS` file translates connector/pin labels into tester points.

It comes as a Windows desktop app with Impact ES / Cirris branding, and as a command-line script for batch use or scripting.

```
_J1-52,P1-1          ──►   INSTRUCTIONS
_J1-53,P1-2                BEGIN
_J1-51,P1-3                    WIRE,   J1-52,  J2-17, 10.0 Ohm
   ...                         WIRE,   J1-53,  J2-18, 10.0 Ohm
                               WIRE,   J1-51,  J2-19, 10.0 Ohm
                                  ...
                           END
```

---

## Features

- **Paste or open:** paste the wire list and label list straight into the app, or load them from files. Loaded text can be edited before converting.
- **Label list with or without the header:** use a full `CUSTOM_LABELS` / `BEGIN` / `END` block or just the `J1-1, _J1-1` lines.
- **Adjustable resistance:** set the ohm value written on every `WIRE` line (default 10.0 Ω).
- **Clear problem reporting:** unknown points, malformed lines and conflicting labels are listed in a Messages tab. Bad wires are skipped and everything else is still converted.
- **Copy or save:** copy the result to the clipboard to paste into your Cirris file, save it to a file, or have every conversion saved to the same file automatically.
- **Case-insensitive matching:** `j3-36` and `J3-36` resolve the same way.

## Download (Windows)

Download the latest `Wirelist-Convertatron` zip from the [**Releases**](https://github.com/nathanielthick/py-test/releases) page. Unzip it and run `Wirelist-Convertatron.exe`. Python is not required.

> Keep the `_internal` folder next to the `.exe`; the program needs it to run.
> Windows SmartScreen or antivirus may warn about an unsigned program the first time it runs.

## Using the app

1. **Wire list:** paste it into the left box or click **Open file…**.
2. **Label list:** paste it into the middle box or click **Open file…**.
3. Set **Resistance per wire** if you need something other than 10.0 Ω.
4. Click **Convert** (or press **Ctrl+Enter**).
5. Use **Copy** to put the instructions on the clipboard, or **Save as…** to write them to a file. Check the **Messages** tab for any skipped lines.

If `wires.csv` and `labels.txt` are in the same folder as the program, they are loaded automatically when it starts.

---

## Input formats

### Wire list

One wire per line, as two comma-separated ends. Each end can be a label or a tester point. Blank lines and lines starting with `#` are ignored.

```csv
# from, to
_J1-52,P1-1
_J1-53,P1-2
j3-36,P2-1
```

### Label list

Each line is `tester point, label`.

```text
CUSTOM_LABELS
BEGIN
     J1-52, _J1-52
     J2-17, P1-1
     J2-18, P1-2
END
```

In the app you can paste just the lines between `BEGIN` and `END`.

### How each wire end is resolved

Matching is case-insensitive, and the rules are applied in this order:

1. If the end is a **tester point listed in the label file** (e.g. `j3-36` → `J3-36`), it is used as-is.
2. If it is a **label** (e.g. `_J1-52`, `P1-1`), it is translated to that label's tester point.
3. If it **looks like a tester point** (`J<n>-<pin>`, no underscore), it is used as-is, even if the label file doesn't list it.
4. Otherwise it is reported as **unresolved** and that wire is skipped. All other wires are still written.

For example, a wire to `NC` (no connection) is reported and skipped:

```
Error: Wire list line 65 (_J1-29,NC): unknown point/label NC; wire skipped
```

---

## Running from source

You need Python 3.8 or newer with Tkinter, which is included in the standard Windows installer from python.org. There are no other required packages.

```bash
git clone https://github.com/nathanielthick/py-test.git
cd py-test
python wirelist_gui.py
```

[Pillow](https://pypi.org/project/Pillow/) is optional (`pip install pillow`). It gives smoother logo scaling and also lets the app use JPG logos.

### Command line

```bash
# print to screen
python wirelist_to_instructions.py wires.csv labels.txt

# write to a file with 5 Ω per wire
python wirelist_to_instructions.py wires.csv labels.txt -o out.txt -r 5.0
```

| Option | Description |
|---|---|
| `wirelist` | Comma-separated wire list file |
| `labels` | File containing the `CUSTOM_LABELS` block |
| `-o`, `--output` | Output file (default: print to screen) |
| `-r`, `--resistance` | Resistance in ohms for each wire (default: `10.0`) |

The exit code is `1` if any line had problems, so scripts can detect skipped wires.

---

## Building the .exe

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name "Wirelist-Convertatron" wirelist_gui.py
```

The program is written to `dist/Wirelist-Convertatron/`. Copy the logo images into that folder next to the `.exe`, then zip the folder to publish it as a release.

For a single self-contained `.exe` with the logos built in, use this instead:

```bash
pyinstaller --onefile --windowed --name "Wirelist-Convertatron" ^
  --add-data "impact_logo.png;." ^
  --add-data "cirris_komaxCompany_color_rgb.png;." ^
  wirelist_gui.py
```

### Logos

The header shows the Impact ES logo on the left and the Cirris logo on the right. The app finds them by file name: any PNG or GIF whose name contains `impact` or `cirris`. It looks next to the script or `.exe`, then in an `assets/` or `images/` subfolder, then in files built into the `.exe`. If a logo is missing, its name is shown as text instead.

---

## Project files

| File | Purpose |
|---|---|
| `wirelist_gui.py` | Desktop app (Tkinter) |
| `wirelist_to_instructions.py` | Conversion logic and command-line tool; the app uses it |
| `impact_logo.png`, `cirris_komaxCompany_color_rgb.png` | Header logos |
| `wires.csv`, `labels.txt` | Example wire list and label file |
| `out.txt` | Example output (5.0 Ω) |
