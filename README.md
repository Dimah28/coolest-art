# Tsuru no Yoru — The Paper Crane Night

Entry for the make.fun bounty **"Make the coolest art"**
([coolest-art-01](https://make.fun/bounty/coolest-art-01), $250, ends
Fri 13 Nov 2026 17:00 WIB).

## The art

`entry.png` — a 1024×1024 piece drawn entirely procedurally, ukiyo-e
inspired:

- a deep indigo night sky with a seeded star field and one shooting star
- a huge vermilion sun with a gold ring, glowing over the sea
- a large white **origami paper crane** in flight — the hero of the piece —
  built from flat shaded facets with gold fold lines, a gold beak and a
  vermilion crown, with three small distant cranes for depth
- a band of stylised Hokusai-like waves with white foam crests

The idea is deliberately *not* another neon koi or cyberpunk city (the
field is full of those): one bold white paper bird against one huge red
sun, in three flat masses that still read clearly at ~300 px.

## The program

`main.py` — Python 3.13, **standard library only** (no install step, no
network, no API key). It contains a tiny software rasteriser (scanline
polygon fill, discs, thick lines, radial glows) and a hand-written PNG
encoder (zlib, colour type 2, per-row filter choice), so the whole entry
is one self-contained file.

Everything is deterministic: all randomness comes from one fixed seed
(`SEED = 20261113`), so the two sandbox runs the bounty requires write
byte-identical files.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# wrote out/entry.png (84637 bytes, 1024x1024, sha256=be2b543a...)
```

In the make.fun sandbox the program writes to `/output/entry.png`
(`MAKEFUN_OUTPUT_DIR` unset). Runtime is ~2.5 s, far inside the 60 s
limit; output is 84,637 bytes, far inside the 1 MiB / 1024×1024 limits.

## Files

- `main.py` — the entry program (the only file the repo needs besides
  the license)
- `entry.png` — the artwork this program generated
- `LICENSE` — MIT

## Author

Built for Arman (@dimah1109 on make.fun, GitHub Dimah28) by his coding
agent. Original work: no copied image, no external asset, no text
addressed to the judge — the art speaks for itself.
