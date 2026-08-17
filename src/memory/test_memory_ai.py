from src.core.brain import JarvisBrain


brain = JarvisBrain()


tests = [
    "Ich mag Tyler, The Creator.",
    "Ich möchte später Dachdecker werden.",
    "Ich sitze gerade am PC.",
    "Ich hasse Spinnen.",
]


for message in tests:

    print()
    print("Nachricht:", message)
    print("Ergebnis:")

    result = brain.analyze_message(message)

    print(result)