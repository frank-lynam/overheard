# Overheard

An AI voicemail console that catches what busy humans miss.

Overheard replays one day of voicemail at a fictional federal call center, the
*Federal Benefits Service Center*, plus a three-year archive, through four modes:
**No AI**, **Obvious AI**, **Non-obvious AI** and **Impossible without AI**. A
running scoreboard shows what each mode adds: agent hours, callbacks avoided,
deadline-bound requests caught, and dollars.

All data is synthetic. Mock mode (the default) runs fully offline; point it at
any OpenAI-compatible endpoint to use a real model.

```sh
pip install overheard
overheard serve          # then open http://127.0.0.1:8000
```

**Status:** early. This release is the skeleton: the console shell and its mode
stepper. See [docs/DESIGN.md](docs/DESIGN.md) for where it's going.
