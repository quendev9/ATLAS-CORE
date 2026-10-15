
from voice.speech_input import listen_once


def main():
    try:
        input("Press Enter when you're ready to speak...")
        recognized_text = listen_once()

        if recognized_text:
            print(f"YOU SAID: {recognized_text}")
        else:
            print("No speech recognized. Try again.")

    except Exception as error:
        print(f"Voice input error: {error}")


if __name__ == "__main__":
    main()
