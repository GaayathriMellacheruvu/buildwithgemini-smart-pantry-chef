import asyncio
import os
import sys
import time
from playwright.async_api import async_playwright

APP_URL = "https://smart-pantry-chef-frontend-af6pxfpkna-ue.a.run.app"
OUTPUT_DIR = "/config/.gemini/antigravity/scratch/smart-pantry-chef/videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def main():
    print("Starting Playwright demo recording...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print(f"Navigating to {APP_URL}...")
        await page.goto(APP_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. Toggle theme to showcase Dark Mode
        print("Toggling Dark Mode...")
        await page.click("#themeToggleBtn")
        await asyncio.sleep(1.5)

        # 2. Toggle Pantry & Favorites Sidebar
        print("Opening Pantry Sidebar...")
        await page.click("#pantryToggleBtn")
        await asyncio.sleep(2)

        # 3. Select Dietary Filter Badges
        print("Closing Pantry Sidebar and activating Dietary Filters...")
        await page.click("#sidebarCloseBtn")
        await asyncio.sleep(1)
        await page.click("button[data-tag='Vegetarian']")
        await asyncio.sleep(0.5)
        await page.click("button[data-tag='Under 30 Mins']")
        await asyncio.sleep(1)

        # 4. Prompt 1: Show main recipe feature
        prompt1 = "What recipe can I make with tomatoes, garlic, and pasta under 30 minutes?"
        print(f"Submitting Prompt 1: {prompt1}")
        await page.fill("#input", prompt1)
        await asyncio.sleep(1)
        await page.click("form button[type='submit']")

        # Wait for agent response
        print("Waiting for Agent response to Prompt 1...")
        await page.wait_for_selector(".msg-wrapper.agent", timeout=30000)
        await asyncio.sleep(4)

        # 5. Prompt 2: Rich prompt showing tool call, Firestore DB lookup, and Image Generation
        prompt2 = "Consult Culpeper's Herbal book for garlic remedies, check my Firestore pantry for fresh organic eggs, and generate a visual plating preview image for classic garlic pasta."
        print(f"Submitting Prompt 2: {prompt2}")
        await page.fill("#input", prompt2)
        await asyncio.sleep(1)
        await page.click("form button[type='submit']")

        # Wait for agent response and image card
        print("Waiting for Agent response and generated image to Prompt 2...")
        await page.wait_for_selector(".msg-wrapper.agent:nth-of-type(4)", timeout=60000)
        await asyncio.sleep(6)

        # Close context to flush video to disk
        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        print(f"Video recording saved successfully at: {video_path}")
        
        # Rename to a nice clear filename
        final_video_path = os.path.join(OUTPUT_DIR, "smart_pantry_chef_demo.webm")
        if os.path.exists(video_path):
            os.rename(video_path, final_video_path)
            print(f"Final demo video ready: {final_video_path}")
            return final_video_path

if __name__ == "__main__":
    asyncio.run(main())
