import asyncio
import os
import json
from dotenv import load_dotenv
from omnis.client import OmnisClient


async def main():
    load_dotenv()
    username = os.getenv("OMNIS_USERNAME")
    password = os.getenv("OMNIS_PASSWORD")

    if not username or not password:
        print("Error: OMNIS_USERNAME and OMNIS_PASSWORD must be set in .env file")
        return

    # Optional overrides for testing different tenants
    base_url = os.getenv("OMNIS_BASE_URL", "https://omnis-br.primo.exlibrisgroup.com")
    institution = os.getenv("OMNIS_INSTITUTION", "48OMNIS_BRP")
    view = os.getenv("OMNIS_VIEW", "48OMNIS_BRP:BRACZ")

    print(f"Targeting Tenant: {institution}")
    print(f"Base URL: {base_url}")
    print(f"View: {view}")

    client = OmnisClient(base_url)
    try:
        print(f"Logging in as {username}...")
        await client.login(username, password, institution, view)
        print("Logged in successfully.")

        headers = {"Authorization": f"Bearer {client.token}"}

        print("DEBUG: Fetching counters...")
        response = await client.client.get(
            f"{client.base_url}/primaws/rest/priv/myaccount/counters", params={"lang": "pl"}, headers=headers
        )
        print(f"Counters: {response.text}")

        print("DEBUG: Fetching personal settings...")
        response = await client.client.get(
            f"{client.base_url}/primaws/rest/priv/myaccount/personal_settings", params={"lang": "pl"}, headers=headers
        )
        print(f"Settings: {response.text}")

        print("\nFetching user info via client...")
        user_info = await client.get_user_info()
        print(f"User: {user_info.display_name} ({user_info.user_name})")
        print(
            f"Loans: {user_info.loans_count}, Requests: {user_info.requests_count}, Fines: {user_info.fines_amount} {user_info.fines_currency}"
        )

        print("\nFetching configuration...")
        config_url = f"{client.base_url}/primaws/rest/pub/configuration/vid/48OMNIS_BRP:BRACZ"
        response = await client.client.get(config_url)
        if response.status_code == 200:
            config = response.json()
            # Save config to file for inspection
            with open("config_dump.json", "w") as f:
                json.dump(config, f, indent=2)
            print("Configuration saved to config_dump.json")

            # Try to print institution list if available
            # It's usually in 'conf' -> 'institution' or similar
            print("Config keys:", config.keys())
        else:
            print(f"Failed to fetch config: {response.status_code}")
        print(f"User: {user_info.display_name} ({user_info.user_name})")
        print(
            f"Loans: {user_info.loans_count}, Requests: {user_info.requests_count}, Fines: {user_info.fines_amount} {user_info.fines_currency}"
        )

        print("\nFetching loans...")
        loans = await client.get_loans()
        for i, loan in enumerate(loans, 1):
            print(f"{i}. {loan.title}")
            print(f"   Author: {loan.author}")
            print(f"   Due: {loan.due_date} {loan.due_hour} at {loan.location_name} ({loan.sub_location_name})")
            print(f"   Status: {loan.status}, Renewable: {loan.renewable}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
