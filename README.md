# Smart Pantry Chef 🍳

An intelligent, AI-powered culinary assistant built with Google's Agent Development Kit (ADK), Vertex AI, and Google Cloud services. Smart Pantry Chef helps users discover personalized recipes based on their current pantry inventory, tracks dietary restrictions across sessions, grounds herbal remedies, finds local grocery stores, and generates visual recipe media previews.

![Smart Pantry Chef Demo](demo.gif)

---

## 🌟 Key Features & Implemented Capabilities

Smart Pantry Chef connects directly to Google Cloud services and ADK tools to deliver a personalized culinary experience:

- **🧠 Persistent Memory Bank**: Automatically recalls and tracks user allergies, health conditions, and dietary preferences across sessions (`PreloadMemoryTool`, `generate_memories_callback`).
- **🧺 Firestore Pantry & Grocery Management**: Performs NoSQL database lookups and writes to manage pantry inventory and saved grocery lists in Google Cloud Firestore (`get_pantry_items`, `add_pantry_item`, `add_to_grocery_list`).
- **📚 Grounded Herbal Knowledge (RAG)**: Searches Nicholas Culpeper's *The Complete Herbal* reference corpus using Vertex AI grounded retrieval (`consult_herbal_book`).
- **🖼️ Dish Image Generation**: Generates dish plating preview images using `gemini-3.1-flash-lite-image`, uploads bytes to Google Cloud Storage, and registers Playground artifacts (`generate_recipe_image`).
- **🎬 Dish Video Generation**: Generates short dish presentation videos using Google's Omni model (`gemini-omni-flash-preview` in global region), uploads bytes to Google Cloud Storage, and registers Playground artifacts (`generate_recipe_video`).
- **📍 Location & Grocery Store Finder**: Converts address queries to lat/lng coordinates and locates nearby supermarkets using Google Maps Geocoding and Google Places APIs (`geocode_address`, `find_nearby_places`).
- **🌐 Recipe & Macro Calculation**: Performs local recipe matching, fetches live online recipes via TheMealDB API, and calculates macronutrient breakdowns (`search_recipes`, `fetch_online_recipes`, `calculate_nutritional_macros`).
- **💻 Sandbox Code Execution**: Generates and executes Python code safely in the Agent Platform sandbox (`AgentEngineSandboxCodeExecutor`).
- **🎨 Interactive A2UI Protocol**: Renders rich UI cards using the A2UI v0.8 schema (`a2ui_callback`).
- **✨ Custom Modern Web Frontend**: Features a dark/light mode toggle, interactive pantry drawer, dietary filter chips (`Vegetarian`, `Gluten-Free`, `Low Carb`, `Under 30m`), animated cooking indicator, voice input, and message action buttons.

---

## 🛠️ Google Cloud Services & Technologies Wired Up

Based on `app/agent.py` and `agents-cli-manifest.yaml`:

| Service / Technology | Implementation Details |
| :--- | :--- |
| **Vertex AI Reasoning Engine** | ADK `Agent` core running `gemini-2.5-flash` model (`us-east1`). |
| **Google Cloud Firestore** | NoSQL database for pantry inventory and grocery list items. |
| **Google Cloud Storage** | Public storage bucket for hosting generated dish images and MP4 videos. |
| **Vertex AI Generative Media** | `gemini-3.1-flash-lite-image` for image generation and `gemini-omni-flash-preview` (global) for video generation. |
| **Vertex AI RAG Search** | Grounded retrieval over Nicholas Culpeper's *The Complete Herbal* corpus. |
| **Google Maps & Places APIs** | Geocoding API and Google Places API (New) for location-aware store searches. |
| **Agent Platform Sandbox** | `AgentEngineSandboxCodeExecutor` for executing Python code in a secure sandbox. |
| **ADK & A2UI Protocol** | Agent Development Kit framework with A2UI v0.8 schema rendering. |

---

## 🚀 Setup & Local Execution Instructions

### Prerequisites
- Python 3.10+
- Google Cloud SDK (`gcloud` CLI)
- An active GCP project with Vertex AI, Firestore, and Cloud Storage enabled

### 1. Environment Setup
Clone the repository and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set required environment variables:

```bash
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
```

### 2. Run the Agent Server Locally
Start the local ADK app development server:

```bash
python3 -m app.main
```

### 3. Run the Frontend Locally
In a separate terminal, start the custom frontend web server:

```bash
cd frontend
python3 -m http.server 8080
```

Open your browser and navigate to your local web server port to interact with Smart Pantry Chef.

---

## 📹 Recording a Demo Video

To record an automated screen-capture demo with the branded overlay frame:

```bash
node .agents/skills/record-demo/record-agent.js \
  -u http://127.0.0.1:8080/ \
  -q "What recipe can I make with tomatoes, garlic, and pasta under 30 minutes?" \
  -q "Consult Culpeper's Herbal book for garlic remedies, check my Firestore pantry for fresh organic eggs, and generate a visual plating preview image for classic garlic pasta." \
  -o agent_demo.webm
```

To convert the WebM video to an optimized looping GIF for embedding:

```bash
ffmpeg -i agent_demo.webm -vf "fps=12,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" -loop 0 demo.gif
```
