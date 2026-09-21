from agents.orion_agent import orion


def main():

    print("=" * 60)
    print("ORION - FIELD INTELLIGENCE")
    print("=" * 60)

    print("ORION is online.")
    print("Type 'exit' to stop.")
    print()

    while True:

        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in {
            "exit",
            "quit"
        }:
            print("ORION shutting down.")
            break

        try:

            response = orion.process(
                user_input
            )

            print()
            print("ORION:")
            print(response)
            print()

        except Exception as error:

            print()
            print("ORION ERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()