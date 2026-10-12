# Analiza treningu – podsumowanie sezonu

Pobiera dane z intervals.icu i buduje `dashboard.html` z tym, co jest w podsumowaniu sezonu od trenera:
CP / AeT / MAP / VO2max / W' (porównanie dwóch okresów), obciążenie tygodniowe wg bodźca, czas w strefach,
kJ/kg, rozkład intensywności, CTL, starty, długie jazdy i spokojne jazdy, które zrobiły się za mocne.

## Pierwsze uruchomienie

1. Skopiuj `.env.example` jako `.env` i wklej swój klucz z intervals.icu (Settings → Developer Settings).
2. W `config.json` ustaw daty sezonu i dwa okresy do porównania.
3. Uruchom:

```bash
python3 sezon.py
```

Potem otwórz `dashboard.html`. Dane zapisują się w `cache/`. `python3 sezon.py --offline` przebudowuje dashboard bez pobierania,
`python3 sezon.py --demo` pokazuje go na danych przykładowych.

## Jak to jest liczone

- **CP i W'**: model 2-parametrowy dopasowany do najlepszych wysiłków 3–20 min z krzywej mocy danego okresu.
  Wynik zależy od tego, czy w okresie były maksymalne wysiłki – bez nich CP wyjdzie zaniżone.
- **AeT**: `aet_jako_procent_cp` × CP (domyślnie 78%). To szacunek, nie wynik testu.
- **MAP**: najlepsza moc z `map_sekundy` (domyślnie 5 min). **VO2max** = 10,8 × MAP/kg + 7.
- **Obciążenie wg bodźca**: obciążenie jazdy (z intervals.icu) rozdzielone na strefy mocy proporcjonalnie do
  czasu × intensywność². Jazdy bez mocy liczone ze stref tętna. Siła i inne sporty mają osobne słupki.
- **Główny bodziec treningu**: strefa, która daje ≥ 25% obciążenia ponad bazą; trzy mocne strefy naraz = mieszany.
- **Starty**: jazdy oznaczone w intervals.icu jako wyścig, dni z wydarzeniem RACE w kalendarzu albo nazwa pasująca do `wzorce_wyscigow`.
- **Spokojne za mocne**: nazwa pasuje do `wzorce_spokojnych`, a IF > `spokojna_za_mocna_if` lub ponad 20% czasu powyżej AeT.
