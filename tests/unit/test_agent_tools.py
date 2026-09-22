# Copyright 2026 Google LLC
# Unit tests for smart-pantry-chef tools

import pytest
from app.a2ui_utils import a2ui_callback
from app.agent import (
    calculate_nutritional_macros,
    consult_herbal_book,
    fetch_online_recipes,
    find_nearby_places,
    generate_recipe_image,
    geocode_address,
    get_pantry_items,
    root_agent,
)
from google.adk.code_executors import AgentEngineSandboxCodeExecutor


def test_calculate_nutritional_macros():
    result = calculate_nutritional_macros("Spaghetti aglio e olio", servings=2)
    assert "Spaghetti aglio e olio" in result
    assert "2 servings" in result
    assert "Calories: 960 kcal" in result
    assert "Protein: 28g" in result


def test_calculate_nutritional_macros_single_serving():
    result = calculate_nutritional_macros("Garlic Butter Chicken", servings=1)
    assert "1 serving" in result
    assert "Protein: 42g" in result


def test_fetch_online_recipes():
    result = fetch_online_recipes("pasta")
    assert "pasta" in result.lower()
    assert "Ingredients:" in result or "No online recipes found" in result


def test_geocode_address():
    result = geocode_address("1600 Amphitheatre Parkway, Mountain View, CA")
    assert "Mountain View" in result or "Latitude" in result
    assert "37.4" in result


def test_find_nearby_places():
    result = find_nearby_places(latitude=37.422, longitude=-122.084, place_type="grocery_store")
    assert "nearby" in result.lower() or "place" in result.lower()


def test_consult_herbal_book():
    result = consult_herbal_book("digestion")
    assert "The Complete Herbal" in result or "Digestion" in result or "passages" in result.lower()


@pytest.mark.asyncio
async def test_generate_recipe_image():
    result = await generate_recipe_image("A gourmet plate of spaghetti aglio e olio with fresh basil")
    assert result.startswith("https://storage.googleapis.com/smart-pantry-chef-media-f2693f0cfa15/generated_recipes/")
    assert ".jpg" in result or ".png" in result


def test_agent_sandbox_code_executor_configured():
    assert root_agent.code_executor is not None
    assert isinstance(root_agent.code_executor, AgentEngineSandboxCodeExecutor)
    assert "sandboxEnvironments" in getattr(root_agent.code_executor, "sandbox_resource_name", "")


def test_agent_a2ui_configured():
    assert root_agent.after_model_callback == a2ui_callback
    assert "beginRendering" in root_agent.instruction
    assert "surfaceUpdate" in root_agent.instruction
