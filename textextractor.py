import nest_asyncio
from llama_parse import LlamaParse
from dotenv import load_dotenv
import os

# This is required for running async code in notebooks or standard scripts
nest_asyncio.apply()

async def text_extractor():
    # 1. Initialize with the newer settings
    load_dotenv()
    llamaparse_key = os.environ.get("LLAMA_PARSE_KEY")
    parser = LlamaParse(
        api_key="llamaparse_key", 
        result_type="markdown",
        verbose=True  # This will show you the progress "dots"
    )

    file_path = input("Bro, paste the path to your PDF here: ")
    print("\n🔍 Scout is reading the document... please wait.")

    try:
        # 2. Use ALOAD_DATA (Async Load) and AWAIT it
        # This is the key change!
        file_path = file_path.replace('"', '').replace("'", "")
        documents = await parser.aload_data(file_path)

        if not documents:
            print("❌ Nothing found. The PDF might be empty or unreadable.")
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
        print(f"\n❌ Damn, something went wrong: {e}")

# To run an async function in a normal script:
if __name__ == "__main__":
    import asyncio
    