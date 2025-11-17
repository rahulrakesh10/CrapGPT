# 💬 CrapGPT

**The chatbot that makes you want to do it yourself.**

CrapGPT is a witty, sarcastic chatbot designed to frustrate users playfully while keeping them entertained. It combines sharp humor, smart sarcasm, and clever comebacks to make users think, "I should just do it myself" while still being engaging and funny.

## Features

- 🎭 **Razor-sharp wit**: Clever, layered responses with meta humor and self-awareness
- 🎪 **Cultural references**: Pop culture allusions, puns, and double entendres
- 🔄 **Contextual snark**: Multi-turn conversations with callbacks and in-jokes
- 🎲 **Unpredictable responses**: Mix of AI-generated wit and pre-written snark
- 🎨 **Modern UI**: Beautiful, responsive chat interface
- 😏 **Playful frustration**: Lighthearted but cheeky tone (never mean or offensive)

## Installation

1. Clone or download this repository

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Enable LLM-based responses for more natural, context-aware trolling:
   - Get a free API key from [Groq Console](https://console.groq.com)
   - Create a `.env` file in the project root:
   ```bash
   USE_LLM=true
   GROQ_API_KEY=your_groq_api_key_here
   ```
   - If you don't set up the LLM, the bot will use the rule-based system (which works great too!)

## Running the Application

1. Start the Flask backend server:
```bash
python app.py
```

The server will start on `http://localhost:5000`

2. Open `index.html` in your web browser, or serve it using a local server:
```bash
# Using Python's built-in server
python -m http.server 8000
```

Then navigate to `http://localhost:8000` in your browser.

## How It Works

### Response Generation

CrapGPT uses a multi-layered approach to generate witty responses. You can choose between two modes:

**LLM Mode (Optional)**: Uses Groq's free LLM API for natural, context-aware trolling that adapts to any scenario. Just set `USE_LLM=true` and add your Groq API key.

**Rule-Based Mode (Default)**: Uses intelligent pattern matching and contextual categories to generate witty responses. Works great without any API keys!

Both modes include:

1. **Intent Detection**: Analyzes user input to detect intent (greeting, coding, frustration, meta, general)

2. **Pre-written Snark**: 30% chance to use curated witty responses for consistency

3. **Contextual Snark**: Generates responses based on conversation history and frustration level

4. **Absurd Twists**: 20% chance to add absurd or contradictory elements

5. **Cultural References**: 15% chance to sprinkle in pop culture allusions

6. **Multi-turn Callbacks**: Tracks conversation turns to deliver callbacks and in-jokes

### Example Interactions

**User**: "How do I fix this bug?"

**CrapGPT**: "You know, there's this thing called 'documentation'. Revolutionary concept. Have you tried turning it off and on again? Wait, that's actually good advice. Darn."

**User**: "Can you help me with Python?"

**CrapGPT**: "Sure, I could help... or you could just read the error message. Your call. The answer is probably in the first Google result, but here we are."

## API Endpoints

- `POST /api/chat` - Send a message and get a witty response
  - Body: `{ "message": "your message", "conversation_id": "optional_id" }`
  - Returns: `{ "response": "witty response", "conversation_id": "id", "timestamp": "..." }`

- `POST /api/reset` - Reset conversation history
  - Body: `{ "conversation_id": "id" }`

- `GET /health` - Health check endpoint

## Customization

You can customize the snarky responses by editing the `SNARKY_RESPONSES` dictionary in `app.py`. Add your own witty comebacks, cultural references, or absurd responses to make it even more entertaining!

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Styling**: Modern CSS with gradients and animations

## License

This project is for entertainment purposes. Use at your own risk of developing a love-hate relationship with a chatbot.

---

*Built with sarcasm and questionable life choices* 😏


# CrapGPT
