from src.core.brain import JarvisBrain


def main():
    print("=" * 50)
    print("JARVIS V6")
    print("Lokaler KI-Assistent")
    print("=" * 50)
    print("JARVIS ist bereit, Sir.")
    print("Mit 'exit' beenden.")
    print()

    try:
        brain = JarvisBrain()
    except Exception as error:
        print(f"[FEHLER] JARVIS konnte nicht gestartet werden:")
        print(error)
        return

    while True:

        try:
            message = input("Du: ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\nJARVIS wird beendet, Sir.")
            break

        if not message:
            continue

        if message.lower() in {
            "exit",
            "quit",
            "beenden"
        }:
            print("JARVIS wird beendet, Sir.")
            break

        try:
            answer = brain.respond(message)

            print(f"JARVIS: {answer}")

        except Exception as error:
            print(
                f"[FEHLER] Bei der Verarbeitung ist "
                f"ein Fehler aufgetreten: {error}"
            )


if __name__ == "__main__":
    main()