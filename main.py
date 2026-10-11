from ai.model import close_gemini
from core.atlas import Atlas


def main():
    atlas = Atlas()

    print("ATLAS CORE ONLINE")

    try:
        while True:

            user_input = input("YOU: ")

            if user_input.lower() == "exit":
                print("ATLAS CORE OFFLINE")
                break

            response = atlas.process(user_input)

            print(f"ATLAS: {response}")
    finally:
        close_gemini()


if __name__ == "__main__":
    main()