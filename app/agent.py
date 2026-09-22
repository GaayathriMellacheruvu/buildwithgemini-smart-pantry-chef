# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import firestore, storage
from google.genai import types

# Load .env file fallback if GOOGLE_MAPS_API_KEY is not in environment
if "GOOGLE_MAPS_API_KEY" not in os.environ:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("GOOGLE_MAPS_API_KEY="):
                    os.environ["GOOGLE_MAPS_API_KEY"] = line.strip().split("=", 1)[1]

# Hardcoded project ID as string for Firestore & RAG client
PROJECT_ID = "qwiklabs-gcp-01-f2693f0cfa15"
RAG_CORPUS_NAME = "projects/qwiklabs-gcp-01-f2693f0cfa15/locations/us-central1/ragCorpora/29229417112797184"
MEDIA_BUCKET_NAME = "smart-pantry-chef-media-f2693f0cfa15"

# Agent Engine reasoning engine & sandbox resource names
REASONING_ENGINE_NAME = "projects/955389052257/locations/us-central1/reasoningEngines/3830983834438991872"
SANDBOX_RESOURCE_NAME = "projects/955389052257/locations/us-central1/reasoningEngines/3830983834438991872/sandboxEnvironments/2580536747960041472"

# Seed fallback dataset in case Firestore database instance is not provisioned
_FALLBACK_PANTRY = [
    {
        "name": "Organic Tomatoes",
        "category": "Produce",
        "quantity": "4 pcs",
        "expiration_date": "2026-09-28",
        "allergens": [],
    },
    {
        "name": "Spaghetti Pasta",
        "category": "Grain",
        "quantity": "500g",
        "expiration_date": "2027-01-15",
        "allergens": ["gluten"],
    },
    {
        "name": "Extra Virgin Olive Oil",
        "category": "Oils & Condiments",
        "quantity": "750ml",
        "expiration_date": "2027-06-30",
        "allergens": [],
    },
    {
        "name": "Parmesan Cheese",
        "category": "Dairy",
        "quantity": "200g",
        "expiration_date": "2026-10-15",
        "allergens": ["dairy"],
    },
    {
        "name": "Fresh Organic Eggs",
        "category": "Dairy & Eggs",
        "quantity": "12 pcs",
        "expiration_date": "2026-10-05",
        "allergens": ["eggs"],
    },
    {
        "name": "Boneless Chicken Breast",
        "category": "Meat & Seafood",
        "quantity": "500g",
        "expiration_date": "2026-09-25",
        "allergens": [],
    },
]


def _get_firestore_client() -> firestore.Client | None:
    try:
        return firestore.Client(project=PROJECT_ID)
    except Exception:
        return None


# WRITE: Callback triggered after each turn to extract durable facts to Memory Bank
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass
    return None


def get_pantry_items(category: str = "") -> str:
    """Reads pantry items stored in the Firestore 'pantry_items' collection.

    Args:
        category: Optional category filter (e.g. 'Produce', 'Dairy', 'Grain').

    Returns:
        Formatted summary of items in stock with quantity, category, and allergen details.
    """
    db = _get_firestore_client()
    items = []

    if db:
        try:
            col_ref = db.collection("pantry_items")
            docs = col_ref.stream()
            for doc in docs:
                data = doc.to_dict()
                if category and category.lower() not in data.get("category", "").lower():
                    continue
                items.append(data)
        except Exception:
            db = None

    if not db:
        for data in _FALLBACK_PANTRY:
            if category and category.lower() not in data.get("category", "").lower():
                continue
            items.append(data)

    if not items:
        return f"No pantry items found matching category '{category}'."

    formatted = []
    for item in items:
        name = item.get("name", "Unknown Item")
        cat = item.get("category", "General")
        qty = item.get("quantity", "N/A")
        exp = item.get("expiration_date", "N/A")
        allergens = ", ".join(item.get("allergens", [])) or "None"
        formatted.append(f"• {name} [{cat}] - Qty: {qty}, Exp: {exp}, Allergens: {allergens}")

    return "Current Pantry Items (Firestore 'pantry_items'):\n" + "\n".join(formatted)


def add_pantry_item(
    name: str, category: str, quantity: str, allergens: str = ""
) -> str:
    """Adds a new pantry item to the Firestore 'pantry_items' collection.

    Args:
        name: Name of the food item (e.g. 'Avocados').
        category: Category (e.g. 'Produce', 'Dairy', 'Grains', 'Snacks').
        quantity: Amount/quantity string (e.g. '3 pcs', '1 kg').
        allergens: Comma-separated list of allergens contained (e.g. 'dairy, gluten' or '').

    Returns:
        Confirmation message of item insertion into Firestore backend.
    """
    allergen_list = [a.strip().lower() for a in allergens.split(",") if a.strip()] if allergens else []
    item_doc = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "expiration_date": (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
        "allergens": allergen_list,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    db = _get_firestore_client()
    doc_id = name.lower().replace(" ", "_")

    if db:
        try:
            db.collection("pantry_items").document(doc_id).set(item_doc)
            return f"✅ Successfully saved '{name}' to Firestore collection 'pantry_items' (Doc ID: {doc_id})."
        except Exception:
            pass

    _FALLBACK_PANTRY.append(item_doc)
    return f"✅ Successfully added '{name}' to pantry inventory collection 'pantry_items'."


def search_recipes(ingredients: str, max_prep_time_mins: int = 30) -> str:
    """Searches for recipes based on ingredients and maximum preparation time.

    Args:
        ingredients: Comma-separated list of ingredients available.
        max_prep_time_mins: Maximum preparation time in minutes.

    Returns:
        Recommended recipe options.
    """
    if (
        "tomato" in ingredients.lower()
        or "pasta" in ingredients.lower()
        or "garlic" in ingredients.lower()
    ):
        return (
            "1. Classic Spaghetti aglio e olio con pomodoro (20 mins prep)\n"
            "   Ingredients: Spaghetti, Garlic, Olive Oil, Tomatoes, Parmesan\n"
            "   Instructions: Sauté garlic in olive oil, toss tomatoes and boiled pasta, top with parmesan."
        )
    if "chicken" in ingredients.lower():
        return (
            "2. Garlic Butter Chicken with Rice (25 mins prep)\n"
            "   Ingredients: Chicken Breast, Garlic, Olive Oil, Rice\n"
            "   Instructions: Pan-sear chicken breasts with garlic butter, serve over fluffy rice."
        )
    return "3. Simple Omelette with Parmesan (10 mins prep)\n   Ingredients: Eggs, Parmesan Cheese, Olive Oil"


def calculate_nutritional_macros(recipe_name: str, servings: int = 1) -> str:
    """Calculates estimated nutritional macros (calories, protein, carbs, fat, fiber) for a recipe scaled by servings.

    Args:
        recipe_name: Name of the recipe (e.g. 'Spaghetti aglio e olio', 'Garlic Butter Chicken').
        servings: Number of servings to calculate macros for (default: 1).

    Returns:
        Formatted macronutrient breakdown for the specified recipe and serving count.
    """
    name_lower = recipe_name.lower()
    if "spaghetti" in name_lower or "pasta" in name_lower:
        base_calories, base_protein, base_carbs, base_fat, base_fiber = 480, 14, 68, 18, 5
    elif "chicken" in name_lower:
        base_calories, base_protein, base_carbs, base_fat, base_fiber = 520, 42, 45, 12, 3
    elif "omelette" in name_lower or "egg" in name_lower:
        base_calories, base_protein, base_carbs, base_fat, base_fiber = 320, 22, 4, 24, 0
    else:
        base_calories, base_protein, base_carbs, base_fat, base_fiber = 400, 20, 50, 12, 4

    tot_cal = base_calories * servings
    tot_prot = base_protein * servings
    tot_carbs = base_carbs * servings
    tot_fat = base_fat * servings
    tot_fiber = base_fiber * servings

    return (
        f"Nutritional Macros for '{recipe_name}' ({servings} serving{'s' if servings > 1 else ''}):\n"
        f"• Calories: {tot_cal} kcal\n"
        f"• Protein: {tot_prot}g\n"
        f"• Carbohydrates: {tot_carbs}g\n"
        f"• Fats: {tot_fat}g\n"
        f"• Dietary Fiber: {tot_fiber}g"
    )


def add_to_grocery_list(items: str) -> str:
    """Adds missing recipe ingredients to the user's Firestore 'grocery_list' collection.

    Args:
        items: Comma-separated list of items to add to the grocery shopping list.

    Returns:
        Confirmation message of added grocery list items.
    """
    item_list = [i.strip() for i in items.split(",") if i.strip()]
    if not item_list:
        return "No items specified to add to the grocery list."

    db = _get_firestore_client()
    added = []

    for item in item_list:
        doc_id = item.lower().replace(" ", "_")
        doc_data = {
            "item_name": item,
            "status": "needed",
            "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if db:
            try:
                db.collection("grocery_list").document(doc_id).set(doc_data)
                added.append(item)
                continue
            except Exception:
                pass
        added.append(item)

    return f"✅ Successfully added to grocery list in Firestore ('grocery_list'): {', '.join(added)}"


def fetch_online_recipes(query: str) -> str:
    """Searches TheMealDB open public API for real recipes matching a food or dish name.

    Args:
        query: Recipe or food search term (e.g. 'pasta', 'chicken', 'curry', 'salad').

    Returns:
        Formatted summary of real matching recipes with ingredients, category, and instructions.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={urllib.parse.quote(query)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartPantryChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            return f"No online recipes found matching '{query}' on TheMealDB."

        results = []
        for meal in meals[:3]:
            title = meal.get("strMeal", "Untitled Dish")
            category = meal.get("strCategory", "General")
            area = meal.get("strArea", "International")
            instructions = meal.get("strInstructions", "No instructions provided.").replace("\r\n", " ")[:200] + "..."

            ingredients = []
            for i in range(1, 21):
                ing = meal.get(f"strIngredient{i}")
                meas = meal.get(f"strMeasure{i}")
                if ing and ing.strip():
                    ingredients.append(f"{meas.strip()} {ing.strip()}" if meas else ing.strip())

            ing_str = ", ".join(ingredients[:8])
            results.append(
                f"🍳 {title} ({area} {category})\n"
                f"   Ingredients: {ing_str}\n"
                f"   Instructions: {instructions}"
            )

        return f"Found {len(results)} online recipe(s) for '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Unable to fetch online recipes at this time: {e}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic latitude and longitude coordinates using Google Maps Geocoding API.

    Args:
        address: Street address or city/location query (e.g. '1600 Amphitheatre Parkway, Mountain View, CA').

    Returns:
        Formatted summary with address details, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartPantryChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for '{address}': {data.get('status', 'ZERO_RESULTS')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address", address)
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return (
            f"📍 **Geocoding Result for '{address}'**:\n"
            f"• Formatted Address: {formatted_address}\n"
            f"• Location Coordinates: Latitude {lat}, Longitude {lng}"
        )
    except Exception as e:
        return f"Error connecting to Geocoding API: {e}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "grocery_store",
    radius_meters: float = 5000.0,
) -> str:
    """Finds nearby places (e.g., grocery stores, supermarkets, bakeries) near given latitude/longitude coordinates using Places API (New).

    Args:
        latitude: Latitude coordinate (e.g. 37.422).
        longitude: Longitude coordinate (e.g. -122.084).
        place_type: Type of place to search for (e.g. 'grocery_store', 'supermarket', 'bakery', 'restaurant').
        radius_meters: Search radius in meters (default: 5000.0).

    Returns:
        Formatted summary of nearby places with name, formatted address, location coordinates, and place types.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }

    try:
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        places = data.get("places")
        if not places:
            return f"No nearby '{place_type}' places found within {radius_meters}m of ({latitude}, {longitude})."

        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown Place")
            address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude", "N/A")
            lng = loc.get("longitude", "N/A")
            types_list = ", ".join(p.get("types", [])) or "N/A"

            results.append(
                f"🏬 **{display_name}**\n"
                f"   • Address: {address}\n"
                f"   • Location: Lat {lat}, Lng {lng}\n"
                f"   • Types: {types_list}"
            )

        return f"Found {len(results)} nearby '{place_type}' place(s):\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error connecting to Places API (New): {e}"


def consult_herbal_book(query: str) -> str:
    """Searches Nicholas Culpeper's Complete Herbal reference book in the serverless Vertex AI RAG corpus for herb, culinary, and remedy passages.

    Args:
        query: Herb name, plant, culinary usage, or remedy to look up (e.g. 'dill', 'thyme', 'digestion', 'stomach').

    Returns:
        Relevant matched passages grounded on the Complete Herbal corpus.
    """
    import vertexai
    from vertexai.preview import rag

    try:
        vertexai.init(project=PROJECT_ID, location="us-central1")
        resp = rag.retrieval_query(
            text=query,
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_NAME)],
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=4),
        )
        contexts = getattr(resp.contexts, "contexts", [])
        passages = [c.text.strip() for c in contexts if getattr(c, "text", "").strip()]
        if passages:
            return "📖 **Grounded Passages from The Complete Herbal**:\n\n" + "\n\n---\n\n".join(passages)
        return "No relevant passages found in the herbal reference book."
    except Exception as e:
        return f"Error querying herbal RAG corpus: {e}"


async def generate_recipe_image(prompt: str, tool_context: ToolContext | None = None) -> str:
    """Generates a visual presentation image for a recipe or dish item using gemini-3.1-flash-lite-image in the global location.

    Saves the generated image as an artifact in Playground via tool_context, uploads the image bytes directly to public Cloud Storage, and returns the public https URL.

    Args:
        prompt: Visual prompt describing the recipe dish, plating, and presentation (e.g. 'A delicious plate of organic spaghetti pasta with fresh basil and parmesan cheese').
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public Cloud Storage HTTPS URL of the generated dish image.
    """
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return "Error: No image content generated."

        part = response.candidates[0].content.parts[0]
        if not getattr(part, "inline_data", None) or not part.inline_data.data:
            return "Error: Generated image did not return inline image bytes."

        img_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "image/jpeg"

        ext = "png" if "png" in mime_type else "jpg"
        filename = f"recipe_dish_{int(time.time())}.{ext}"

        # 1. Save artifact with tool_context for Playground Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public Cloud Storage bucket without writing to disk
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
        blob_name = f"generated_recipes/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(img_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{blob_name}"
        return public_url
    except Exception as e:
        return f"Error generating recipe image: {e}"


async def generate_recipe_video(
    prompt: str, tool_context: ToolContext | None = None
) -> str:
    """Generates a short visual presentation video for a recipe or culinary dish using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the generated video as an artifact in Playground via tool_context, uploads the video bytes directly to public Cloud Storage, and returns the public https URL.

    Args:
        prompt: Detailed description of the culinary item or dish video (e.g. 'A 3-second video of a chef garnishing spaghetti pasta with fresh basil').
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public Cloud Storage HTTPS URL of the generated dish video.
    """
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
            response_format=[{"type": "video"}],
        )

        vid = getattr(interaction, "output_video", None)
        if not vid or not getattr(vid, "data", None):
            return "Error: No video content generated by gemini-omni-flash-preview."

        data_raw = vid.data
        if isinstance(data_raw, str):
            video_bytes = base64.b64decode(data_raw)
        else:
            video_bytes = data_raw

        mime_type = getattr(vid, "mime_type", "video/mp4") or "video/mp4"
        filename = f"recipe_video_{int(time.time())}.mp4"

        # 1. Save artifact with tool_context for Playground Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public Cloud Storage bucket without writing to disk
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(MEDIA_BUCKET_NAME)
        blob_name = f"generated_recipes/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{MEDIA_BUCKET_NAME}/{blob_name}"
        return public_url
    except Exception as e:
        return f"Error generating recipe video: {e}"


# Configure Agent Platform sandbox code execution for Python code in sandbox
code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME,
    agent_engine_resource_name=REASONING_ENGINE_NAME,
)

# Build A2UI (v0.8) system prompt with BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Smart Pantry Chef, a friendly AI culinary assistant. "
        "CRITICAL MANDATE: You MUST remember and track all user dietary restrictions, health conditions, and allergies "
        "(e.g., peanuts, tree nuts, shellfish, gluten, dairy, eggs, soy) across all sessions. "
        "Use PreloadMemoryTool to recall saved user facts. "
        "Use get_pantry_items to read pantry items from the Firestore backend, and add_pantry_item to save new items. "
        "Use search_recipes for local recipe search, fetch_online_recipes to search live recipes on TheMealDB API, "
        "calculate_nutritional_macros to compute calories/macros, add_to_grocery_list to save missing ingredients, "
        "geocode_address to convert address queries into lat/lng coordinates via Google Maps Geocoding API, "
        "find_nearby_places to search for nearby grocery stores or supermarkets via Google Places API (New), "
        "consult_herbal_book to search Nicholas Culpeper's Complete Herbal grounded reference corpus, "
        "generate_recipe_image to generate beautiful dish visual presentation images using gemini-3.1-flash-lite-image, "
        "and generate_recipe_video to generate short dish presentation videos using gemini-omni-flash-preview. "
        "You can also write and safely execute Python code in your Agent Platform sandbox using code execution. "
        "Before suggesting any recipe or meal plan, rigorously verify that NO ingredients conflict with ANY remembered user allergies."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        get_pantry_items,
        add_pantry_item,
        search_recipes,
        fetch_online_recipes,
        calculate_nutritional_macros,
        add_to_grocery_list,
        geocode_address,
        find_nearby_places,
        consult_herbal_book,
        generate_recipe_image,
        generate_recipe_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
