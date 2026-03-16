# Sprawozdanie — Stacja Pogodowa na Raspberry Pi Zero W

**Przedmiot:** SCIR
**Autorzy:** Oliwier Szypczyn, Kacper Multan
**Data rozpoczęcia:** 2026-03-13

---

## Spis treści

- [Sprawozdanie — Stacja Pogodowa na Raspberry Pi Zero W](#sprawozdanie--stacja-pogodowa-na-raspberry-pi-zero-w)
  - [Spis treści](#spis-treści)
  - [Krok 1 — Konfiguracja ThingSpeak](#krok-1--konfiguracja-thingspeak)
    - [1.1 Rejestracja konta MathWorks](#11-rejestracja-konta-mathworks)
    - [1.2 Utworzenie kanału ThingSpeak](#12-utworzenie-kanału-thingspeak)
    - [1.3 Widok utworzonego kanału](#13-widok-utworzonego-kanału)
    - [1.4 Pozyskanie klucza API](#14-pozyskanie-klucza-api)
  - [Krok 2 — Instalacja systemu na karcie microSD](#krok-2--instalacja-systemu-na-karcie-microsd)
    - [2.1 Pobranie Raspberry Pi Imager](#21-pobranie-raspberry-pi-imager)
    - [2.2 Wybór systemu operacyjnego](#22-wybór-systemu-operacyjnego)
    - [2.3 Wybór karty microSD](#23-wybór-karty-microsd)
    - [2.4 Konfiguracja wstępna (OS Customisation)](#24-konfiguracja-wstępna-os-customisation)
    - [2.5 Zapis obrazu na kartę](#25-zapis-obrazu-na-kartę)
    - [2.6 Weryfikacja i zakończenie](#26-weryfikacja-i-zakończenie)
  - [Krok 3 — Pierwsze uruchomienie Pi i połączenie SSH](#krok-3--pierwsze-uruchomienie-pi-i-połączenie-ssh)
    - [3.1 Włożenie karty i uruchomienie Pi](#31-włożenie-karty-i-uruchomienie-pi)
    - [3.2 Połączenie SSH z komputera](#32-połączenie-ssh-z-komputera)
  - [Krok 4 — Konfiguracja Pi (I2C, aktualizacja)](#krok-4--konfiguracja-pi-i2c-aktualizacja)
    - [4.1 Aktualizacja systemu](#41-aktualizacja-systemu)
    - [4.2 Włączenie interfejsu I2C](#42-włączenie-interfejsu-i2c)
    - [4.3 Instalacja narzędzi I2C i bibliotek](#43-instalacja-narzędzi-i2c-i-bibliotek)
    - [4.4 Restart i weryfikacja](#44-restart-i-weryfikacja)

---

## Krok 1 — Konfiguracja ThingSpeak

**Cel:** Założenie konta MathWorks, utworzenie kanału ThingSpeak i pozyskanie klucza API potrzebnego do wysyłania danych z czujników.

### 1.1 Rejestracja konta MathWorks

Utworzono konto studenckie MathWorks na stronie https://www.mathworks.com/mwaccount/register, podając uczelniany adres e-mail.

### 1.2 Utworzenie kanału ThingSpeak

Po zalogowaniu na https://thingspeak.com przejśto do **Channels → New Channel** i wypełniono formularz:

| Pole | Wartość |
|------|---------|
| **Channel Name** | `RPi Zero W Weather Station` |
| **Description** | `Outdoor weather monitoring station powered by Raspberry Pi Zero W. Collects temperature, humidity, atmospheric pressure (BME280) and light intensity (BH1750) via I2C, reporting every 60 seconds.` |
| **Field 1** | `Temperature (°C)` |
| **Field 2** | `Humidity (%)` |
| **Field 3** | `Pressure (hPa)` |
| **Field 4** | `Light (lux)` |
| **Metadata** | `{"sensors":["BME280","BH1750"],"board":"Raspberry Pi Zero WH","protocol":"I2C","interval_s":60}` |
| **Tags** | `raspberry pi, weather station, bme280, bh1750, iot, i2c, warsaw` |
| **Latitude** | `52.2220` |
| **Longitude** | `21.0070` |
| **Elevation** | `112` |

![Tworzenie kanału](img/02_thingspeak_nowy_kanal.png)

### 1.3 Widok utworzonego kanału

Po zapisaniu kanału ThingSpeak wygenerował pustą stronę z czterema wykresami (po jednym na każde pole). Wykresy zaczną pokazywać dane po uruchomieniu skryptu na Raspberry Pi.

![Pusty kanał](img/03_thingspeak_pusty_kanal.png)

### 1.4 Pozyskanie klucza API

W zakładce **API Keys** skopiowano **Write API Key**, który jest niezbędny do autoryzacji zapytań HTTP POST wysyłanych z Raspberry Pi. Klucz zapisano w pliku `.env` w repozytorium projektu (plik dodany do `.gitignore`, aby nie trafił do publicznego repozytorium).

---

## Krok 2 — Instalacja systemu na karcie microSD

**Cel:** Wgranie systemu Raspberry Pi OS Lite na kartę microSD z wstępną konfiguracją SSH, WiFi i nazwy hosta — aby Pi po pierwszym uruchomieniu automatycznie połączyło się z siecią i było dostępne zdalnie.

### 2.1 Pobranie Raspberry Pi Imager

Pobrano i zainstalowano narzędzie **Raspberry Pi Imager** ze strony https://www.raspberrypi.com/software/. Imager pozwala na łatwe wgranie systemu operacyjnego na kartę microSD wraz z wstępną konfiguracją.

![Ekran startowy Imager](img/04_imager_start.png)

### 2.2 Wybór systemu operacyjnego

W Imager wybrano:
- **Device:** Raspberry Pi Zero W
- **System:** Raspberry Pi OS Lite (32-bit) — wersja bez środowiska graficznego, lżejsza i wystarczająca do pracy przez SSH (Pi Zero W ma procesor ARMv6, który nie obsługuje 64-bit)

![Wybór systemu](img/05_imager_wybor_os.png)

### 2.3 Wybór karty microSD

Włożono kartę microSD Goodram 16GB do komputera przez adapter i wybrano ją jako cel zapisu w Imager.

![Wybór karty](img/06_imager_wybor_karty.png)

### 2.4 Konfiguracja wstępna (OS Customisation)

Przed zapisem kliknięto **Edit Settings** i skonfigurowano następujące parametry:

**Zakładka General:**

| Parametr | Wartość |
|----------|---------|
| **Hostname** | `weather-station` |
| **Username** | `pi` |
| **Password** | *(ustawione, ukryte ze względów bezpieczeństwa)* |
| **SSID WiFi** | *(nazwa domowej sieci WiFi)* |
| **Hasło WiFi** | *(ukryte)* |
| **Locale** | `Europe/Warsaw`, klawiatura `pl` |

![Ustawienia ogólne](img/07_imager_ustawienia_ogolne.png)

**Zakładka Services:**

Włączono **SSH** z uwierzytelnianiem hasłem — umożliwia zdalne połączenie z Pi od pierwszego uruchomienia.

![Ustawienia SSH](img/09_imager_ustawienia_ssh.png)

### 2.5 Zapis obrazu na kartę

Po zatwierdzeniu konfiguracji kliknięto **Zapisz** i rozpoczął się proces zapisu systemu na kartę microSD.

![Zapis w toku](img/10_imager_zapis.png)

### 2.6 Weryfikacja i zakończenie

Imager automatycznie zweryfikował poprawność zapisu. Po wyświetleniu komunikatu o sukcesie bezpiecznie wyjęto kartę microSD z komputera.

![Zapis zakończony](img/11_imager_sukces.png)

**Karta microSD jest gotowa do włożenia do Raspberry Pi Zero W** — system przy pierwszym uruchomieniu automatycznie połączy się z siecią WiFi i będzie dostępny przez SSH pod adresem `weather-station.local`.

---

## Krok 3 — Pierwsze uruchomienie Pi i połączenie SSH

**Cel:** Uruchomienie Raspberry Pi z przygotowaną kartą microSD, połączenie się z nim zdalnie przez SSH i potwierdzenie, że Pi jest dostępne w sieci.

### 3.1 Włożenie karty i uruchomienie Pi

Włożono kartę microSD do slotu w Raspberry Pi Zero WH i podłączono zasilacz micro-USB. Zielona dioda LED na płytce zaczęła migać, co oznacza odczyt z karty SD i uruchamianie systemu.

![Pi z kartą SD i zasilaczem](img/12_pi_pierwsze_uruchomienie.png)

### 3.2 Połączenie SSH z komputera

Po odczekaniu ~2 minut (czas na boot i połączenie z WiFi) otworzono terminal na komputerze i połączono się z Pi:

```bash
ssh pi@weather-station.local
```

Przy pierwszym połączeniu terminal wyświetlił ostrzeżenie o nieznanym hoście (fingerprint). Wpisano `yes`, aby dodać Pi do listy znanych hostów, a następnie podano hasło ustawione w Imager. Po zalogowaniu wyświetlił się prompt systemowy Raspberry Pi OS, potwierdzając udane połączenie. Od tego momentu cała dalsza konfiguracja Pi odbywa się zdalnie przez SSH z komputera.

![Połączenie SSH — fingerprint](img/13_ssh_fingerprint.png)

---

## Krok 4 — Konfiguracja Pi (I2C, aktualizacja)

**Cel:** Aktualizacja systemu, włączenie magistrali I2C potrzebnej do komunikacji z czujnikami oraz instalacja niezbędnych narzędzi.

### 4.1 Aktualizacja systemu

Wykonano pełną aktualizację pakietów systemowych:

```bash
sudo apt update && sudo apt upgrade -y
```

![Aktualizacja systemu](img/15_apt_update.png)

### 4.2 Włączenie interfejsu I2C

Uruchomiono narzędzie konfiguracyjne i włączono I2C:

```bash
sudo raspi-config
```

W menu nawigowano: **Interface Options → I2C → Enable**

![raspi-config — włączenie I2C](img/16_raspi_config_i2c.png)

### 4.3 Instalacja narzędzi I2C i bibliotek

Zainstalowano pakiety potrzebne do diagnostyki I2C i komunikacji z czujnikami przez Python:

```bash
sudo apt install -y i2c-tools python3-pip python3-smbus
```

![Instalacja narzędzi I2C](img/17_apt_install_i2c.png)

### 4.4 Restart i weryfikacja

Zrestartowano Pi, aby zmiany konfiguracji I2C zostały zastosowane:

```bash
sudo reboot
```

Po ~1 minucie ponownie połączono się przez SSH i zweryfikowano, że moduł I2C jest załadowany:

```bash
ls /dev/i2c*
```

Wyświetlenie `/dev/i2c-1` potwierdza, że interfejs I2C działa poprawnie.

![Weryfikacja I2C po restarcie](img/18_i2c_weryfikacja.png)

---

<!-- Dalsze kroki będą uzupełniane w miarę realizacji projektu -->
