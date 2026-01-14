from __future__ import annotations

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import CoreService

from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def print_menu(logged_in: bool) -> None:
    print("\nValutaTrade Hub")
    if not logged_in:
        print(
            """
Доступные команды:
1. Регистрация
2. Вход
0. Выход
"""
        )
    else:
        print(
            """
Доступные команды:
1. Показать портфель
2. Купить валюту
3. Продать валюту
4. Получить курс
5. Обновить курсы
6. Выйти из аккаунта
0. Выход
"""
        )


def input_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Значение не может быть пустым")


def input_float(prompt: str) -> float:
    while True:
        try:
            value = float(input(prompt))
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("Введите положительное число")


def run_cli() -> None:
    core = CoreService()

    while True:
        logged_in = core.session is not None
        print_menu(logged_in)

        choice = input("Введите номер команды: ").strip()

        try:
            if not logged_in:
                match choice:
                    case "1":  # register
                        username = input_non_empty("Имя пользователя: ")
                        password = input_non_empty("Пароль: ")
                        print(core.register(username, password))

                    case "2":  # login
                        username = input_non_empty("Имя пользователя: ")
                        password = input_non_empty("Пароль: ")
                        print(core.login(username, password))

                    case "0":
                        print("Выход из программы.")
                        return

                    case _:
                        print("Неизвестная команда")

            else:
                session = core.require_login()

                match choice:
                    case "1":  # show portfolio
                        result = core.show_portfolio()
                        if result["empty"]:
                            print("Портфель пуст")
                        else:
                            print(f"\nПортфель пользователя '{session.username}' (база: {result['base']}):")
                            for row in result["rows"]:
                                print(
                                    f"- {row['currency']}: {row['balance']:.4f} → "
                                    f"{row['value_in_base']:.2f} {result['base']}"
                                )
                            print(f"ИТОГО: {result['total']:.2f} {result['base']}")

                    case "2":  # buy
                        currency = input_non_empty("Код валюты: ").upper()
                        amount = input_float("Количество: ")
                        res = core.buy(session.user_id, currency, amount)
                        print(
                            f"Покупка выполнена: {currency}, "
                            f"было {res['before']:.4f} → стало {res['after']:.4f}"
                        )

                    case "3":  # sell
                        currency = input_non_empty("Код валюты: ").upper()
                        amount = input_float("Количество: ")
                        res = core.sell(session.user_id, currency, amount)
                        print(
                            f"Продажа выполнена: {currency}, "
                            f"было {res['before']:.4f} → стало {res['after']:.4f}"
                        )

                    case "4":  # get-rate
                        from_c = input_non_empty("Из валюты: ").upper()
                        to_c = input_non_empty("В валюту: ").upper()
                        rate, updated, _ = core.get_rate(from_c, to_c, allow_stale=True)
                        print(f"Курс {from_c} → {to_c}: {rate:.8f} (обновлено {updated})")

                    case "5":  # update-rates
                        print("Обновление курсов...")

                        config = ParserConfig()
                        storage = RatesStorage()
                        updater = RatesUpdater(
                            clients=[
                                ("CoinGecko", CoinGeckoClient(config)),
                                ("ExchangeRate-API", ExchangeRateApiClient(config)),
                            ],
                            storage=storage,
                        )

                        result = updater.run_update()
                        if result.get("status") == "ok":
                            print(f"Курсы обновлены успешно. Обновлено: {result.get('updated')}")
                        else:
                            print(f"Обновление завершено с ошибками. Обновлено: {result.get('updated')}")

                    case "6":  # logout
                        core.logout()
                        print("Вы вышли из аккаунта")

                    case "0":
                        print("Выход из программы.")
                        return

                    case _:
                        print("Неизвестная команда")

        except (ApiRequestError, CurrencyNotFoundError, InsufficientFundsError) as e:
            print(f"Ошибка: {e}")
        except PermissionError as e:
            print(e)
        except KeyboardInterrupt:
            print("\nВыход.")
            return
