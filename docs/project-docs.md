# SCIR — Stacja Pogodowa na Raspberry Pi Zero W
## Wstępna dokumentacja projektu

---

## 1. Opis projektu

Stacja pogodowa mierząca temperaturę, wilgotność, ciśnienie atmosferyczne (BME280) oraz natężenie światła (BH1750). Dane zbierane są przez Raspberry Pi Zero W i wysyłane cyklicznie do chmury ThingSpeak, gdzie prezentowane są jako wykresy w czasie rzeczywistym.

---

## 2. Architektura systemu

```
┌─────────────┐    I2C     ┌──────────────────┐    WiFi/HTTP    ┌─────────────┐
│   BME280    │───────────▶│                  │───────────────▶│  ThingSpeak  │
│ temp/wilg/  │            │  Raspberry Pi    │                │   (chmura)   │
│  ciśnienie  │            │    Zero W        │                │              │
└─────────────┘            │                  │                │  - wykresy   │
                           │  Python script   │                │  - eksport   │
┌─────────────┐    I2C     │  (cron co 60s)   │                │  - alerty    │
│   BH1750    │───────────▶│                  │                └─────────────┘
│  światło    │            └──────────────────┘                       │
└─────────────┘                    ▲                                  │
                                   │ SSH                              ▼
                            ┌──────────────┐                ┌─────────────┐
                            │  Komputer    │                │ Przeglądarka│
                            │  (programow.)│                │  (podgląd)  │
                            └──────────────┘                └─────────────┘
```

**Przepływ danych:**
1. Czujniki BME280 i BH1750 podłączone do Pi przez magistralę I2C
2. Skrypt Python odczytuje dane co 60 sekund
3. Dane wysyłane zapytaniem HTTP POST do ThingSpeak REST API
4. ThingSpeak generuje wykresy dostępne przez przeglądarkę

---

## 3. Lista komponentów do zamówienia

### Kluczowe komponenty

| # | Komponent | Opis | Ilość | Link |
|---|-----------|------|-------|------|
| 1 | **Raspberry Pi Zero WH Basic (zestaw)** | Mikrokomputer z WiFi, BT i wlutowanymi goldpinami GPIO + zasilacz| 1 szt. | [Botland](https://botland.com.pl/moduly-i-zestawy-raspberry-pi-zero/16722-zestaw-raspberry-pi-zero-wh-basic-5904422344948.html) |
| 2 | **Czujnik BME280** | Temperatura, wilgotność, ciśnienie (I2C/SPI, 3.3V) | 1 szt. | [Botland](https://botland.com.pl/czujniki-cisnienia/11803-bme280-czujnik-wilgotnosci-temperatury-oraz-cisnienia-110kpa-i2cspi-33v-5904422366179.html) |
| 3 | **Czujnik BH1750** | Natężenie światła w luksach (I2C) | 1 szt. | [Botland](https://botland.com.pl/czujniki-swiatla-i-koloru/2024-czujnik-natezenia-swiatla-bh1750-5904422373283.html) |
| 4 | **Karta microSD Goodram 16GB** | Class 10, UHS-I, 100MB/s + adapter | 1 szt. | [Botland](https://botland.com.pl/karty-pamieci-microsd-sd/2123-karta-pamieci-goodram-m1aa-microsd-16gb-100mbs-uhs-i-klasa-10-z-adapterem-5908267930137.html) |

### Elementy do połączenia (nie wymaga lutowania)

| # | Komponent | Opis | Ilość |
|---|-----------|------|-------|
| 5 | **Płytka stykowa (breadboard)** | Mała, 400 otworów — do prototypowania | 1 szt. |
| 6 | **Kabelki jumper żeńsko-żeńskie** | Do połączenia Pi z czujnikami | ~10 szt. |

---

## 4. Schemat połączeń

Oba czujniki komunikują się przez I2C — współdzielą te same 4 piny:

```
Raspberry Pi Zero W          BME280          BH1750
─────────────────          ─────────        ──────────
Pin 1  (3.3V)  ──────────▶ VIN ──────────▶ VCC
Pin 6  (GND)   ──────────▶ GND ──────────▶ GND
Pin 3  (SDA/GPIO2) ──────▶ SDA ──────────▶ SDA
Pin 5  (SCL/GPIO3) ──────▶ SCL ──────────▶ SCL
```

### Wizualizacja na płytce stykowej

```
         Raspberry Pi Zero W (GPIO header)
    ┌─────────────────────────────────────────┐
    │ [1:3.3V] [2:5V]                        │
    │ [3:SDA ] [4:5V]                        │
    │ [5:SCL ] [6:GND]                       │
    │ [7     ] [8    ]                        │
    │  ...                                    │
    └─────────────────────────────────────────┘
        │  │  │  │
        │  │  │  └──── GND (czarny kabelek)
        │  │  └─────── SCL (żółty kabelek)
        │  └────────── SDA (zielony kabelek)
        └───────────── 3.3V (czerwony kabelek)
                │  │  │  │
        ┌───────┴──┴──┴──┴───────┐
        │      Płytka stykowa     │
        │                         │
        │  ┌───────┐  ┌───────┐  │
        │  │BME280 │  │BH1750 │  │
        │  │VIN────│──│VCC────│──│── 3.3V
        │  │GND────│──│GND────│──│── GND
        │  │SDA────│──│SDA────│──│── SDA
        │  │SCL────│──│SCL────│──│── SCL
        │  └───────┘  └───────┘  │
        └─────────────────────────┘
```

**Kluczowe informacje:**
- NIE potrzebujecie żadnych rezystorów — moduły BME280 i BH1750 mają wbudowane pull-up rezystory
- Oba czujniki podłączone równolegle do tych samych 4 pinów
- Rozróżnianie czujników odbywa się przez adresy I2C (BME280: 0x76, BH1750: 0x23)
- Łącznie podłączacie tylko 4 kabelki z Pi do płytki stykowej

---

## 5. Instrukcja realizacji — krok po kroku

---

### KROK 1: Konfiguracja ThingSpeak (na komputerze, bez Pi)

Zaczynamy od chmury, bo potrzebujemy klucza API do skryptu, a to można zrobić zanim przyjdą komponenty.

1. Wejść na https://thingspeak.com i zalogować się kontem uczelnianym MathWorks
2. Kliknąć **Channels → New Channel**
3. Wypełnić pola:
   - Name: `Stacja Pogodowa`
   - Field 1: `Temperature (°C)`
   - Field 2: `Humidity (%)`
   - Field 3: `Pressure (hPa)`
   - Field 4: `Light (lux)`
4. Zapisać kanał
5. Przejść do zakładki **API Keys**
6. Skopiować **Write API Key** — będzie potrzebny w kroku 6

**Dlaczego ThingSpeak?** Darmowy z kontem uczelnianym, automatyczne wykresy, prosty REST API (jedno zapytanie HTTP POST), eksport do CSV. Zdecydowanie najczęściej używany przez studentów w poprzednich semestrach i sugerowany przez wykładowcę w materiałach.

---

### KROK 2: Instalacja systemu na karcie microSD (na komputerze, bez Pi)

1. Pobrać i zainstalować **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Włożyć kartę microSD do komputera (przez adapter jeśli trzeba)
3. Uruchomić Imager i wybrać:
   - System: **Raspberry Pi OS Lite (64-bit)** — wersja bez pulpitu, lżejsza
   - Karta: wasza microSD
4. **Kluczowe** — przed zapisem kliknąć ikonę zębatki (⚙) i skonfigurować:
   - ✅ Włączyć SSH
   - ✅ Ustawić login i hasło (np. `pi` / `wasze_haslo`)
   - ✅ Wpisać nazwę i hasło domowej sieci WiFi
   - ✅ Ustawić hostname (np. `stacja-pogodowa`)
5. Kliknąć **Zapisz** i poczekać aż obraz zostanie wgrany na kartę

---

### KROK 3: Pierwsze uruchomienie Pi i połączenie SSH (komputer + Pi)

1. Włożyć kartę microSD do Raspberry Pi Zero WH
2. Podłączyć zasilacz micro-USB do Pi
3. Odczekać **~2 minuty** aż Pi się uruchomi i połączy z WiFi
4. Na komputerze otworzyć terminal i połączyć się:

```bash
ssh pi@stacja-pogodowa.local
```

Jeśli hostname nie działa, sprawdzić adres IP Pi w ustawieniach routera i użyć:

```bash
ssh pi@192.168.1.XXX
```

5. Zaakceptować fingerprint (wpisać `yes`) i podać hasło ustawione w kroku 2

Od teraz macie terminal Pi na swoim komputerze.

---

### KROK 4: Konfiguracja Pi — włączenie I2C i aktualizacja systemu

```bash
# Aktualizacja systemu
sudo apt update && sudo apt upgrade -y

# Włączenie interfejsu I2C
sudo raspi-config
# → Interface Options → I2C → Enable

# Instalacja narzędzi I2C
sudo apt install -y i2c-tools python3-pip python3-smbus

# Restart Pi
sudo reboot
```

Po restarcie połączyć się ponownie przez SSH.

---

### KROK 5: Fizyczne podłączenie czujników (przy wyłączonym Pi!)

⚠️ **Przed podłączaniem czujników odłączyć zasilanie Pi!**

1. Wpiąć czujniki BME280 i BH1750 w płytkę stykową
2. Połączyć kabelkami jumper zgodnie ze schematem z rozdziału 4:
   - Pin 1 (3.3V) → VIN/VCC obu czujników
   - Pin 6 (GND) → GND obu czujników
   - Pin 3 (SDA) → SDA obu czujników
   - Pin 5 (SCL) → SCL obu czujników
3. Sprawdzić dwukrotnie czy nic nie jest na odwrót
4. Podłączyć zasilanie Pi

---

### KROK 6: Weryfikacja czujników i instalacja bibliotek

Po podłączeniu zasilania, połączyć się ponownie przez SSH i sprawdzić czy Pi widzi czujniki:

```bash
i2cdetect -y 1
```

Powinniście zobaczyć adresy **0x23** (BH1750) i **0x76** (BME280) w tabeli.

Następnie zainstalować biblioteki Python:

```bash
pip3 install adafruit-circuitpython-bme280 adafruit-circuitpython-bh1750 requests
```

---

### KROK 7: Utworzenie i uruchomienie skryptu

Utworzyć plik skryptu:

```bash
nano /home/pi/weather_station.py
```

Wkleić poniższy kod (podmienić `WASZ_WRITE_API_KEY` na klucz z kroku 1):

```python
import time
import board
import requests
import adafruit_bme280.advanced as adafruit_bme280
import adafruit_bh1750

# --- Konfiguracja ThingSpeak ---
THINGSPEAK_API_KEY = "WASZ_WRITE_API_KEY"
THINGSPEAK_URL = "https://api.thingspeak.com/update"

# --- Inicjalizacja czujników ---
i2c = board.I2C()
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
bh1750 = adafruit_bh1750.BH1750(i2c, address=0x23)

def read_sensors():
    """Odczytuje dane ze wszystkich czujników."""
    return {
        "temperature": round(bme280.temperature, 2),
        "humidity": round(bme280.relative_humidity, 2),
        "pressure": round(bme280.pressure, 2),
        "light": round(bh1750.lux, 2)
    }

def send_to_thingspeak(data):
    """Wysyła dane do chmury ThingSpeak."""
    payload = {
        "api_key": THINGSPEAK_API_KEY,
        "field1": data["temperature"],
        "field2": data["humidity"],
        "field3": data["pressure"],
        "field4": data["light"]
    }
    try:
        response = requests.post(THINGSPEAK_URL, data=payload)
        if response.status_code == 200:
            print(f"OK — wysłano: {data}")
        else:
            print(f"Błąd HTTP: {response.status_code}")
    except Exception as e:
        print(f"Błąd połączenia: {e}")

# --- Pętla główna ---
if __name__ == "__main__":
    print("Stacja pogodowa uruchomiona!")
    while True:
        data = read_sensors()
        send_to_thingspeak(data)
        time.sleep(60)  # ThingSpeak przyjmuje dane co min. 15 sekund
```

Zapisać plik (`Ctrl+O`, `Enter`, `Ctrl+X`) i uruchomić testowo:

```bash
python3 /home/pi/weather_station.py
```

Jeśli widzicie komunikat `OK — wysłano: {...}` — wszystko działa!

---

### KROK 8: Weryfikacja danych w ThingSpeak

1. Wejść na https://thingspeak.com i otworzyć swój kanał
2. Sprawdzić czy na wykresach pojawiają się dane
3. Poczekać kilka minut żeby zebrało się więcej punktów
4. Opcjonalnie dostosować wykresy — zakres czasu, uśrednianie danych

---

### KROK 9: Automatyczne uruchamianie skryptu po starcie Pi

Żeby stacja działała po każdym włączeniu Pi bez ręcznego uruchamiania:

```bash
crontab -e
```

Dodać na końcu pliku linię:

```
@reboot sleep 30 && python3 /home/pi/weather_station.py &
```

Zapisać i zamknąć. Od teraz po każdym restarcie Pi skrypt uruchomi się automatycznie po 30 sekundach.

---

## 6. Tabelka dla wykładowcy

| Pole | Wartość |
|------|---------|
| **Sprzęt** | Raspberry Pi Zero W, BME280, BH1750 |
| **Komunikacja** | HTTP (WiFi) |
| **Chmura** | ThingSpeak |

---

## 7. Harmonogram realizacji (propozycja)

| Etap | Opis | Czas |
|------|------|------|
| 1 | Zamówienie komponentów, konfiguracja ThingSpeak (krok 1) | 1 dzień |
| 2 | Instalacja systemu na karcie SD, pierwsze połączenie SSH (kroki 2–4) | 1 dzień |
| 3 | Podłączenie czujników, weryfikacja, instalacja bibliotek (kroki 5–6) | 1 dzień |
| 4 | Wgranie skryptu, integracja z ThingSpeak, testy (kroki 7–8) | 1 dzień |
| 5 | Automatyzacja, poprawki, testy końcowe (krok 9) | 1 dzień |
| 6 | Przygotowanie prezentacji | 1 dzień |

**Łączny szacowany czas: ~6 dni roboczych (na spokojnie)**

---

## 8. Potencjalne rozszerzenia (na dodatkowe punkty)

- Alerty email/Telegram gdy temperatura przekroczy próg
- Lokalna strona WWW na Pi (Flask) jako alternatywny podgląd
- Logowanie danych lokalnie do SQLite jako backup