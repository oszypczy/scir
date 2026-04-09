# Etap 4 - Analiza i wizualizacja danych stacji pogodowej

## Kontekst

Prowadzacy wymaga, aby Etap 4 wykraczal poza prosta prezentacje wynikow - trzeba wykorzystac zebrane dane do obliczenia statystyk, korelacji i innych pochodnych metryk. Stacja zbiera 4 parametry co 60s: temperature (C), wilgotnosc (%), cisnienie (hPa), natezenie swiatla (lux). Dane sa w chmurze ThingSpeak.

## Plan: nowy skrypt `src/analyze_data.py`

Jeden skrypt Python, ktory pobiera dane z ThingSpeak, analizuje je i generuje wykresy + raport tekstowy.

### 1. Pobranie danych z ThingSpeak

- REST API: `https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?results=8000`
- Paginacja po datach (limit 8000 rekordow/zapytanie)
- Konwersja do pandas DataFrame
- Dodac `THINGSPEAK_CHANNEL_ID` do `.env`

### 2. Czyszczenie danych

- Usuniecie outlierow (metoda IQR, 3*IQR)
- Walidacja zakresow fizycznych (temp -30..+50, wilg 0-100%, cisn 900-1100 hPa)
- Forward-fill malych luk (do 5 min)

### 3. Metryki pochodne

| Metryka | Wzor / metoda | Po co |
|---------|---------------|-------|
| **Punkt rosy** | Wzor Magnusa: `alpha = (17.27*T)/(237.7+T) + ln(RH/100)` | Bliskosc temp do punktu rosy = ryzyko mgly |
| **Klasyfikacja dzien/noc** | Prog swiatla: <10 lux = noc | Analiza krosowa miedzy czujnikami |
| **Trend cisnienia** | Roznica kroczaca 3h | Prosta prognoza pogody (spadek = pogorszenie) |
| **Indeks komfortu Thoma** | `DI = T - 0.55*(1-0.01*RH)*(T-14.5)` | Biometeorologia |

### 4. Analiza statystyczna

- **Statystyki opisowe**: srednia, mediana, odch. std., min, max, Q1, Q3 - dla kazdego czujnika
- **Agregacje dobowe**: srednie, min, max dzienne; amplituda dobowa temperatury
- **Profile godzinowe**: sredni przebieg parametrow w ciagu doby (grupowanie po godzinie 0-23)
- **Macierz korelacji Pearsona**: temperatura vs wilgotnosc (oczekiwana ujemna), swiatlo vs temperatura (oczekiwana dodatnia), cisnienie vs temperatura
- **Porownanie dzien vs noc**: statystyki z podzialem na dzien/noc (dzieki czujnikowi swiatla)
- **Detekcja anomalii**: z-score > 3, nagly skok wartosci

### 5. Wizualizacje (10 wykresow PNG)

| # | Wykres | Opis |
|---|--------|------|
| 1 | **Przebieg czasowy** | 4 subploty: temp, wilg, cisn, swiatlo - caly zakres dat |
| 2 | **Profil dobowy** | Srednie godzinowe (0-23h) z pasmem odch. std. |
| 3 | **Macierz korelacji** | Heatmapa z wartosciami liczbowymi |
| 4 | **Scatter korelacji** | 2x2: temp-wilg, temp-cisn, swiatlo-temp, wilg-punkt_rosy z linia regresji i R^2 |
| 5 | **Histogramy** | Rozklady wartosci 4 czujnikow z zaznaczona srednia/mediana |
| 6 | **Dzien vs noc** | Box ploty temp i wilgotnosci: porownanie dzien/noc |
| 7 | **Trend cisnienia** | Cisnienie + kolorowe tlo (zielone=rosnie, czerwone=spada) |
| 8 | **Punkt rosy** | Temperatura i punkt rosy na jednym wykresie, zacieniony obszar miedzy nimi |
| 9 | **Mapa cieplna** | Godzina (x) vs dzien (y) vs temperatura (kolor) |
| 10 | **Anomalie** | Przebieg temp z zaznaczonymi anomaliami na czerwono |

### 6. Raport tekstowy

Generowany automatycznie do `output/report.txt`:
- Podsumowanie danych (zakres dat, liczba pomiarow)
- Tabela statystyk opisowych
- Najsilniejsze korelacje
- Podsumowanie metryk pochodnych
- Rozklad trendu cisnienia (% czasu: rosnie/spada/stabilne)
- Porownanie dzien vs noc
- Raport anomalii

## Zmiany w plikach

| Plik | Zmiana |
|------|--------|
| `src/analyze_data.py` | **NOWY** - caly skrypt analizy (~400-500 linii) |
| `requirements.txt` | Dodac: `numpy`, `pandas` |
| `.env` | Dodac: `THINGSPEAK_CHANNEL_ID=<uzupelnic>` |
| `.gitignore` | Dodac: `output/` |

## Weryfikacja

1. Uzupelnic `THINGSPEAK_CHANNEL_ID` w `.env`
2. `pip install -r requirements.txt`
3. `python src/analyze_data.py`
4. Sprawdzic `output/charts/` - powinno byc 10 plikow PNG
5. Sprawdzic `output/report.txt` - raport tekstowy ze statystykami
6. Wykresy i raport wlozyc do sprawozdania Etapu 4

## Kolejnosc implementacji

1. Aktualizacja `requirements.txt` i `.gitignore`
2. Szkielet skryptu: config, pobieranie danych, czyszczenie
3. Metryki pochodne
4. Analiza statystyczna i korelacje
5. Wszystkie wizualizacje
6. Generowanie raportu tekstowego
7. Funkcja `main()` spinajaca wszystko
