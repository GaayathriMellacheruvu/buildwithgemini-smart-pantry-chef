# Copyright 2026 Google LLC
# Script to create a serverless Vertex AI RAG corpus and import Project Gutenberg document

import sys
import vertexai
from vertexai.preview import rag
from vertexai.preview.rag.utils import resources as rr

PROJECT_ID = "qwiklabs-gcp-01-f2693f0cfa15"
LOCATION = "us-central1"
GCS_PATH = "gs://smart-pantry-chef-media-f2693f0cfa15/rag/pg49513.txt"

PARSING_PROMPT = (
    "Extract the individual useful facts, herbs, plants, culinary and medicinal remedies described in this text. "
    "Ignore and omit all Gutenberg metadata, license boilerplate, and headers. "
    "Output clean, self-contained prose."
)

print(f"Initializing Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})...")
vertexai.init(project=PROJECT_ID, location=LOCATION)

# 1. Set serverless mode for the project/location
cfg = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
print("Setting RAG Engine mode to Serverless...")
try:
    rag.update_rag_engine_config(
        rag_engine_config=rag.RagEngineConfig(
            name=cfg,
            rag_managed_db_config=rag.RagManagedDbConfig(mode=rr.Serverless()),
        )
    )
    print("✅ Serverless mode configured.")
except Exception as e:
    print(f"Notice during update_rag_engine_config: {e}")

# 2. Create the corpus
print("Creating RAG corpus 'herbal-culinary-corpus'...")
corpus = rag.create_corpus(
    display_name="herbal-culinary-corpus",
    embedding_model_config=rag.EmbeddingModelConfig(
        publisher_model="publishers/google/models/text-embedding-005"
    ),
)
corpus_name = corpus.name
print(f"✅ Corpus created successfully: {corpus_name}")

# 3. Import and index document
print(f"Importing and indexing document from {GCS_PATH}...")
resp = rag.import_files(
    corpus_name=corpus_name,
    paths=[GCS_PATH],
    transformation_config=rag.TransformationConfig(
        chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=100)
    ),
    llm_parser=rag.LlmParserConfig(
        model_name="gemini-2.5-flash",
        custom_parsing_prompt=PARSING_PROMPT,
    ),
)
print(f"✅ Import complete! Status: {resp}")

with open("rag_corpus_info.txt", "w") as f:
    f.write(corpus_name)
print(f"Saved corpus resource name to 'rag_corpus_info.txt': {corpus_name}")
