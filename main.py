from core.atlas import Atlas


atlas = Atlas()

print("ATLAS CORE ONLINE")

while True:

    user_input = input("YOU: ")

    if user_input.lower() == "exit":
        print("ATLAS CORE OFFLINE")
        break

    response = atlas.process(user_input)

    print(f"ATLAS: {response}")