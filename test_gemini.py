
import os
from dotenv import load_dotenv
from google import genai


def main():
    load_dotenv()

    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY")
    )

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input="Responda apenas: Gemini conectado."
    )

    print(interaction.output_text)


if __name__ == "__main__":
    main()
