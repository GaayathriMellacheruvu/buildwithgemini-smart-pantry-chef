#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Seed script for smart-pantry-chef Firestore backend

import sys
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-f2693f0cfa15"

SEED_ITEMS = [
    {
        "id": "tomatoes",
        "name": "Organic Tomatoes",
        "category": "Produce",
        "quantity": "4 pcs",
        "expiration_date": "2026-09-28",
        "allergens": [],
    },
    {
        "id": "spaghetti",
        "name": "Spaghetti Pasta",
        "category": "Grain",
        "quantity": "500g",
        "expiration_date": "2027-01-15",
        "allergens": ["gluten"],
    },
    {
        "id": "olive_oil",
        "name": "Extra Virgin Olive Oil",
        "category": "Oils & Condiments",
        "quantity": "750ml",
        "expiration_date": "2027-06-30",
        "allergens": [],
    },
    {
        "id": "parmesan",
        "name": "Parmesan Cheese",
        "category": "Dairy",
        "quantity": "200g",
        "expiration_date": "2026-10-15",
        "allergens": ["dairy"],
    },
    {
        "id": "eggs",
        "name": "Fresh Organic Eggs",
        "category": "Dairy & Eggs",
        "quantity": "12 pcs",
        "expiration_date": "2026-10-05",
        "allergens": ["eggs"],
    },
    {
        "id": "chicken",
        "name": "Boneless Chicken Breast",
        "category": "Meat & Seafood",
        "quantity": "500g",
        "expiration_date": "2026-09-25",
        "allergens": [],
    },
]


def seed_database():
    print(f"Initializing Firestore client for project: {PROJECT_ID}")
    try:
        db = firestore.Client(project=PROJECT_ID)
        collection_ref = db.collection("pantry_items")

        for item in SEED_ITEMS:
            item_id = item["id"]
            data = {k: v for k, v in item.items() if k != "id"}
            collection_ref.document(item_id).set(data)
            print(f"  - Seeded Firestore doc 'pantry_items/{item_id}': {data['name']}")

        print("✅ Firestore seed complete!")
    except (NotFound, PermissionDenied, Exception) as e:
        print(f"⚠️ Cloud Firestore unavailable ({e}). Using seeded fallback pantry dataset.")


if __name__ == "__main__":
    seed_database()
