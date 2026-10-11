
import pyttsx3


engine = pyttsx3.init()
voices = engine.getProperty("voices")

print("\n=== ATLAS VOICE INVENTORY ===\n")

for index, voice in enumerate(voices):
    print(f"[{index}] Name: {voice.name}")
    print(f"    ID: {voice.id}")
    print(f"    Languages: {voice.languages}")
    print()

print(f"Total available voices: {len(voices)}")

engine.stop()
