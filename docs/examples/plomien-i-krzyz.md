# Przykład: wyszukanie całego cyklu "Płomień i krzyż" (tomy 1-4)

Cel: znaleźć jedną bibliotekę (filię), w której da się wypożyczyć wszystkie 4 tomy cyklu
"O Mordimerze Madderdinie" Jacka Piekary na raz. Jeśli to niemożliwe — wybrać dla każdego
tomu z osobna najlepszą dostępną filię, zaczynając od tomu 1, z priorytetem dla **Filii 35**,
**Filii 14** i **Filii 62**, a dopiero potem dowolnej innej.

Wszystkie polecenia i wyniki poniżej pochodzą z prawdziwego uruchomienia `omnis-cli` na koncie
Biblioteki Raczyńskich (2026-08-02) — dostępność zmienia się codziennie, więc traktuj to jako
przykład metody, nie aktualny stan.

## Krok 1 — szeroki przegląd cyklu

```bash
omnis-cli --search "płomień i krzyż"
```

Wynik zwraca kilka osobnych "dzieł" (grupowanych po `frbrgroupid`), bo wyszukiwarka Primo
dopasowuje dowolne słowo z zapytania, nie tylko cały cykl:

- `Płomień i krzyż` — **to jest tom 1**, wydany pod tym tytułem w edycjach z 2008/2011/2012.
- `Płomień i krzyż. T. 1` — **to też tom 1**, ale w wznowieniach z 2015/2016/2018, które
  wydawca zaczął numerować dopiero po wydaniu kolejnych tomów.
- `Płomień i krzyż. T. 2`, `T. 3`, `T. 4` — tomy 2-4.
- Kilka niepowiązanych książek Piekary (np. "Kościany Galeon", "Sługa Boży", "Bicz Boży",
  "Młot na czarownice"), które trafiły do wyników, bo dzielą słowa "i"/"krzyż" albo autora.

**Ważne:** tom 1 jest rozbity na dwie osobne grupy wydań, bo Primo grupuje wydania po
identycznym tytule, a tytuł zmienił się między wznowieniami. Żeby sprawdzić dostępność
tomu 1, trzeba patrzeć na obie grupy (`Płomień i krzyż` **i** `Płomień i krzyż. T. 1`), a nie
tylko na tę z dopiskiem "T. 1".

## Krok 2 — sprawdzenie preferowanych filii po kolei

```bash
omnis-cli --search "płomień i krzyż" --branch "Filia 35"
omnis-cli --search "płomień i krzyż" --branch "Filia 14"
omnis-cli --search "płomień i krzyż" --branch "Filia 62"
```

Wyniki (fragmenty istotne dla cyklu, tabele z niepowiązanymi książkami pominięte):

**Filia 35:**

```
    📖 Płomień i krzyż — Piekara, Jacek
┏━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Edition    ┃ Year ┃ Branch   ┃ Status    ┃
┡━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ Wydanie I. │ 2008 │ Filia 35 │ Available │
└────────────┴──────┴──────────┴───────────┘
```

→ Filia 35 ma **tylko tom 1** (żadnej tabeli dla T. 2/T. 3/T. 4 — filia w ogóle nie ma tych
tomów w zbiorach).

**Filia 14:**

```
             📖 Płomień i krzyż — Piekara, Jacek
┏━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Edition      ┃ Year ┃ Branch   ┃ Status                    ┃
┡━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Wydanie III. │ 2012 │ Filia 14 │ Borrowed until 21/08/2026 │
└──────────────┴──────┴──────────┴───────────────────────────┘
```

→ Filia 14 też ma tylko tom 1, i akurat teraz jest wypożyczony (wróci 21.08.2026). Tomów
2-4 tam nie ma w ogóle.

**Filia 62:**

Brak jakiejkolwiek tabeli "Płomień i krzyż" — Filia 62 nie ma w zbiorach żadnego tomu tego
cyklu (pojawia się tylko przy niepowiązanych książkach Piekary).

**Wniosek kroku 2:** żadna z trzech preferowanych filii nie pozwala wypożyczyć nawet
kompletu — a Filia 62 odpada całkowicie dla tego cyklu.

## Krok 3 — poszerzenie poszukiwań poza preferowane filie

Skoro preferowane filie zawodzą, wracamy do pełnego wyniku z kroku 1 i przeglądamy wszystkie
filie występujące przy tomach 1-4, szukając takiej, która powtarza się we wszystkich pięciu
tabelach (`Płomień i krzyż`, `T. 1`, `T. 2`, `T. 3`, `T. 4`). Dwie filie/lokalizacje spełniają
to od razu:

```bash
omnis-cli --search "płomień i krzyż" --branch "Filia 56"
```

```
     📖 Płomień i krzyż — Piekara, Jacek     
│ Wydanie II. │ 2011 │ Filia 56 │ Available │

 📖 Płomień i krzyż. T. 1 — Piekara, Jacek  
│ Wydanie II. │ 2018 │ Filia 56 │ Available │

 📖 Płomień i krzyż. T. 2 — Piekara, Jacek  
│ Wydanie I.  │ 2018 │ Filia 56 │ Available │

 📖 Płomień i krzyż. T. 3 — Piekara, Jacek  
│ Wydanie I.  │ 2019 │ Filia 56 │ Available │

 📖 Płomień i krzyż. T. 4 — Piekara, Jacek  
│ Wydanie I.  │ 2023 │ Filia 56 │ Available │
```

```bash
omnis-cli --search "płomień i krzyż" --branch "BG - Wypożyczalnia"
```

```
                  📖 Płomień i krzyż — Piekara, Jacek
│ Wydanie II. │ 2011 │ BG - Wypożyczalnia │ Borrowed until 26/08/2026 │
│ Wydanie I.  │ 2008 │ BG - Wypożyczalnia │ Available                 │

      📖 Płomień i krzyż. T. 1 — Piekara, Jacek
│ -          │ 2016 │ BG - Wypożyczalnia │ Available │
│ Wydanie 4. │ 2015 │ BG - Wypożyczalnia │ Available │

      📖 Płomień i krzyż. T. 2 — Piekara, Jacek
│ Wydanie I. │ 2018 │ BG - Wypożyczalnia │ Available │

      📖 Płomień i krzyż. T. 3 — Piekara, Jacek
│ Wydanie I. │ 2019 │ BG - Wypożyczalnia │ Available │

      📖 Płomień i krzyż. T. 4 — Piekara, Jacek
│ Wydanie I. │ 2023 │ BG - Wypożyczalnia │ Available │
```

**Wynik:** obie lokalizacje mają **komplet 4 tomów dostępny od ręki**:

- **Filia 56** (ul. Galileusza 8) — wszystkie 4 tomy, każdy w jednym wydaniu dostępnym.
- **Główna siedziba — BG-Wypożyczalnia** (Aleje Marcinkowskiego 23) — też komplet; wydanie
  `Wydanie II.` tomu 1 jest akurat wypożyczone, ale `Wydanie I.` tego samego tomu jest wolne,
  więc realnie i tak wszystkie 4 tomy da się stamtąd wypożyczyć.

Żadna z nich nie jest z listy preferowanych (F35/F14/F62), ale to zgodnie z założeniem "jak
nie [ma w preferowanych], to mogą być inne" — Filia 56 jest praktycznym zwycięzcą.

## Krok 4 — plan awaryjny "od pierwszego tomu"

Gdyby żadna filia nie miała kompletu (a Filia 56 akurat go ma), procedura "od pierwszego
tomu licząc" wyglądałaby tak — dla każdego tomu osobno, w kolejności preferencji filii:

```bash
# Tom 1
omnis-cli --search "płomień i krzyż" --branch "Filia 35"   # jest -> wybieramy Filia 35
# Tom 2 (Filia 35/14/62 nie mają go wcale - patrz krok 2 dla F35/F14, i F62 brak w ogóle)
omnis-cli --search "płomień i krzyż. t. 2"                 # bez --branch, dowolna filia
# Tom 3
omnis-cli --search "płomień i krzyż. t. 3"
# Tom 4
omnis-cli --search "płomień i krzyż. t. 4"
```

W tym konkretnym przypadku ta ścieżka jest gorsza niż komplet z Filii 56/BG-Wypożyczalnia —
warto ją stosować tylko wtedy, gdy krok 3 faktycznie nie znajdzie żadnej wspólnej filii.

## Podsumowanie poleceń

| Cel | Polecenie |
|---|---|
| Przegląd całego cyklu, wszystkie filie | `omnis-cli --search "płomień i krzyż"` |
| Dostępność w konkretnej filii | `omnis-cli --search "płomień i krzyż" --branch "Filia 35"` |
| Wyszukanie jednego konkretnego tomu | `omnis-cli --search "płomień i krzyż. t. 2"` |

`--branch` filtruje po fragmencie nazwy filii (bez rozróżniania wielkości liter), więc
`--branch "filia 5"` złapie zarówno "Filia 50" jak i "Filia 56" — dla precyzyjnego trafienia
warto podawać pełny numer filii.
