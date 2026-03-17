#!/usr/bin/env python3
"""
test_led_i2c.py — Skrypt testowy dla Raspberry Pi Zero W
Etap 1: Weryfikacja działania GPIO (LED ACT) oraz magistrali I2C.

Autorzy: Oliwier Szypczyn, Kacper Multan
Projekt: Stacja Pogodowa na Raspberry Pi Zero W (SCIR)
"""

import time
import subprocess
import sys


def blink_act_led(times: int = 5, interval: float = 0.4) -> None:
    """Miga wbudowanym zielonym LED-em ACT na Raspberry Pi."""

    led_path = "/sys/class/leds/ACT"
    trigger_path = f"{led_path}/trigger"
    brightness_path = f"{led_path}/brightness"

    # Wyłącz domyślny trigger (normalnie LED miga przy odczycie SD)
    try:
        with open(trigger_path, "w") as f:
            f.write("none")
    except PermissionError:
        print("Brak uprawnień — uruchom skrypt z sudo:")
        print("  sudo python3 test_led_i2c.py")
        sys.exit(1)

    print(f"Miganie LED-em ACT ({times} razy)...")
    for i in range(times):
        # Włącz LED
        with open(brightness_path, "w") as f:
            f.write("1")
        print(f"  [{i+1}/{times}] LED ON  ●")
        time.sleep(interval)

        # Wyłącz LED
        with open(brightness_path, "w") as f:
            f.write("0")
        print(f"  [{i+1}/{times}] LED OFF ○")
        time.sleep(interval)

    # Przywróć domyślny trigger (miganie przy aktywności SD)
    with open(trigger_path, "w") as f:
        f.write("mmc0")
    print("Przywrócono domyślny tryb LED (aktywność SD).\n")


def scan_i2c_bus() -> None:
    """Skanuje magistralę I2C-1 i wyświetla znalezione urządzenia."""

    print("Skanowanie magistrali I2C-1...")
    try:
        result = subprocess.run(
            ["i2cdetect", "-y", "1"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)

        # Sprawdź, czy znaleziono jakiekolwiek urządzenia (adresy inne niż --)
        lines = result.stdout.strip().split("\n")[1:]  # Pomiń nagłówek
        found = []
        for line in lines:
            parts = line.split(":")[1].split() if ":" in line else []
            for part in parts:
                if part != "--":
                    found.append(f"0x{part}")

        if found:
            print(f"Znalezione urządzenia I2C: {', '.join(found)}")
            print("(BME280 zwykle: 0x76 lub 0x77, BH1750 zwykle: 0x23 lub 0x5c)")
        else:
            print("Brak urządzeń I2C — to normalne, czujniki nie są jeszcze podłączone.")
            print("Po podłączeniu BME280 i BH1750 powinny pojawić się adresy 0x76 i 0x23.")

    except FileNotFoundError:
        print("Komenda i2cdetect nie znaleziona. Zainstaluj: sudo apt install i2c-tools")
    except subprocess.CalledProcessError as e:
        print(f"Błąd skanowania I2C: {e.stderr}")


def main() -> None:
    print("=" * 50)
    print("  Test GPIO i I2C — Stacja Pogodowa RPi Zero W")
    print("=" * 50)
    print()

    # Test 1: Miganie LED-em
    blink_act_led(times=5, interval=0.4)

    # Test 2: Skan I2C
    scan_i2c_bus()

    print("=" * 50)
    print("  Testy zakończone!")
    print("=" * 50)


if __name__ == "__main__":
    main()
