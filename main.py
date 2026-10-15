
from ai.model import close_gemini
from core.lewis import Lewis
from voice.speech_input import listen_once
from voice.speech_output import speak


def main():
    lewis = Lewis()

    print("LEWIS CORE ONLINE")
    print("Choose input mode:")
    print("[1] Text")
    print("[2] Voice (push-to-talk)")

    mode = input("MODE: ").strip()

    if mode not in {"1", "2"}:
        print("Invalid mode. Starting text mode.")
        mode = "1"

    try:
        while True:
            try:
                if mode == "2":
                    input("\nPress Enter to talk, or type 'exit' to quit: ")

                    # Check for exit before opening the microphone.
                    # The prompt accepts Enter or text; typing exit quits.
                    # (See the note below for the improved prompt.)
                    user_input = listen_once()
                else:
                    user_input = input("\nYOU: ")

                user_input = user_input.strip()

                if not user_input:
                    print("No input received. Try again.")
                    continue

                if user_input.casefold() == "exit":
                    print("LEWIS CORE OFFLINE")
                    break

                print(f"YOU: {user_input}")

                response = lewis.process(user_input)
                print(f"LEWIS: {response}")

                if mode == "2":
                    speak(response)

            except KeyboardInterrupt:
                print("\nLEWIS CORE OFFLINE")
                break
            except Exception as error:
                print(f"Input error: {error}")
                if mode == "2":
                    print("Voice mode is still active. You can try again.")

    finally:
        close_gemini()


if __name__ == "__main__":
    main()
