#👨‍🔧 we are importing net_asyncio because when we are gonna deploy our code at the cloud platforms. these platforms already running async function. so with nest_asyncio we can nest them. we don't do this it can cause RunTimeERROR: event loop is already running.
import nest_asyncio
from llama_parse import LlamaParse
from dotenv import load_dotenv
import os
import logging


logger  = logging.getLogger("Scout.textextractor")
# This is required for running async code in notebooks or standard scripts
nest_asyncio.apply()

async def text_extractor(file_path : str):
    # 1. Initialize with the newer settings
    load_dotenv()
    llamaparse_key = os.environ.get("LLAMA_PARSE_KEY")
    parser = LlamaParse(
        api_key=llamaparse_key, 
        result_type="markdown", # we are ruturning markdown here. cause it will return result with markdowns like #, **, |, -. so it will be easy for our summmarizer to understand. if we don't use this it will return raw text. Note: we can also return Json.
        verbose=True  # This will show you the progress "dots"
    )

    try:
        # 2. Use ALOAD_DATA (Async Load) and AWAIT it
        # This is the key change!
        file_path = file_path.replace('"', '').replace("'", "")
        documents = await parser.aload_data(file_path)

        if not documents:
            logger.error("❌ Nothing found. The PDF might be empty or unreadable.")
            return None

        # 3. Extract the text from the first document object
        extracted_text = documents[0].text
        
        # print("\n✅ Extraction Complete! Preview:")
        # print("-" * 30)
        # print(extracted_text[:1000]) # Shows first 1000 characters
        # print("-" * 30)
        # print(documents)
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"\n❌ Damn, something went wrong: {e}")

# To run an async function in a normal script:
if __name__ == "__main__":
    import asyncio
    